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
from collections.abc import Callable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, TypeVar, cast

from sqlalchemy import text
from sqlalchemy.engine import Engine

from etlantic.control_plane.durable_memory import MemoryDurableWorkStore
from etlantic.control_plane.durable_models import (
    ActionJobRecord,
    AttemptRecord,
    BaselineAcknowledgement,
    CheckpointRecord,
    DiffRecord,
    EffectRecord,
    ExecutionScopePage,
    LeaseRecord,
    OutboxRecord,
    PreviewWorkspace,
    ResultPublicationRecord,
    ShadowRunRecord,
    StateDiagnostic,
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

DURABLE_TABLES = (
    DurableSnapshotRow,
    DurableSubmissionEntityRow,
    DurableOutboxEntityRow,
)


def create_durable_tables(engine: Engine) -> None:
    """Create CP3 durable tables (tests/demos only)."""
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in DURABLE_TABLES],  # type: ignore[list-item]
    )


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _encode_key(parts: tuple[str, ...]) -> str:
    return json.dumps(list(parts), separators=(",", ":"))


def _decode_key(text: str) -> tuple[str, ...]:
    raw = json.loads(text)
    if not isinstance(raw, list) or not all(isinstance(p, str) for p in raw):
        raise ValueError("durable snapshot key must be a JSON string array")
    return tuple(raw)


def _dump_store(store: MemoryDurableWorkStore) -> dict[str, Any]:
    return {
        "admission_limit": store.admission_limit,
        "submissions": {
            _encode_key(k): asdict(v) for k, v in store._submissions.items()
        },
        "action_jobs": {
            _encode_key(k): asdict(v) for k, v in store._action_jobs.items()
        },
        "action_idempotency": {
            _encode_key(k): v for k, v in store._action_idempotency.items()
        },
        "idempotency": {_encode_key(k): v for k, v in store._idempotency.items()},
        "outbox": {_encode_key(k): asdict(v) for k, v in store._outbox.items()},
        "leases": {_encode_key(k): asdict(v) for k, v in store._leases.items()},
        "attempts": {_encode_key(k): asdict(v) for k, v in store._attempts.items()},
        "result_publications": {
            _encode_key(k): asdict(v) for k, v in store._result_publications.items()
        },
        "checkpoints": {
            _encode_key(k): asdict(v) for k, v in store._checkpoints.items()
        },
        "effects": {_encode_key(k): asdict(v) for k, v in store._effects.items()},
        "previews": {_encode_key(k): asdict(v) for k, v in store._previews.items()},
        "diffs": {_encode_key(k): asdict(v) for k, v in store._diffs.items()},
        "shadows": {_encode_key(k): asdict(v) for k, v in store._shadows.items()},
        "baselines": {_encode_key(k): asdict(v) for k, v in store._baselines.items()},
        "diagnostics": [asdict(d) for d in store._diagnostics],
    }


def _load_store(payload: Mapping[str, Any]) -> MemoryDurableWorkStore:
    store = MemoryDurableWorkStore(admission_limit=payload.get("admission_limit"))
    store._submissions = {
        _decode_key(k): SubmissionRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("submissions") or {}).items()
    }
    store._action_jobs = {
        _decode_key(k): ActionJobRecord(**cast(dict[str, Any], v))
        for k, v in dict(payload.get("action_jobs") or {}).items()
    }
    store._action_idempotency = {
        _decode_key(k): v
        for k, v in dict(payload.get("action_idempotency") or {}).items()
    }
    store._idempotency = {
        _decode_key(k): v for k, v in dict(payload.get("idempotency") or {}).items()
    }
    store._outbox = {
        _decode_key(k): OutboxRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("outbox") or {}).items()
    }
    store._leases = {
        _decode_key(k): LeaseRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("leases") or {}).items()
    }
    store._attempts = {
        _decode_key(k): AttemptRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("attempts") or {}).items()
    }
    store._result_publications = {
        _decode_key(k): ResultPublicationRecord(**cast(Any, v))
        for k, v in dict(payload.get("result_publications") or {}).items()
    }
    store._checkpoints = {
        _decode_key(k): CheckpointRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("checkpoints") or {}).items()
    }
    store._effects = {
        _decode_key(k): EffectRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("effects") or {}).items()
    }
    store._previews = {
        _decode_key(k): PreviewWorkspace(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("previews") or {}).items()
    }
    store._diffs = {
        _decode_key(k): DiffRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("diffs") or {}).items()
    }
    store._shadows = {
        _decode_key(k): ShadowRunRecord(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("shadows") or {}).items()
    }
    store._baselines = {
        _decode_key(k): BaselineAcknowledgement(**v)  # type: ignore[arg-type]
        for k, v in dict(payload.get("baselines") or {}).items()
    }
    store._diagnostics = [
        StateDiagnostic(**d)  # type: ignore[arg-type]
        for d in list(payload.get("diagnostics") or [])
    ]
    return store


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
        with session_scope(self.engine) as session:
            self._lock_store(session)
            mem, version = self._read(session, for_update=True)
            if self.admission_limit is not None:
                mem.admission_limit = self.admission_limit
            result = fn(mem)
            self._write(session, mem, expected_version=version)
            return result

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
        session.execute(
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
        return _load_store(json.loads(row.payload_json or "{}")), int(
            row.payload_version or 0
        )

    def _write(
        self,
        session: Session,
        store: MemoryDurableWorkStore,
        *,
        expected_version: int,
    ) -> None:
        payload = json.dumps(_dump_store(store), sort_keys=True)
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
        for key, submission in store._submissions.items():
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
        for key, outbox in store._outbox.items():
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
            if high_watermark is None:
                last_row = session.exec(
                    select(
                        DurableSubmissionEntityRow.id,
                        DurableSubmissionEntityRow.submission_id,
                    )
                    .where(*workspace_filter)
                    .order_by(DurableSubmissionEntityRow.id.desc())
                    .limit(1)
                ).first()
                if last_row is not None:
                    watermark_row_id, high_watermark = last_row
            elif high_watermark is not None:
                watermark_row_id = session.exec(
                    select(DurableSubmissionEntityRow.id)
                    .where(
                        *workspace_filter,
                        DurableSubmissionEntityRow.submission_id == high_watermark,
                    )
                    .limit(1)
                ).first()
            stmt = select(DurableSubmissionEntityRow).where(*workspace_filter)
            if watermark_row_id is not None:
                stmt = stmt.where(DurableSubmissionEntityRow.id <= watermark_row_id)
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

    def pending_outbox(self, ctx: ControlPlaneContext, *, limit: int = 100):
        return self._read_only(lambda m: m.pending_outbox(ctx, limit=limit))

    def reconcile_terminal_outbox(self, ctx: ControlPlaneContext, *, limit: int = 100):
        return self._txn(lambda m: m.reconcile_terminal_outbox(ctx, limit=limit))

    def reconcile_cancelled_submissions(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ):
        return self._txn(lambda m: m.reconcile_cancelled_submissions(ctx, limit=limit))

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
