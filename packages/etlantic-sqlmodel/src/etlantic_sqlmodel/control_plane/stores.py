"""SQLModel-backed DefinitionRepository and SubmissionStore implementations."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Table, delete
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import text

from etlantic.control_plane import (
    AcceptReceipt,
    AcceptResult,
    ControlPlaneContext,
    ControlPlaneError,
    ControlPlaneEvent,
    DefinitionResolution,
    redact_control_plane_payload,
)
from etlantic.control_plane.event_retention import (
    DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS,
    MAX_EVENT_IDEMPOTENCY_PRUNE_BATCH,
    event_expiry,
    event_time,
    is_event_expired,
    normalize_event_time,
)
from etlantic_sqlmodel.control_plane.models import (
    DefinitionRow,
    EventIdempotencyRow,
    EventRow,
    SubmissionRow,
)
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import Session, SQLModel, select


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


_EVENT_APPEND_MAX_ATTEMPTS = 3
_EVENT_IDEMPOTENCY_SWEEP_BATCH_SIZE = MAX_EVENT_IDEMPOTENCY_PRUNE_BATCH
_EVENT_SEQUENCE_CONSTRAINT = "uq_cp_event_scope_seq"
_EVENT_IDEMPOTENCY_CONSTRAINT = "uq_cp_event_scope_idem"


def _event_idempotency_table() -> Table:
    return cast(Table, vars(EventIdempotencyRow)["__table__"])


def _sqlmodel_table(model: type[SQLModel]) -> Table:
    return cast(Table, vars(model)["__table__"])


def create_control_plane_tables(engine: Engine) -> None:
    """Create CP reference tables.

    Intended for tests and local demos — not a production migration path.
    """
    tables: list[Table] = [
        _sqlmodel_table(DefinitionRow),
        _sqlmodel_table(SubmissionRow),
        _sqlmodel_table(EventRow),
        _event_idempotency_table(),
    ]
    SQLModel.metadata.create_all(engine, tables=tables)


class SQLModelDefinitionRepository:
    """Workspace-scoped definition registry backed by SQLModel."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, ctx: ControlPlaneContext, definition_id: str) -> Mapping[str, Any]:
        with session_scope(self._engine) as session:
            row = self._get_row(session, ctx, definition_id)
            if row is None:
                raise ControlPlaneError.not_found(
                    f"Definition {definition_id!r} not found"
                )
            return json.loads(row.document_json)

    def resolve_revision(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        selector: str,
    ) -> DefinitionResolution:
        """Resolve the current content-addressed document in this legacy store."""
        document = self.get(ctx, definition_id)
        canonical = json.dumps(
            dict(document),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        revision_id = f"defrev-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
        if selector not in {"current", revision_id}:
            raise ControlPlaneError.not_found(
                "Definition revision was not found",
                extensions={"definition_id": definition_id},
            )
        return DefinitionResolution(revision_id=revision_id, document=document)

    def list(self, ctx: ControlPlaneContext) -> Sequence[str]:
        with session_scope(self._engine) as session:
            statement = select(DefinitionRow).where(
                DefinitionRow.tenant_id == ctx.tenant.tenant_id,
                DefinitionRow.workspace_id == ctx.workspace.workspace_id,
            )
            rows = session.exec(statement).all()
            return sorted(r.definition_id for r in rows)

    def put(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        document: Mapping[str, Any],
    ) -> None:
        with session_scope(self._engine) as session:
            row = self._get_row(session, ctx, definition_id)
            payload = json.dumps(dict(document), sort_keys=True)
            if row is None:
                session.add(
                    DefinitionRow(
                        tenant_id=ctx.tenant.tenant_id,
                        workspace_id=ctx.workspace.workspace_id,
                        definition_id=definition_id,
                        document_json=payload,
                    )
                )
            else:
                row.document_json = payload
                session.add(row)

    def compare_and_swap(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        expected_document: Mapping[str, Any],
        document: Mapping[str, Any],
    ) -> None:
        """Atomically replace the row only while its source JSON is unchanged."""
        expected = json.dumps(dict(expected_document), sort_keys=True)
        payload = json.dumps(dict(document), sort_keys=True)
        statement = text(
            "UPDATE cp_definitions SET document_json = :document_json "
            "WHERE tenant_id = :tenant_id AND workspace_id = :workspace_id "
            "AND definition_id = :definition_id AND document_json = :expected_document"
        ).bindparams(
            document_json=payload,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            definition_id=definition_id,
            expected_document=expected,
        )
        with self._engine.begin() as connection:
            result = connection.execute(statement)
            if result.rowcount != 1:
                raise ControlPlaneError.conflict(
                    "Definition changed since the edit was prepared"
                )

    @staticmethod
    def _get_row(
        session: Session, ctx: ControlPlaneContext, definition_id: str
    ) -> DefinitionRow | None:
        statement = select(DefinitionRow).where(
            DefinitionRow.tenant_id == ctx.tenant.tenant_id,
            DefinitionRow.workspace_id == ctx.workspace.workspace_id,
            DefinitionRow.definition_id == definition_id,
        )
        return session.exec(statement).first()


class SQLModelSubmissionStore:
    """Durable acceptance store with ADR-016 scoped idempotency and run observation."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lookup_idempotency(
        self,
        ctx: ControlPlaneContext,
        idempotency_key: str,
        *,
        operation: str = "run.submit",
    ) -> AcceptReceipt | None:
        with session_scope(self._engine) as session:
            row = self._by_idem(session, ctx, idempotency_key, operation=operation)
            return None if row is None else self._to_receipt(row)

    def lookup_idempotency_payload(
        self,
        ctx: ControlPlaneContext,
        idempotency_key: str,
        *,
        operation: str = "run.submit",
    ) -> Mapping[str, Any] | None:
        with session_scope(self._engine) as session:
            row = self._by_idem(session, ctx, idempotency_key, operation=operation)
            return None if row is None else json.loads(row.payload_json)

    def accept(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        payload: Mapping[str, Any],
        resource_type: str = "run",
        resource_id: str | None = None,
        submission_id: str | None = None,
        operation: str = "run.submit",
    ) -> AcceptResult:
        from sqlalchemy.exc import IntegrityError

        safe_payload = redact_control_plane_payload(deepcopy(dict(payload)))
        if not isinstance(safe_payload, dict):
            safe_payload = {}
        requested_submission_id = submission_id
        try:
            with session_scope(self._engine) as session:
                existing = self._by_idem(
                    session, ctx, idempotency_key, operation=operation
                )
                if existing is not None:
                    prior = json.loads(existing.payload_json)
                    if prior != safe_payload:
                        raise ControlPlaneError.conflict(
                            "Idempotency key reuse with a different payload",
                            extensions={"idempotency_key": idempotency_key},
                        )
                    if (
                        submission_id is not None
                        and existing.submission_id != submission_id
                    ):
                        raise ControlPlaneError.conflict(
                            "Idempotency key is bound to a different submission"
                        )
                    return AcceptResult(
                        receipt=self._to_receipt(existing), created=False
                    )

                acceptance_id = f"acc-{uuid.uuid4().hex[:16]}"
                submission_id = submission_id or f"sub-{uuid.uuid4().hex[:16]}"
                run_id = resource_id or submission_id
                created = _utcnow_iso()
                row = SubmissionRow(
                    tenant_id=ctx.tenant.tenant_id,
                    workspace_id=ctx.workspace.workspace_id,
                    principal_subject=ctx.principal.subject,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    acceptance_id=acceptance_id,
                    submission_id=submission_id,
                    created_at=created,
                    status="accepted",
                    resource_type=resource_type,
                    resource_id=run_id,
                    payload_json=json.dumps(safe_payload, sort_keys=True),
                    run_status="accepted",
                    updated_at=created,
                    definition_id=(
                        str(safe_payload["definition_id"])
                        if safe_payload.get("definition_id") is not None
                        else None
                    ),
                )
                session.add(row)
                session.flush()
                return AcceptResult(receipt=self._to_receipt(row), created=True)
        except IntegrityError as exc:
            with session_scope(self._engine) as session:
                winner = self._by_idem(
                    session, ctx, idempotency_key, operation=operation
                )
                if winner is None:
                    raise ControlPlaneError.conflict(
                        "Idempotency collision without durable row",
                        extensions={"idempotency_key": idempotency_key},
                    ) from exc
                prior = json.loads(winner.payload_json)
                if prior != safe_payload:
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with a different payload",
                        extensions={"idempotency_key": idempotency_key},
                    ) from exc
                if (
                    requested_submission_id is not None
                    and winner.submission_id != requested_submission_id
                ):
                    raise ControlPlaneError.conflict(
                        "Idempotency key is bound to a different submission"
                    ) from exc
                return AcceptResult(receipt=self._to_receipt(winner), created=False)

    def get_run(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        with session_scope(self._engine) as session:
            row = self._by_run(session, ctx, run_id)
            if row is None:
                raise KeyError(run_id)
            return self._to_run(row)

    def cancel_run(
        self, ctx: ControlPlaneContext, run_id: str
    ) -> tuple[dict[str, Any], bool]:
        with session_scope(self._engine) as session:
            row = self._by_run(session, ctx, run_id)
            if row is None:
                raise KeyError(run_id)
            changed = False
            if row.run_status == "accepted":
                row.run_status = "cancel_requested"
                row.updated_at = _utcnow_iso()
                session.add(row)
                changed = True
            return self._to_run(row), changed

    def poll_accepted(
        self, ctx: ControlPlaneContext, *, limit: int = 1
    ) -> Sequence[dict[str, Any]]:
        if limit < 1:
            return ()
        with session_scope(self._engine) as session:
            statement = (
                select(SubmissionRow)
                .where(
                    SubmissionRow.run_status == "accepted",
                    SubmissionRow.tenant_id == ctx.tenant.tenant_id,
                    SubmissionRow.workspace_id == ctx.workspace.workspace_id,
                )
                .limit(limit)
            )
            rows = session.exec(statement).all()
            return [self._to_run(r) for r in rows]

    @staticmethod
    def _by_idem(
        session: Session,
        ctx: ControlPlaneContext,
        idempotency_key: str,
        *,
        operation: str,
    ) -> SubmissionRow | None:
        statement = select(SubmissionRow).where(
            SubmissionRow.tenant_id == ctx.tenant.tenant_id,
            SubmissionRow.workspace_id == ctx.workspace.workspace_id,
            SubmissionRow.principal_subject == ctx.principal.subject,
            SubmissionRow.operation == operation,
            SubmissionRow.idempotency_key == idempotency_key,
        )
        return session.exec(statement).first()

    @staticmethod
    def _by_run(
        session: Session, ctx: ControlPlaneContext, run_id: str
    ) -> SubmissionRow | None:
        from sqlalchemy import or_

        statement = select(SubmissionRow).where(
            SubmissionRow.tenant_id == ctx.tenant.tenant_id,
            SubmissionRow.workspace_id == ctx.workspace.workspace_id,
            or_(
                SubmissionRow.resource_id == run_id,
                SubmissionRow.submission_id == run_id,
            ),
        )
        return session.exec(statement).first()

    @staticmethod
    def _to_receipt(row: SubmissionRow) -> AcceptReceipt:
        return AcceptReceipt(
            acceptance_id=row.acceptance_id,
            submission_id=row.submission_id,
            tenant_id=row.tenant_id,
            workspace_id=row.workspace_id,
            idempotency_key=row.idempotency_key,
            created_at=row.created_at,
            status="accepted",  # type: ignore[arg-type]
            resource_type=row.resource_type,
            resource_id=row.resource_id,
        )

    @staticmethod
    def _to_run(row: SubmissionRow) -> dict[str, Any]:
        return {
            "run_id": row.resource_id or row.submission_id,
            "submission_id": row.submission_id,
            "acceptance_id": row.acceptance_id,
            "status": row.run_status,
            "tenant_id": row.tenant_id,
            "workspace_id": row.workspace_id,
            "definition_id": row.definition_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at or row.created_at,
            "idempotency_key": row.idempotency_key,
            "resource_type": row.resource_type,
        }


class SqlModelEventStore:
    """Minimal SQLModel-backed EventStore with tenant/workspace isolation."""

    def __init__(
        self,
        engine: Engine,
        *,
        max_events_per_scope: int | None = None,
        idempotency_retention_seconds: int = DEFAULT_EVENT_IDEMPOTENCY_RETENTION_SECONDS,
    ) -> None:
        if max_events_per_scope is not None and (
            type(max_events_per_scope) is not int or max_events_per_scope < 1
        ):
            raise ValueError("max_events_per_scope must be a positive integer or None")
        if (
            type(idempotency_retention_seconds) is not int
            or idempotency_retention_seconds < 1
        ):
            raise ValueError(
                "idempotency_retention_seconds must be a positive integer or None"
            )
        self._engine = engine
        self.max_events_per_scope = max_events_per_scope
        self.idempotency_retention_seconds = idempotency_retention_seconds

    def append(
        self,
        ctx: ControlPlaneContext,
        *,
        kind: str,
        payload: Mapping[str, Any] | None = None,
    ) -> ControlPlaneEvent:
        return self._append(
            ctx,
            event_key=None,
            kind=kind,
            payload=payload,
        )

    def append_once(
        self,
        ctx: ControlPlaneContext,
        *,
        event_key: str,
        kind: str,
        payload: Mapping[str, Any] | None = None,
    ) -> ControlPlaneEvent:
        """Append once per trusted scope and key, including across restarts."""
        if not event_key.strip():
            raise ValueError("event_key must not be empty")
        return self._append(ctx, event_key=event_key, kind=kind, payload=payload)

    def _append(
        self,
        ctx: ControlPlaneContext,
        *,
        event_key: str | None,
        kind: str,
        payload: Mapping[str, Any] | None,
    ) -> ControlPlaneEvent:
        redacted_payload = redact_control_plane_payload(deepcopy(dict(payload or {})))
        safe_payload = (
            cast(dict[str, Any], redacted_payload)
            if isinstance(redacted_payload, dict)
            else {}
        )
        safe_key = (
            None
            if event_key is None
            else hashlib.sha256(event_key.encode("utf-8")).hexdigest()
        )
        for attempt in range(1, _EVENT_APPEND_MAX_ATTEMPTS + 1):
            try:
                return self._append_once(
                    ctx,
                    kind=kind,
                    safe_payload=safe_payload,
                    event_key=safe_key,
                )
            except IntegrityError as exc:
                if self._is_idempotency_conflict(exc) and safe_key is not None:
                    existing = self._get_event_by_key(ctx, safe_key)
                    if existing is not None:
                        if (
                            existing.kind != kind
                            or dict(existing.payload or {}) != safe_payload
                        ):
                            raise ControlPlaneError.conflict(
                                "Event idempotency key was reused with different content",
                                extensions={"operation": "event.append_once"},
                            ) from exc
                        return existing
                elif not self._is_sequence_conflict(exc):
                    raise
                if attempt == _EVENT_APPEND_MAX_ATTEMPTS:
                    raise ControlPlaneError.conflict(
                        "Concurrent event append could not allocate a sequence; retry the append",
                        extensions={
                            "operation": "event.append",
                            "retryable": True,
                        },
                    ) from exc

        raise AssertionError("event append retry loop did not return")

    @staticmethod
    def _is_sequence_conflict(exc: IntegrityError) -> bool:
        diagnostic = getattr(exc.orig, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        if constraint_name is not None:
            return constraint_name == _EVENT_SEQUENCE_CONSTRAINT
        return _EVENT_SEQUENCE_CONSTRAINT in str(exc.orig)

    @staticmethod
    def _is_idempotency_conflict(exc: IntegrityError) -> bool:
        diagnostic = getattr(exc.orig, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        if constraint_name is not None:
            return constraint_name == _EVENT_IDEMPOTENCY_CONSTRAINT
        detail = str(exc.orig)
        return _EVENT_IDEMPOTENCY_CONSTRAINT in detail or (
            "cp_event_idempotency.tenant_id, "
            "cp_event_idempotency.workspace_id, "
            "cp_event_idempotency.event_key" in detail
        )

    def _append_once(
        self,
        ctx: ControlPlaneContext,
        *,
        kind: str,
        safe_payload: dict[str, Any],
        event_key: str | None,
    ) -> ControlPlaneEvent:
        with session_scope(self._engine) as session:
            self._lock_append_scope(session, ctx)
            now = normalize_event_time()
            self._prune_expired_idempotency(
                session,
                ctx,
                now=now,
                limit=_EVENT_IDEMPOTENCY_SWEEP_BATCH_SIZE,
            )
            if event_key is not None:
                existing = session.exec(
                    select(EventIdempotencyRow).where(
                        EventIdempotencyRow.tenant_id == ctx.tenant.tenant_id,
                        EventIdempotencyRow.workspace_id == ctx.workspace.workspace_id,
                        EventIdempotencyRow.event_key == event_key,
                    )
                ).first()
                if existing is not None and is_event_expired(
                    existing.expires_at, now=now
                ):
                    session.delete(existing)
                    session.flush()
                    existing = None
                if existing is not None:
                    event_row = session.exec(
                        select(EventRow).where(
                            EventRow.tenant_id == ctx.tenant.tenant_id,
                            EventRow.workspace_id == ctx.workspace.workspace_id,
                            EventRow.event_id == existing.event_id,
                        )
                    ).first()
                    if event_row is None:
                        payload_digest = hashlib.sha256(
                            json.dumps(safe_payload, sort_keys=True).encode("utf-8")
                        ).hexdigest()
                        if (
                            existing.event_kind != kind
                            or existing.payload_sha256 != payload_digest
                        ):
                            raise ControlPlaneError.conflict(
                                "Event idempotency key was reused with different content",
                                extensions={"operation": "event.append_once"},
                            )
                        raise ControlPlaneError.gone(
                            "Previously delivered event is outside retained history",
                            extensions={
                                "hint": "event_expired",
                                "operation": "event.append_once",
                            },
                        )
                    event = self._to_event(event_row)
                    if event.kind != kind or dict(event.payload or {}) != safe_payload:
                        raise ControlPlaneError.conflict(
                            "Event idempotency key was reused with different content",
                            extensions={"operation": "event.append_once"},
                        )
                    return event
            statement = (
                select(EventRow)
                .where(
                    EventRow.tenant_id == ctx.tenant.tenant_id,
                    EventRow.workspace_id == ctx.workspace.workspace_id,
                )
                .order_by(EventRow.sequence.desc())  # type: ignore[union-attr]
                .limit(1)
            )
            last = session.exec(statement).first()
            sequence = 1 if last is None else int(last.sequence) + 1
            cursor = hashlib.sha256(
                f"{ctx.tenant.tenant_id}:{ctx.workspace.workspace_id}:{sequence}".encode()
            ).hexdigest()[:24]
            event_id = f"evt-{uuid.uuid4().hex[:16]}"
            created = _utcnow_iso()
            correlation_id = (
                ctx.correlation_key.value if ctx.correlation_key is not None else None
            )
            row = EventRow(
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                event_id=event_id,
                sequence=sequence,
                cursor=cursor,
                kind=kind,
                created_at=created,
                payload_json=json.dumps(safe_payload, sort_keys=True),
                correlation_id=correlation_id,
            )
            session.add(row)
            session.flush()
            if event_key is not None:
                session.add(
                    EventIdempotencyRow(
                        tenant_id=ctx.tenant.tenant_id,
                        workspace_id=ctx.workspace.workspace_id,
                        event_key=event_key,
                        event_id=event_id,
                        event_kind=kind,
                        payload_sha256=hashlib.sha256(
                            json.dumps(safe_payload, sort_keys=True).encode("utf-8")
                        ).hexdigest(),
                        sequence=sequence,
                        cursor=cursor,
                        expires_at=event_expiry(
                            event_time(created) or now,
                            self.idempotency_retention_seconds,
                        ),
                    )
                )
                session.flush()
            self._enforce_retention(session, ctx, high_water_sequence=sequence)
            return ControlPlaneEvent(
                event_id=event_id,
                sequence=sequence,
                cursor=cursor,
                kind=kind,
                created_at=created,
                payload=safe_payload,
                correlation_id=correlation_id,
                scope={
                    "tenant_id": ctx.tenant.tenant_id,
                    "workspace_id": ctx.workspace.workspace_id,
                },
            )

    def prune_before_sequence(
        self, ctx: ControlPlaneContext, before_sequence: int
    ) -> int:
        """Delete older scoped events while preserving the sequence high-water."""
        if before_sequence < 1:
            raise ValueError("before_sequence must be at least 1")
        with session_scope(self._engine) as session:
            self._lock_append_scope(session, ctx)
            latest_sequence = session.exec(
                select(EventRow.sequence)
                .where(
                    EventRow.tenant_id == ctx.tenant.tenant_id,
                    EventRow.workspace_id == ctx.workspace.workspace_id,
                )
                .order_by(text("sequence DESC"))
                .limit(1)
            ).first()
            if latest_sequence is None:
                return 0
            cutoff = min(before_sequence, int(latest_sequence))
            result = session.exec(
                delete(EventRow).where(
                    EventRow.tenant_id == ctx.tenant.tenant_id,
                    EventRow.workspace_id == ctx.workspace.workspace_id,
                    EventRow.sequence < cutoff,
                )
            )
            return int(result.rowcount or 0)

    def prune_expired_idempotency(
        self,
        ctx: ControlPlaneContext,
        *,
        limit: int = _EVENT_IDEMPOTENCY_SWEEP_BATCH_SIZE,
        now: datetime | None = None,
    ) -> int:
        """Delete a bounded number of expired scoped event-key tombstones."""
        if (
            type(limit) is not int
            or not 1 <= limit <= MAX_EVENT_IDEMPOTENCY_PRUNE_BATCH
        ):
            raise ValueError(
                f"limit must be between 1 and {MAX_EVENT_IDEMPOTENCY_PRUNE_BATCH}"
            )
        current = normalize_event_time(now)
        with session_scope(self._engine) as session:
            self._lock_append_scope(session, ctx)
            return self._prune_expired_idempotency(
                session, ctx, now=current, limit=limit
            )

    @staticmethod
    def _prune_expired_idempotency(
        session: Session,
        ctx: ControlPlaneContext,
        *,
        now: datetime,
        limit: int,
    ) -> int:
        """Delete expired tombstones in the caller's transaction."""
        boundary = now.isoformat(timespec="microseconds").replace("+00:00", "Z")
        expired = session.exec(
            select(EventIdempotencyRow)
            .where(
                EventIdempotencyRow.tenant_id == ctx.tenant.tenant_id,
                EventIdempotencyRow.workspace_id == ctx.workspace.workspace_id,
                EventIdempotencyRow.expires_at.is_not(None),
                EventIdempotencyRow.expires_at <= boundary,
            )
            .order_by(text("expires_at ASC"))
            .limit(limit)
        ).all()
        for row in expired:
            session.delete(row)
        return len(expired)

    def _get_event_by_key(
        self, ctx: ControlPlaneContext, event_key: str
    ) -> ControlPlaneEvent | None:
        with session_scope(self._engine) as session:
            mapping = session.exec(
                select(EventIdempotencyRow).where(
                    EventIdempotencyRow.tenant_id == ctx.tenant.tenant_id,
                    EventIdempotencyRow.workspace_id == ctx.workspace.workspace_id,
                    EventIdempotencyRow.event_key == event_key,
                )
            ).first()
            if mapping is None:
                return None
            if is_event_expired(mapping.expires_at):
                return None
            row = session.exec(
                select(EventRow).where(
                    EventRow.tenant_id == ctx.tenant.tenant_id,
                    EventRow.workspace_id == ctx.workspace.workspace_id,
                    EventRow.event_id == mapping.event_id,
                )
            ).first()
            return None if row is None else self._to_event(row)

    def _lock_append_scope(self, session: Session, ctx: ControlPlaneContext) -> None:
        """Serialize sequence allocation for this scope on PostgreSQL.

        The unique constraint remains the final safety net for writers that do
        not yet use this allocator. Those collisions are retried by ``append``
        and become a transport-neutral control-plane conflict if exhausted.
        """
        if self._engine.dialect.name != "postgresql":
            return
        session.execute(
            text(
                "SELECT pg_advisory_xact_lock("
                "hashtext(:tenant_id), hashtext(:workspace_id))"
            ),
            {
                "tenant_id": ctx.tenant.tenant_id,
                "workspace_id": ctx.workspace.workspace_id,
            },
        )

    def list_after_cursor(
        self,
        ctx: ControlPlaneContext,
        cursor: str | None,
        *,
        limit: int = 100,
    ) -> Sequence[ControlPlaneEvent]:
        if limit < 1:
            return ()
        self.prune_expired_idempotency(ctx)
        self._enforce_scope_retention(ctx)
        with session_scope(self._engine) as session:
            start_seq = 0
            if cursor is not None:
                found = session.exec(
                    select(EventRow).where(
                        EventRow.tenant_id == ctx.tenant.tenant_id,
                        EventRow.workspace_id == ctx.workspace.workspace_id,
                        EventRow.cursor == cursor,
                    )
                ).first()
                if found is None:
                    raise ControlPlaneError.gone(
                        "SSE cursor expired or unknown; reconnect without "
                        "cursor (or Last-Event-ID) to replay from the beginning",
                        extensions={
                            "hint": "omit_cursor_or_last_event_id",
                            "schema": "etlantic.control_plane.sse_cursor/1",
                        },
                    )
                start_seq = int(found.sequence)
            statement = (
                select(EventRow)
                .where(
                    EventRow.tenant_id == ctx.tenant.tenant_id,
                    EventRow.workspace_id == ctx.workspace.workspace_id,
                    EventRow.sequence > start_seq,
                )
                .order_by(EventRow.sequence)  # type: ignore[arg-type]
                .limit(limit)
            )
            rows = session.exec(statement).all()
            return [self._to_event(r) for r in rows]

    def _enforce_scope_retention(self, ctx: ControlPlaneContext) -> None:
        if self.max_events_per_scope is None:
            return
        with session_scope(self._engine) as session:
            self._lock_append_scope(session, ctx)
            latest_sequence = session.exec(
                select(EventRow.sequence)
                .where(
                    EventRow.tenant_id == ctx.tenant.tenant_id,
                    EventRow.workspace_id == ctx.workspace.workspace_id,
                )
                .order_by(text("sequence DESC"))
                .limit(1)
            ).first()
            if latest_sequence is not None:
                self._enforce_retention(
                    session, ctx, high_water_sequence=int(latest_sequence)
                )

    def _enforce_retention(
        self, session: Session, ctx: ControlPlaneContext, *, high_water_sequence: int
    ) -> None:
        """Keep only the configured newest event window inside this scope."""
        if self.max_events_per_scope is None:
            return
        first_retained = high_water_sequence - self.max_events_per_scope + 1
        if first_retained <= 1:
            return
        session.exec(
            delete(EventRow).where(
                EventRow.tenant_id == ctx.tenant.tenant_id,
                EventRow.workspace_id == ctx.workspace.workspace_id,
                EventRow.sequence < first_retained,
            )
        )

    @staticmethod
    def _to_event(row: EventRow) -> ControlPlaneEvent:
        return ControlPlaneEvent(
            event_id=row.event_id,
            sequence=int(row.sequence),
            cursor=row.cursor,
            kind=row.kind,
            created_at=row.created_at,
            payload=json.loads(row.payload_json),
            correlation_id=row.correlation_id,
            scope={
                "tenant_id": row.tenant_id,
                "workspace_id": row.workspace_id,
            },
        )


# Typing helper for hosts that inject session factories later.
SessionFactory = Callable[[], Session]


__all__ = [
    "SQLModelDefinitionRepository",
    "SQLModelSubmissionStore",
    "SessionFactory",
    "SqlModelEventStore",
    "create_control_plane_tables",
]
