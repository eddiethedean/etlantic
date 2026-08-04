"""Append-only integrity-protected audit evidence (CP4)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)

AUDIT_RECORD_SCHEMA = "etlantic.control_plane.audit_record/1"
AUDIT_EXPORT_SCHEMA = "etlantic.control_plane.audit_export/1"

GENESIS_HASH = "0" * 64


def _now() -> datetime:
    return datetime.now(UTC)


def compute_record_hash(
    *,
    prev_hash: str,
    actor_subject: str,
    action: str,
    resource: str,
    decision_refs: tuple[str, ...],
    created_at: datetime,
    metadata: Mapping[str, Any],
) -> str:
    payload = {
        "prev_hash": prev_hash,
        "actor_subject": actor_subject,
        "action": action,
        "resource": resource,
        "decision_refs": list(decision_refs),
        "created_at": created_at.isoformat(),
        "metadata": redact_control_plane_payload(dict(metadata)),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AuditRecord:
    record_id: str
    tenant_id: str
    workspace_id: str
    actor_subject: str
    actor_issuer: str | None
    action: str
    resource: str
    prev_hash: str
    record_hash: str
    decision_refs: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": AUDIT_RECORD_SCHEMA,
            "record_id": self.record_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "actor_subject": self.actor_subject,
            "actor_issuer": self.actor_issuer,
            "action": redact_control_plane_text(self.action),
            "resource": self.resource,
            "prev_hash": self.prev_hash,
            "record_hash": self.record_hash,
            "decision_refs": list(self.decision_refs),
            "created_at": self.created_at.isoformat(),
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }


@dataclass(frozen=True, slots=True)
class AuditExport:
    export_id: str
    tenant_id: str
    workspace_id: str
    records: tuple[AuditRecord, ...]
    tip_hash: str
    created_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": AUDIT_EXPORT_SCHEMA,
            "export_id": self.export_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "records": [r.to_dict() for r in self.records],
            "tip_hash": self.tip_hash,
            "created_at": self.created_at.isoformat(),
        }


__all__ = [
    "AUDIT_EXPORT_SCHEMA",
    "AUDIT_RECORD_SCHEMA",
    "AuditExport",
    "AuditRecord",
    "GENESIS_HASH",
    "compute_record_hash",
]
