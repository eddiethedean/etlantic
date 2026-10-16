"""SQLModel-backed DurableWorkStore (CP3 / 041-P).

Reference provider: each mutating call loads the durable snapshot inside a
database transaction, applies MemoryDurableWorkStore semantics, and writes the
snapshot back with an optimistic ``payload_version`` check before commit.

Production note: apply versioned migrations — do not rely on
``create_durable_tables`` as the sole schema path.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from time import sleep
from typing import Any, TypeVar, cast

from sqlalchemy import Column, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from etlantic.control_plane.durable_memory import MemoryDurableWorkStore
from etlantic.control_plane.durable_models import (
    DiffRecord,
    EffectRecord,
    ExecutionRouteLifecycle,
    ExecutionRouteRecord,
    ExecutionRouteWorkload,
    ExecutionScopePage,
    PreviewWorkspace,
    ResultPublicationRecord,
    ShadowRunRecord,
    SubmissionRecord,
    execution_context_from_submission,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic_sqlmodel.control_plane.models import (
    DurableOutboxEntityRow,
    DurableSnapshotRow,
    DurableSubmissionEntityRow,
)
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import Session, SQLModel, select

T = TypeVar("T")

_DURABLE_TXN_MAX_ATTEMPTS = 4
_DURABLE_TXN_RETRY_BASE_SECONDS = 0.01

DURABLE_TABLES = (
    DurableSnapshotRow,
    DurableSubmissionEntityRow,
    DurableOutboxEntityRow,
)


def create_durable_tables(engine: Engine) -> None:
    """Create CP3 durable tables (tests/demos only)."""
    SQLModel.metadata.create_all(
        engine,
        tables=[
            SQLModel.metadata.tables[table_name]
            for table_name in (
                "cp_durable_snapshot",
                "cp_durable_submission_entity",
                "cp_durable_outbox_entity",
            )
        ],
    )


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _is_sqlite_lock_error(error: OperationalError) -> bool:
    message = str(error).lower()
    return "database is locked" in message or "database table is locked" in message


class SQLModelDurableWorkStore:
    """Transactional DurableWorkStore backed by a SQL snapshot row."""

    def __init__(
        self,
        engine: Engine,
        *,
        admission_limit: int | None = None,
        store_id: str = "default",
    ) -> None:
        self.engine = engine
        self.admission_limit = admission_limit
        self.store_id = store_id

    def _txn(self, fn: Callable[[MemoryDurableWorkStore], T]) -> T:
        for attempt in range(_DURABLE_TXN_MAX_ATTEMPTS):
            try:
                with session_scope(self.engine) as session:
                    self._lock_store(session)
                    mem, version = self._read(session, for_update=True)
                    if self.admission_limit is not None:
                        mem.admission_limit = self.admission_limit
                    result = fn(mem)
                    self._write(session, mem, expected_version=version)
                    return result
            except ControlPlaneError as exc:
                # A concurrent durable mutation can win the snapshot CAS while
                # this operation is in flight. Re-read and re-apply the pure
                # memory-store operation against the committed state instead
                # of treating an unrelated heartbeat as lease loss.
                if (
                    attempt + 1 == _DURABLE_TXN_MAX_ATTEMPTS
                    or not exc.detail.startswith("Durable snapshot version conflict")
                ):
                    raise
            except OperationalError as exc:
                # SQLite reports a stale read transaction as "database is
                # locked" when another writer commits before this transaction
                # upgrades its read lock. The failed transaction is rolled
                # back by session_scope, so retrying the in-memory operation is
                # safe and lets the next read observe the winning snapshot.
                if (
                    attempt + 1 == _DURABLE_TXN_MAX_ATTEMPTS
                    or self.engine.dialect.name != "sqlite"
                    or not _is_sqlite_lock_error(exc)
                ):
                    raise

            if attempt + 1 < _DURABLE_TXN_MAX_ATTEMPTS:
                sleep(_DURABLE_TXN_RETRY_BASE_SECONDS * (2**attempt))
        raise RuntimeError("Durable transaction retry loop exhausted")

    def _lock_store(self, session: Session) -> None:
        """Serialize PostgreSQL mutations even before the snapshot row exists.

        ``SELECT FOR UPDATE`` cannot lock a missing row. Without a transaction
        advisory lock, two fresh processes can both observe version zero and
        race to create the snapshot, which turns a valid concurrent accept
        into a uniqueness failure instead of an idempotent recovery.
        """
        if self.engine.dialect.name != "postgresql":
            return
        digest = hashlib.sha256(self.store_id.encode("utf-8")).digest()[:8]
        lock_id = int.from_bytes(digest, byteorder="big", signed=True)
        session.connection().execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
        )

    def _read_only(self, fn: Callable[[MemoryDurableWorkStore], T]) -> T:
        with session_scope(self.engine) as session:
            mem, _version = self._read(session, for_update=False)
            if self.admission_limit is not None:
                mem.admission_limit = self.admission_limit
            return fn(mem)

    def apply_in_transaction(
        self,
        session: Session,
        operation: Callable[[MemoryDurableWorkStore], T],
    ) -> T:
        """Apply durable-work semantics inside a caller-owned SQL transaction.

        This public coordination hook lets same-engine stores commit linked
        state atomically without reaching into this adapter's snapshot methods.
        The caller owns transaction lifetime and must share this store's engine.
        """
        self._lock_store(session)
        memory, version = self._read(session, for_update=True)
        if self.admission_limit is not None:
            memory.admission_limit = self.admission_limit
        result = operation(memory)
        self._write(session, memory, expected_version=version)
        return result

    def _read(
        self, session: Session, *, for_update: bool
    ) -> tuple[MemoryDurableWorkStore, int]:
        stmt = select(DurableSnapshotRow).where(
            DurableSnapshotRow.store_id == self.store_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        row = session.exec(stmt).first()
        if row is None:
            return MemoryDurableWorkStore(admission_limit=self.admission_limit), 0
        return (
            MemoryDurableWorkStore.from_snapshot(json.loads(row.payload_json or "{}")),
            int(row.payload_version or 0),
        )

    def _write(
        self,
        session: Session,
        store: MemoryDurableWorkStore,
        *,
        expected_version: int,
    ) -> None:
        payload = json.dumps(store.to_snapshot(), sort_keys=True)
        row = session.exec(
            select(DurableSnapshotRow)
            .where(DurableSnapshotRow.store_id == self.store_id)
            .with_for_update()
        ).first()
        if row is None:
            if expected_version != 0:
                raise ControlPlaneError.conflict(
                    "Durable snapshot version conflict (missing row)"
                )
            session.add(
                DurableSnapshotRow(
                    store_id=self.store_id,
                    payload_json=payload,
                    payload_version=1,
                    updated_at=_utcnow_iso(),
                )
            )
            self._sync_entity_tables(session, store)
            return
        current = int(row.payload_version or 0)
        if current != expected_version:
            raise ControlPlaneError.conflict(
                "Durable snapshot version conflict (stale write)"
            )
        row.payload_json = payload
        row.payload_version = current + 1
        row.updated_at = _utcnow_iso()
        session.add(row)
        self._sync_entity_tables(session, store)

    def _sync_entity_tables(
        self, session: Session, store: MemoryDurableWorkStore
    ) -> None:
        """Dual-write mirrors while preserving IDs used by bounded keyset scans."""
        submission_rows = session.exec(
            select(DurableSubmissionEntityRow).where(
                DurableSubmissionEntityRow.store_id == self.store_id
            )
        ).all()
        existing_submissions = {
            (row.tenant_id, row.workspace_id, row.submission_id): row
            for row in submission_rows
        }
        current_submission_keys: set[tuple[str, str, str]] = set()
        for key, submission in store.iter_submission_records():
            tenant_id, workspace_id, submission_id = key
            row_key = (tenant_id, workspace_id, submission_id)
            current_submission_keys.add(row_key)
            payload_json = json.dumps(asdict(submission), sort_keys=True)
            row = existing_submissions.get(row_key)
            if row is None:
                session.add(
                    DurableSubmissionEntityRow(
                        store_id=self.store_id,
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        submission_id=submission_id,
                        payload_json=payload_json,
                    )
                )
            else:
                row.payload_json = payload_json
        for row_key, row in existing_submissions.items():
            if row_key not in current_submission_keys:
                session.delete(row)

        outbox_rows = session.exec(
            select(DurableOutboxEntityRow).where(
                DurableOutboxEntityRow.store_id == self.store_id
            )
        ).all()
        existing_outbox = {
            (row.tenant_id, row.workspace_id, row.outbox_id): row for row in outbox_rows
        }
        current_outbox_keys: set[tuple[str, str, str]] = set()
        for key, outbox in store.iter_outbox_records():
            tenant_id, workspace_id, outbox_id = key
            row_key = (tenant_id, workspace_id, outbox_id)
            current_outbox_keys.add(row_key)
            payload_json = json.dumps(asdict(outbox), sort_keys=True)
            row = existing_outbox.get(row_key)
            if row is None:
                session.add(
                    DurableOutboxEntityRow(
                        store_id=self.store_id,
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        outbox_id=outbox_id,
                        payload_json=payload_json,
                    )
                )
            else:
                row.payload_json = payload_json
        for row_key, row in existing_outbox.items():
            if row_key not in current_outbox_keys:
                session.delete(row)

    def accept(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.accept(ctx, **kwargs))

    def list_execution_scopes(
        self,
        ctx: ControlPlaneContext,
        *,
        after_submission_id: str | None = None,
        through_submission_id: str | None = None,
        limit: int = 100,
    ) -> ExecutionScopePage:
        """Read a bounded scope page from the normalized submission mirror."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        workspace_filter = (
            DurableSubmissionEntityRow.store_id == self.store_id,
            DurableSubmissionEntityRow.tenant_id == ctx.tenant.tenant_id,
            DurableSubmissionEntityRow.workspace_id == ctx.workspace.workspace_id,
        )
        with session_scope(self.engine) as session:
            high_watermark = through_submission_id
            watermark_row_id: int | None = None
            submission_table = SQLModel.metadata.tables["cp_durable_submission_entity"]
            id_column = cast(Column[int], submission_table.c["id"])
            if high_watermark is None:
                last_row = session.exec(
                    select(
                        id_column,
                        DurableSubmissionEntityRow.submission_id,
                    )
                    .where(*workspace_filter)
                    .order_by(id_column.desc())
                    .limit(1)
                ).first()
                if last_row is not None:
                    watermark_row_id, high_watermark = last_row
            else:
                watermark_row_id = session.exec(
                    select(id_column)
                    .where(
                        *workspace_filter,
                        DurableSubmissionEntityRow.submission_id == high_watermark,
                    )
                    .limit(1)
                ).first()
            stmt = select(DurableSubmissionEntityRow).where(*workspace_filter)
            if watermark_row_id is not None:
                stmt = stmt.where(id_column <= watermark_row_id)
            else:
                stmt = stmt.where(False)
            if after_submission_id is not None:
                stmt = stmt.where(
                    DurableSubmissionEntityRow.submission_id > after_submission_id
                )
            stmt = stmt.order_by(DurableSubmissionEntityRow.submission_id).limit(
                limit + 1
            )
            rows = session.exec(stmt).all()
            selected = [(row.submission_id, row.payload_json) for row in rows[:limit]]

        has_more = len(rows) > limit
        scopes: list[ControlPlaneContext] = []
        seen: set[ControlPlaneContext] = set()
        for _submission_id, payload_json in selected:
            try:
                submission = SubmissionRecord(**json.loads(payload_json))
            except (json.JSONDecodeError, TypeError, ValueError):
                # A corrupt mirror row cannot safely choose an artifact store.
                continue
            accepted_ctx = execution_context_from_submission(submission)
            if accepted_ctx is not None and accepted_ctx not in seen:
                seen.add(accepted_ctx)
                scopes.append(accepted_ctx)
        return ExecutionScopePage(
            scopes=tuple(scopes),
            next_cursor=selected[-1][0] if has_more and selected else None,
            high_watermark=high_watermark,
        )

    def pending_outbox(
        self,
        ctx: ControlPlaneContext,
        *,
        limit: int = 100,
        include_terminal: bool = False,
        terminal_only: bool = False,
        submission_id: str | None = None,
        execution_route: str | None = "local",
    ):
        return self._read_only(
            lambda m: m.pending_outbox(
                ctx,
                limit=limit,
                include_terminal=include_terminal,
                terminal_only=terminal_only,
                submission_id=submission_id,
                execution_route=execution_route,
            )
        )

    def pending_dispatches(
        self,
        ctx: ControlPlaneContext,
        *,
        execution_route: str,
        limit: int = 100,
    ):
        return self._read_only(
            lambda m: m.pending_dispatches(
                ctx, execution_route=execution_route, limit=limit
            )
        )

    def get_execution_route_state(
        self, ctx: ControlPlaneContext, execution_route: str
    ) -> ExecutionRouteRecord:
        return self._read_only(
            lambda m: m.get_execution_route_state(ctx, execution_route)
        )

    def execution_route_workload(
        self, ctx: ControlPlaneContext, execution_route: str
    ) -> ExecutionRouteWorkload:
        return self._read_only(
            lambda m: m.execution_route_workload(ctx, execution_route)
        )

    def execution_route_reference_counts(
        self, ctx: ControlPlaneContext, execution_route: str
    ) -> dict[str, int]:
        return self._read_only(
            lambda m: m.execution_route_reference_counts(ctx, execution_route)
        )

    def reserve_execution_route_reference(
        self,
        ctx: ControlPlaneContext,
        execution_route: str,
        reference_id: str,
    ) -> None:
        self._txn(
            lambda m: m.reserve_execution_route_reference(
                ctx, execution_route, reference_id
            )
        )

    def release_execution_route_reference(
        self,
        ctx: ControlPlaneContext,
        execution_route: str,
        reference_id: str,
    ) -> None:
        self._txn(
            lambda m: m.release_execution_route_reference(
                ctx, execution_route, reference_id
            )
        )

    def release_execution_route_reference_id(
        self, ctx: ControlPlaneContext, reference_id: str
    ) -> None:
        self._txn(lambda m: m.release_execution_route_reference_id(ctx, reference_id))

    def transition_execution_route_state(
        self,
        ctx: ControlPlaneContext,
        execution_route: str,
        *,
        expected_revision: int,
        status: ExecutionRouteLifecycle,
        now: datetime | None = None,
    ) -> ExecutionRouteRecord:
        return self._txn(
            lambda m: m.transition_execution_route_state(
                ctx,
                execution_route,
                expected_revision=expected_revision,
                status=status,
                now=now,
            )
        )

    def dispatched_for_reconciliation(
        self,
        ctx: ControlPlaneContext,
        *,
        execution_route: str,
        limit: int = 100,
        after_submission_id: str | None = None,
    ):
        return self._read_only(
            lambda m: m.dispatched_for_reconciliation(
                ctx,
                execution_route=execution_route,
                limit=limit,
                after_submission_id=after_submission_id,
            )
        )

    def prepare_dispatch(self, ctx: ControlPlaneContext, submission_id: str):
        return self._txn(lambda m: m.prepare_dispatch(ctx, submission_id))

    def get_dispatch(self, ctx: ControlPlaneContext, submission_id: str):
        return self._read_only(lambda m: m.get_dispatch(ctx, submission_id))

    def claim_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        lease_seconds: int = 30,
        now: datetime | None = None,
    ):
        return self._txn(
            lambda m: m.claim_dispatch(
                ctx,
                submission_id,
                owner_id=owner_id,
                lease_seconds=lease_seconds,
                now=now,
            )
        )

    def link_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        remote_run_id: str | None = None,
        prefect_flow_run_id: str | None = None,
        now: datetime | None = None,
    ):
        return self._txn(
            lambda m: m.link_dispatch(
                ctx,
                submission_id,
                owner_id=owner_id,
                fencing_token=fencing_token,
                remote_run_id=remote_run_id,
                prefect_flow_run_id=prefect_flow_run_id,
                now=now,
            )
        )

    def release_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        outcome_uncertain: bool,
        cancelled: bool = False,
        error_code: str | None = None,
        now: datetime | None = None,
    ):
        return self._txn(
            lambda m: m.release_dispatch(
                ctx,
                submission_id,
                owner_id=owner_id,
                fencing_token=fencing_token,
                outcome_uncertain=outcome_uncertain,
                cancelled=cancelled,
                error_code=error_code,
                now=now,
            )
        )

    def quarantine_expired_ecs_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_generation: int,
        expected_creation_started_at: str | None,
        safe_retry_deadline: datetime,
        owner_id: str | None = None,
        fencing_token: int | None = None,
        now: datetime | None = None,
    ):
        return self._txn(
            lambda m: m.quarantine_expired_ecs_dispatch(
                ctx,
                submission_id,
                expected_generation=expected_generation,
                expected_creation_started_at=expected_creation_started_at,
                safe_retry_deadline=safe_retry_deadline,
                owner_id=owner_id,
                fencing_token=fencing_token,
                now=now,
            )
        )

    def confirm_dispatch_cancelled(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_generation: int,
        expected_remote_run_id: str,
        now: datetime | None = None,
    ):
        return self._txn(
            lambda m: m.confirm_dispatch_cancelled(
                ctx,
                submission_id,
                expected_generation=expected_generation,
                expected_remote_run_id=expected_remote_run_id,
                now=now,
            )
        )

    def rearm_dispatch_after_remote_failure(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_remote_run_id: str | None = None,
        expected_flow_run_id: str | None = None,
        now: datetime | None = None,
    ):
        return self._txn(
            lambda m: m.rearm_dispatch_after_remote_failure(
                ctx,
                submission_id,
                expected_remote_run_id=expected_remote_run_id,
                expected_flow_run_id=expected_flow_run_id,
                now=now,
            )
        )

    def rearm_ecs_dispatch_after_remote_stop(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_generation: int,
        expected_remote_run_id: str,
        now: datetime | None = None,
    ):
        return self._txn(
            lambda m: m.rearm_ecs_dispatch_after_remote_stop(
                ctx,
                submission_id,
                expected_generation=expected_generation,
                expected_remote_run_id=expected_remote_run_id,
                now=now,
            )
        )

    def settle_terminal_ecs_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_generation: int,
        now: datetime | None = None,
    ):
        return self._txn(
            lambda m: m.settle_terminal_ecs_dispatch(
                ctx,
                submission_id,
                expected_generation=expected_generation,
                now=now,
            )
        )

    def rearm_dispatch_after_remote_missing(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_remote_run_id: str | None = None,
        expected_flow_run_id: str | None = None,
        minimum_age_seconds: int = 300,
        now: datetime | None = None,
    ):
        return self._txn(
            lambda m: m.rearm_dispatch_after_remote_missing(
                ctx,
                submission_id,
                expected_remote_run_id=expected_remote_run_id,
                expected_flow_run_id=expected_flow_run_id,
                minimum_age_seconds=minimum_age_seconds,
                now=now,
            )
        )

    def rearm_reconciliation_required_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_generation: int,
        expected_remote_run_id: str | None = None,
        expected_flow_run_id: str | None = None,
        evidence_sha256: str,
        now: datetime | None = None,
    ):
        return self._txn(
            lambda m: m.rearm_reconciliation_required_dispatch(
                ctx,
                submission_id,
                expected_generation=expected_generation,
                expected_remote_run_id=expected_remote_run_id,
                expected_flow_run_id=expected_flow_run_id,
                evidence_sha256=evidence_sha256,
                now=now,
            )
        )

    def reconcile_terminal_outbox(self, ctx: ControlPlaneContext, *, limit: int = 100):
        return self._txn(lambda m: m.reconcile_terminal_outbox(ctx, limit=limit))

    def reconcile_cancelled_submissions(
        self,
        ctx: ControlPlaneContext,
        *,
        limit: int = 100,
        acknowledge_outbox: bool = True,
        submission_id: str | None = None,
        execution_route: str | None = None,
    ):
        return self._txn(
            lambda m: m.reconcile_cancelled_submissions(
                ctx,
                limit=limit,
                acknowledge_outbox=acknowledge_outbox,
                submission_id=submission_id,
                execution_route=execution_route,
            )
        )

    def get_submission(self, ctx: ControlPlaneContext, submission_id: str):
        return self._read_only(lambda m: m.get_submission(ctx, submission_id))

    def get_submission_by_idempotency(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        operation: str = "run.submit",
    ):
        return self._read_only(
            lambda m: m.get_submission_by_idempotency(
                ctx, idempotency_key=idempotency_key, operation=operation
            )
        )

    def accept_action_job(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.accept_action_job(ctx, **kwargs))

    def get_action_job(self, ctx: ControlPlaneContext, action_id: str):
        return self._read_only(lambda m: m.get_action_job(ctx, action_id))

    def get_action_job_by_idempotency(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._read_only(lambda m: m.get_action_job_by_idempotency(ctx, **kwargs))

    def cancel_action_job(self, ctx: ControlPlaneContext, action_id: str):
        return self._txn(lambda m: m.cancel_action_job(ctx, action_id))

    def list_action_jobs(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._read_only(lambda m: m.list_action_jobs(ctx, **kwargs))

    def claim_action_job(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.claim_action_job(ctx, **kwargs))

    def heartbeat_action_job(
        self, ctx: ControlPlaneContext, action_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.heartbeat_action_job(ctx, action_id, **kwargs))

    def mark_action_job_accepting(
        self, ctx: ControlPlaneContext, action_id: str, **kwargs: Any
    ):
        return self._txn(
            lambda m: m.mark_action_job_accepting(ctx, action_id, **kwargs)
        )

    def finish_action_job(
        self, ctx: ControlPlaneContext, action_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.finish_action_job(ctx, action_id, **kwargs))

    def cleanup_expired_action_results(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.cleanup_expired_action_results(ctx, **kwargs))

    def list_attempts(self, ctx: ControlPlaneContext, submission_id: str):
        return self._read_only(lambda m: m.list_attempts(ctx, submission_id))

    def mark_published(self, ctx: ControlPlaneContext, outbox_id: str):
        return self._txn(lambda m: m.mark_published(ctx, outbox_id))

    def cancel_submission(self, ctx: ControlPlaneContext, submission_id: str):
        return self._txn(lambda m: m.cancel_submission(ctx, submission_id))

    def acquire_lease(
        self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.acquire_lease(ctx, submission_id, **kwargs))

    def heartbeat(self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any):
        return self._txn(lambda m: m.heartbeat(ctx, submission_id, **kwargs))

    def release_lease(
        self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.release_lease(ctx, submission_id, **kwargs))

    def start_attempt(
        self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.start_attempt(ctx, submission_id, **kwargs))

    def finish_attempt(self, ctx: ControlPlaneContext, attempt_id: str, **kwargs: Any):
        return self._txn(lambda m: m.finish_attempt(ctx, attempt_id, **kwargs))

    def record_result_publication(
        self, ctx: ControlPlaneContext, record: ResultPublicationRecord, **kwargs: Any
    ):
        return self._txn(lambda m: m.record_result_publication(ctx, record, **kwargs))

    def get_latest_result_publication(
        self, ctx: ControlPlaneContext, submission_id: str
    ):
        return self._read_only(
            lambda m: m.get_latest_result_publication(ctx, submission_id)
        )

    def pending_result_publications(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ):
        return self._read_only(
            lambda m: m.pending_result_publications(ctx, limit=limit)
        )

    def mark_result_publication_published(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        attempt_id: str,
        **kwargs: Any,
    ):
        return self._txn(
            lambda m: m.mark_result_publication_published(
                ctx, submission_id, attempt_id, **kwargs
            )
        )

    def compare_and_swap_checkpoint(
        self, ctx: ControlPlaneContext, checkpoint_id: str, **kwargs: Any
    ):
        return self._txn(
            lambda m: m.compare_and_swap_checkpoint(ctx, checkpoint_id, **kwargs)
        )

    def explain_transition(
        self, ctx: ControlPlaneContext, checkpoint_id: str, **kwargs: Any
    ):
        return self._read_only(
            lambda m: m.explain_transition(ctx, checkpoint_id, **kwargs)
        )

    def diagnose_checkpoint(
        self, ctx: ControlPlaneContext, checkpoint_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.diagnose_checkpoint(ctx, checkpoint_id, **kwargs))

    def acknowledge_baseline(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.acknowledge_baseline(ctx, **kwargs))

    def record_effect(self, ctx: ControlPlaneContext, effect: EffectRecord):
        return self._txn(lambda m: m.record_effect(ctx, effect))

    def record_attempt_effect(
        self, ctx: ControlPlaneContext, effect: EffectRecord, **kwargs: Any
    ):
        return self._txn(lambda m: m.record_attempt_effect(ctx, effect, **kwargs))

    def get_effect(self, ctx: ControlPlaneContext, effect_id: str):
        return self._read_only(lambda m: m.get_effect(ctx, effect_id))

    def replay(self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any):
        return self._read_only(lambda m: m.replay(ctx, submission_id, **kwargs))

    def plan_resume(self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any):
        return self._read_only(lambda m: m.plan_resume(ctx, submission_id, **kwargs))

    def plan_repair(self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any):
        return self._read_only(lambda m: m.plan_repair(ctx, submission_id, **kwargs))

    def plan_backfill(
        self, ctx: ControlPlaneContext, submission_id: str, **kwargs: Any
    ):
        return self._read_only(lambda m: m.plan_backfill(ctx, submission_id, **kwargs))

    def create_preview(self, ctx: ControlPlaneContext, preview: PreviewWorkspace):
        return self._txn(lambda m: m.create_preview(ctx, preview))

    def mark_preview_stale(
        self, ctx: ControlPlaneContext, preview_id: str, **kwargs: Any
    ):
        return self._txn(lambda m: m.mark_preview_stale(ctx, preview_id, **kwargs))

    def record_preview_diff(self, ctx: ControlPlaneContext, diff: DiffRecord):
        return self._txn(lambda m: m.record_preview_diff(ctx, diff))

    def authorize_shadow_run(self, ctx: ControlPlaneContext, shadow: ShadowRunRecord):
        return self._txn(lambda m: m.authorize_shadow_run(ctx, shadow))

    def cleanup_expired_previews(self, ctx: ControlPlaneContext):
        return self._txn(lambda m: m.cleanup_expired_previews(ctx))


__all__ = [
    "DURABLE_TABLES",
    "SQLModelDurableWorkStore",
    "create_durable_tables",
]
