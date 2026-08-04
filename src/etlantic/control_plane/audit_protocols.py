"""Audit evidence store protocol (CP4)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from etlantic.control_plane.audit_models import AuditExport, AuditRecord
from etlantic.control_plane.models import ControlPlaneContext


@runtime_checkable
class AuditEvidenceStore(Protocol):
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
        """Append a hash-chained audit record (redacted metadata only)."""

    def list(
        self, ctx: ControlPlaneContext, *, limit: int = 100, after_id: str | None = None
    ) -> Sequence[AuditRecord]:
        ...

    def verify_chain(self, ctx: ControlPlaneContext) -> bool:
        """Return True when the scoped chain hashes are intact."""

    def export(
        self, ctx: ControlPlaneContext, *, limit: int = 1000
    ) -> AuditExport:
        ...

    def restore(self, ctx: ControlPlaneContext, *, export: AuditExport) -> int:
        """Restore an export into an empty scoped chain; fail if tip mismatch."""


__all__ = ["AuditEvidenceStore"]
