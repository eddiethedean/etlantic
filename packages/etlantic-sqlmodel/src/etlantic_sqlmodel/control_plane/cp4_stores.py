"""SQLModel-backed CP4 governance stores (audit reference provider)."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy.engine import Engine

from etlantic.control_plane.audit_memory import MemoryAuditEvidenceStore
from etlantic.control_plane.audit_models import AuditExport, AuditRecord
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic_sqlmodel.control_plane.models import Cp4GovernanceSnapshotRow
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import Session, SQLModel, select

T = TypeVar("T")

CP4_TABLES = (Cp4GovernanceSnapshotRow,)


def create_cp4_tables(engine: Engine) -> None:
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in CP4_TABLES],  # type: ignore[list-item]
    )


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _dump_audit(store: MemoryAuditEvidenceStore) -> dict[str, Any]:
    return {
        "chains": {
            f"{t}|{w}": [r.to_dict() for r in records]
            for (t, w), records in store._chains.items()
        }
    }


def _load_audit(payload: Mapping[str, Any]) -> MemoryAuditEvidenceStore:
    store = MemoryAuditEvidenceStore()
    for key, records in dict(payload.get("chains") or {}).items():
        tenant_id, workspace_id = str(key).split("|", 1)
        loaded: list[AuditRecord] = []
        for item in records:
            created = item.get("created_at")
            if isinstance(created, str):
                created_at = datetime.fromisoformat(created)
            else:
                created_at = datetime.now(UTC)
            loaded.append(
                AuditRecord(
                    record_id=str(item["record_id"]),
                    tenant_id=str(item["tenant_id"]),
                    workspace_id=str(item["workspace_id"]),
                    actor_subject=str(item["actor_subject"]),
                    actor_issuer=item.get("actor_issuer"),
                    action=str(item["action"]),
                    resource=str(item["resource"]),
                    prev_hash=str(item["prev_hash"]),
                    record_hash=str(item["record_hash"]),
                    decision_refs=tuple(item.get("decision_refs") or ()),
                    created_at=created_at,
                    metadata=dict(item.get("metadata") or {}),
                )
            )
        store._chains[(tenant_id, workspace_id)] = loaded
    return store


class SQLModelAuditEvidenceStore:
    """Transactional AuditEvidenceStore backed by a CP4 snapshot row."""

    def __init__(self, engine: Engine, *, store_id: str = "default") -> None:
        self.engine = engine
        self.store_id = store_id
        self.kind = "audit"

    def _txn(self, fn: Callable[[MemoryAuditEvidenceStore], T]) -> T:
        with session_scope(self.engine) as session:
            mem, version = self._read(session)
            result = fn(mem)
            self._write(session, mem, expected_version=version)
            return result

    def _read(self, session: Session) -> tuple[MemoryAuditEvidenceStore, int]:
        row = session.exec(
            select(Cp4GovernanceSnapshotRow)
            .where(Cp4GovernanceSnapshotRow.store_id == self.store_id)
            .where(Cp4GovernanceSnapshotRow.kind == self.kind)
            .with_for_update()
        ).first()
        if row is None:
            return MemoryAuditEvidenceStore(), 0
        return _load_audit(json.loads(row.payload_json or "{}")), int(
            row.payload_version or 0
        )

    def _write(
        self,
        session: Session,
        store: MemoryAuditEvidenceStore,
        *,
        expected_version: int,
    ) -> None:
        payload = json.dumps(_dump_audit(store), sort_keys=True)
        row = session.exec(
            select(Cp4GovernanceSnapshotRow)
            .where(Cp4GovernanceSnapshotRow.store_id == self.store_id)
            .where(Cp4GovernanceSnapshotRow.kind == self.kind)
            .with_for_update()
        ).first()
        if row is None:
            if expected_version != 0:
                raise ControlPlaneError.conflict("CP4 audit snapshot conflict")
            session.add(
                Cp4GovernanceSnapshotRow(
                    store_id=self.store_id,
                    kind=self.kind,
                    payload_json=payload,
                    payload_version=1,
                    updated_at=_utcnow_iso(),
                )
            )
            return
        if int(row.payload_version or 0) != expected_version:
            raise ControlPlaneError.conflict("CP4 audit snapshot conflict")
        row.payload_json = payload
        row.payload_version = expected_version + 1
        row.updated_at = _utcnow_iso()
        session.add(row)

    def append(self, ctx: ControlPlaneContext, **kwargs: Any) -> AuditRecord:
        return self._txn(lambda m: m.append(ctx, **kwargs))

    def list(
        self, ctx: ControlPlaneContext, *, limit: int = 100, after_id: str | None = None
    ) -> Sequence[AuditRecord]:
        return self._txn(lambda m: m.list(ctx, limit=limit, after_id=after_id))

    def verify_chain(self, ctx: ControlPlaneContext) -> bool:
        return self._txn(lambda m: m.verify_chain(ctx))

    def export(self, ctx: ControlPlaneContext, *, limit: int = 1000) -> AuditExport:
        return self._txn(lambda m: m.export(ctx, limit=limit))

    def restore(self, ctx: ControlPlaneContext, *, export: AuditExport) -> int:
        return self._txn(lambda m: m.restore(ctx, export=export))


__all__ = [
    "CP4_TABLES",
    "SQLModelAuditEvidenceStore",
    "create_cp4_tables",
]
