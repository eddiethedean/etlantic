"""In-memory hash-chained audit evidence store (CP4)."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from etlantic.control_plane.audit_models import (
    GENESIS_HASH,
    AuditExport,
    AuditRecord,
    compute_record_hash,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.redaction import redact_control_plane_payload


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.tenant.tenant_id, ctx.workspace.workspace_id


def _now() -> datetime:
    return datetime.now(UTC)


class MemoryAuditEvidenceStore:
    def __init__(self) -> None:
        self._chains: dict[tuple[str, str], list[AuditRecord]] = {}
        self._lock = threading.RLock()

    def append(
        self,
        ctx: ControlPlaneContext,
        *,
        action: str,
        resource: str,
        decision_refs: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
        record_id: str | None = None,
    ) -> AuditRecord:
        with self._lock:
            chain = self._chains.setdefault(_scope(ctx), [])
            prev_hash = chain[-1].record_hash if chain else GENESIS_HASH
            created_at = _now()
            meta = redact_control_plane_payload(dict(metadata or {}))
            if not isinstance(meta, dict):
                meta = {}
            record_hash = compute_record_hash(
                prev_hash=prev_hash,
                actor_subject=ctx.principal.subject,
                action=action,
                resource=resource,
                decision_refs=tuple(decision_refs),
                created_at=created_at,
                metadata=meta,
            )
            record = AuditRecord(
                record_id=record_id or str(uuid.uuid4()),
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                actor_subject=ctx.principal.subject,
                actor_issuer=ctx.principal.issuer,
                action=action,
                resource=resource,
                prev_hash=prev_hash,
                record_hash=record_hash,
                decision_refs=tuple(decision_refs),
                created_at=created_at,
                metadata=meta,
            )
            chain.append(record)
            return deepcopy(record)

    def list(
        self, ctx: ControlPlaneContext, *, limit: int = 100, after_id: str | None = None
    ) -> Sequence[AuditRecord]:
        with self._lock:
            chain = self._chains.get(_scope(ctx), [])
            start = 0
            if after_id is not None:
                for i, rec in enumerate(chain):
                    if rec.record_id == after_id:
                        start = i + 1
                        break
            return [deepcopy(r) for r in chain[start : start + limit]]

    def verify_chain(self, ctx: ControlPlaneContext) -> bool:
        with self._lock:
            chain = self._chains.get(_scope(ctx), [])
            prev = GENESIS_HASH
            for rec in chain:
                expected = compute_record_hash(
                    prev_hash=prev,
                    actor_subject=rec.actor_subject,
                    action=rec.action,
                    resource=rec.resource,
                    decision_refs=rec.decision_refs,
                    created_at=rec.created_at,
                    metadata=rec.metadata,
                )
                if rec.prev_hash != prev or rec.record_hash != expected:
                    return False
                prev = rec.record_hash
            return True

    def export(self, ctx: ControlPlaneContext, *, limit: int = 1000) -> AuditExport:
        with self._lock:
            chain = self._chains.get(_scope(ctx), [])[:limit]
            tip = chain[-1].record_hash if chain else GENESIS_HASH
            return AuditExport(
                export_id=str(uuid.uuid4()),
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                records=tuple(deepcopy(r) for r in chain),
                tip_hash=tip,
            )

    def restore(self, ctx: ControlPlaneContext, *, export: AuditExport) -> int:
        with self._lock:
            if (
                export.tenant_id != ctx.tenant.tenant_id
                or export.workspace_id != ctx.workspace.workspace_id
            ):
                raise ControlPlaneError.forbidden("audit export scope mismatch")
            if self._chains.get(_scope(ctx)):
                raise ControlPlaneError.conflict("cannot restore onto non-empty chain")
            records = list(export.records)
            tip = records[-1].record_hash if records else GENESIS_HASH
            if tip != export.tip_hash:
                raise ControlPlaneError.conflict("audit export tip mismatch")
            # Verify before commit.
            prev = GENESIS_HASH
            for rec in records:
                expected = compute_record_hash(
                    prev_hash=prev,
                    actor_subject=rec.actor_subject,
                    action=rec.action,
                    resource=rec.resource,
                    decision_refs=rec.decision_refs,
                    created_at=rec.created_at,
                    metadata=rec.metadata,
                )
                if rec.prev_hash != prev or rec.record_hash != expected:
                    raise ControlPlaneError.conflict("audit export chain invalid")
                prev = rec.record_hash
            self._chains[_scope(ctx)] = [deepcopy(r) for r in records]
            return len(records)

    def tamper_for_tests(self, ctx: ControlPlaneContext, *, index: int = 0) -> None:
        """Corrupt a record hash for integrity tests only."""
        with self._lock:
            chain = self._chains.get(_scope(ctx), [])
            if not chain:
                return
            from dataclasses import replace

            bad = replace(chain[index], record_hash="deadbeef" * 8)
            chain[index] = bad


__all__ = ["MemoryAuditEvidenceStore"]
