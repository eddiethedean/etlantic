"""SQLModel-backed DefinitionRepository and SubmissionStore implementations."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Engine

from etlantic.control_plane import (
    AcceptReceipt,
    AcceptResult,
    ControlPlaneContext,
    ControlPlaneError,
    ControlPlaneEvent,
    redact_control_plane_payload,
)
from etlantic_sqlmodel.control_plane.models import (
    DefinitionRow,
    EventRow,
    SubmissionRow,
)
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import Session, SQLModel, select


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_control_plane_tables(engine: Engine) -> None:
    """Create CP reference tables.

    Intended for tests and local demos — not a production migration path.
    """
    SQLModel.metadata.create_all(
        engine,
        tables=[
            DefinitionRow.__table__,  # type: ignore[list-item]
            SubmissionRow.__table__,  # type: ignore[list-item]
            EventRow.__table__,  # type: ignore[list-item]
        ],
    )


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

    def accept(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        payload: Mapping[str, Any],
        resource_type: str = "run",
        resource_id: str | None = None,
        operation: str = "run.submit",
    ) -> AcceptResult:
        from sqlalchemy.exc import IntegrityError

        safe_payload = redact_control_plane_payload(deepcopy(dict(payload)))
        if not isinstance(safe_payload, dict):
            safe_payload = {}
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
                    return AcceptResult(
                        receipt=self._to_receipt(existing), created=False
                    )

                acceptance_id = f"acc-{uuid.uuid4().hex[:16]}"
                submission_id = f"sub-{uuid.uuid4().hex[:16]}"
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

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def append(
        self,
        ctx: ControlPlaneContext,
        *,
        kind: str,
        payload: Mapping[str, Any] | None = None,
    ) -> ControlPlaneEvent:
        import hashlib

        safe_payload = redact_control_plane_payload(deepcopy(dict(payload or {})))
        if not isinstance(safe_payload, dict):
            safe_payload = {}
        with session_scope(self._engine) as session:
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

    def list_after_cursor(
        self,
        ctx: ControlPlaneContext,
        cursor: str | None,
        *,
        limit: int = 100,
    ) -> Sequence[ControlPlaneEvent]:
        if limit < 1:
            return ()
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
