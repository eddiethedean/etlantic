"""SQLModel-backed DefinitionRepository and SubmissionStore implementations."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Engine

from etlantic.control_plane import (
    AcceptReceipt,
    ControlPlaneContext,
    ControlPlaneError,
)
from etlantic_sqlmodel.control_plane.models import DefinitionRow, SubmissionRow
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
                raise KeyError(definition_id)
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
    """Durable acceptance store with scoped idempotency and run observation."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lookup_idempotency(
        self,
        ctx: ControlPlaneContext,
        idempotency_key: str,
    ) -> AcceptReceipt | None:
        with session_scope(self._engine) as session:
            row = self._by_idem(session, ctx, idempotency_key)
            return None if row is None else self._to_receipt(row)

    def accept(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        payload: Mapping[str, Any],
        resource_type: str = "run",
        resource_id: str | None = None,
    ) -> AcceptReceipt:
        from sqlalchemy.exc import IntegrityError

        try:
            with session_scope(self._engine) as session:
                existing = self._by_idem(session, ctx, idempotency_key)
                if existing is not None:
                    prior = json.loads(existing.payload_json)
                    if prior != dict(payload):
                        raise ControlPlaneError.conflict(
                            "Idempotency key reuse with a different payload",
                            extensions={"idempotency_key": idempotency_key},
                        )
                    return self._to_receipt(existing)

                acceptance_id = f"acc-{uuid.uuid4().hex[:16]}"
                submission_id = f"sub-{uuid.uuid4().hex[:16]}"
                run_id = resource_id or submission_id
                created = _utcnow_iso()
                row = SubmissionRow(
                    tenant_id=ctx.tenant.tenant_id,
                    workspace_id=ctx.workspace.workspace_id,
                    idempotency_key=idempotency_key,
                    acceptance_id=acceptance_id,
                    submission_id=submission_id,
                    created_at=created,
                    status="accepted",
                    resource_type=resource_type,
                    resource_id=run_id,
                    payload_json=json.dumps(dict(payload), sort_keys=True),
                    run_status="accepted",
                    updated_at=created,
                    definition_id=(
                        str(payload["definition_id"])
                        if payload.get("definition_id") is not None
                        else None
                    ),
                )
                session.add(row)
                session.flush()
                return self._to_receipt(row)
        except IntegrityError as exc:
            with session_scope(self._engine) as session:
                winner = self._by_idem(session, ctx, idempotency_key)
                if winner is None:
                    raise ControlPlaneError.conflict(
                        "Idempotency collision without durable row",
                        extensions={"idempotency_key": idempotency_key},
                    ) from exc
                prior = json.loads(winner.payload_json)
                if prior != dict(payload):
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with a different payload",
                        extensions={"idempotency_key": idempotency_key},
                    ) from exc
                return self._to_receipt(winner)

    def get_run(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        with session_scope(self._engine) as session:
            row = self._by_run(session, ctx, run_id)
            if row is None:
                raise KeyError(run_id)
            return self._to_run(row)

    def cancel_run(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        with session_scope(self._engine) as session:
            row = self._by_run(session, ctx, run_id)
            if row is None:
                raise KeyError(run_id)
            if row.run_status in ("accepted", "cancel_requested"):
                row.run_status = "cancel_requested"
                row.updated_at = _utcnow_iso()
                session.add(row)
            return self._to_run(row)

    def poll_accepted(self, *, limit: int = 1) -> Sequence[dict[str, Any]]:
        if limit < 1:
            return ()
        with session_scope(self._engine) as session:
            statement = (
                select(SubmissionRow)
                .where(SubmissionRow.run_status == "accepted")
                .limit(limit)
            )
            rows = session.exec(statement).all()
            return [self._to_run(r) for r in rows]

    @staticmethod
    def _by_idem(
        session: Session, ctx: ControlPlaneContext, idempotency_key: str
    ) -> SubmissionRow | None:
        statement = select(SubmissionRow).where(
            SubmissionRow.tenant_id == ctx.tenant.tenant_id,
            SubmissionRow.workspace_id == ctx.workspace.workspace_id,
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


# Typing helper for hosts that inject session factories later.
SessionFactory = Callable[[], Session]


__all__ = [
    "SQLModelDefinitionRepository",
    "SQLModelSubmissionStore",
    "SessionFactory",
    "create_control_plane_tables",
]
