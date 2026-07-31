"""Metadata-only history and impact models (CP2 / 040-H).

Observations store fingerprints and secret-free metadata only — never source
rows or resolved secrets. Accepting a baseline is an observation acknowledgement
and must not mutate registry revision authority (ADR-017).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from etlantic.control_plane.redaction import redact_control_plane_payload

SCHEMA_OBSERVATION_RECORD_SCHEMA = "etlantic.control_plane.schema_observation_record/1"
RELIABILITY_OBSERVATION_RECORD_SCHEMA = (
    "etlantic.control_plane.reliability_observation_record/1"
)
PLAN_OBSERVATION_RECORD_SCHEMA = "etlantic.control_plane.plan_observation_record/1"
IMPACT_EDGE_SCHEMA = "etlantic.control_plane.impact_edge/1"
CACHE_INVALIDATION_EVENT_SCHEMA = "etlantic.control_plane.cache_invalidation_event/1"

ObservationKind = Literal["schema", "reliability", "plan"]

_FORBIDDEN_ROW_KEYS = frozenset(
    {
        "rows",
        "sample_rows",
        "source_rows",
        "data_rows",
        "records",
        "payload_rows",
        "cells",
        "table_data",
    }
)


def _looks_like_row_payload(metadata: Mapping[str, Any] | None) -> bool:
    """True when metadata keys/values look like stored source rows."""
    if not metadata:
        return False
    for key, value in metadata.items():
        key_l = str(key).lower()
        if key_l in _FORBIDDEN_ROW_KEYS:
            return True
        if (
            key_l.endswith("_rows")
            or "sample" in key_l
            or key_l in {"cells", "table_data", "export"}
        ):
            return True
        if isinstance(value, list) and value:
            if all(isinstance(item, dict) for item in value):
                return True
            if all(isinstance(item, (list, tuple)) for item in value):
                return True
        if isinstance(value, dict) and _looks_like_row_payload(value):
            return True
        if isinstance(value, str):
            text = value.strip()
            if text.startswith(("[", "{")):
                try:
                    decoded = json.loads(text)
                except (TypeError, ValueError, json.JSONDecodeError):
                    decoded = None
                if isinstance(decoded, list) and decoded:
                    return True
                if isinstance(decoded, dict) and _looks_like_row_payload(decoded):
                    return True
    return False


def assert_history_metadata_only(metadata: Mapping[str, Any] | None) -> None:
    """Refuse history/impact metadata that embeds source-row-like payloads."""
    if _looks_like_row_payload(metadata):
        raise ValueError(
            "Control-plane history must not store source rows; failing closed."
        )


def _safe_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    assert_history_metadata_only(value)
    redacted = redact_control_plane_payload(dict(value or {}))
    return dict(redacted) if isinstance(redacted, dict) else {}


def _wire_bool(value: Any, *, field_name: str) -> bool:
    """Decode a JSON boolean without treating non-empty strings as true."""
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(f"{field_name} must be a boolean")


@dataclass(frozen=True, slots=True)
class SchemaObservationRecord:
    """Scoped schema observation (fingerprints + metadata only)."""

    observation_id: str
    tenant_id: str
    workspace_id: str
    subject_id: str
    schema_fingerprint: str
    field_fingerprints: Mapping[str, str] = field(default_factory=dict)
    observed_at: str | None = None
    inspector: str | None = None
    acknowledged: bool = False
    acknowledged_at: str | None = None
    note: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_OBSERVATION_RECORD_SCHEMA,
            "observation_id": self.observation_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "subject_id": self.subject_id,
            "schema_fingerprint": self.schema_fingerprint,
            "field_fingerprints": dict(self.field_fingerprints),
            "observed_at": self.observed_at,
            "inspector": self.inspector,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
            "note": self.note,
            "metadata": _safe_metadata(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SchemaObservationRecord:
        fields = data.get("field_fingerprints") or {}
        return cls(
            observation_id=str(data["observation_id"]),
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            subject_id=str(data["subject_id"]),
            schema_fingerprint=str(data["schema_fingerprint"]),
            field_fingerprints={str(k): str(v) for k, v in dict(fields).items()},
            observed_at=(
                str(data["observed_at"])
                if data.get("observed_at") is not None
                else None
            ),
            inspector=(
                str(data["inspector"]) if data.get("inspector") is not None else None
            ),
            acknowledged=_wire_bool(
                data.get("acknowledged", False), field_name="acknowledged"
            ),
            acknowledged_at=(
                str(data["acknowledged_at"])
                if data.get("acknowledged_at") is not None
                else None
            ),
            note=(str(data["note"]) if data.get("note") is not None else None),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class ReliabilityObservationRecord:
    """Scoped reliability observation (fingerprints + metadata only)."""

    observation_id: str
    tenant_id: str
    workspace_id: str
    subject_id: str
    kind: str
    result_fingerprint: str
    observed_at: str | None = None
    acknowledged: bool = False
    acknowledged_at: str | None = None
    note: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RELIABILITY_OBSERVATION_RECORD_SCHEMA,
            "observation_id": self.observation_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "subject_id": self.subject_id,
            "kind": self.kind,
            "result_fingerprint": self.result_fingerprint,
            "observed_at": self.observed_at,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
            "note": self.note,
            "metadata": _safe_metadata(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReliabilityObservationRecord:
        return cls(
            observation_id=str(data["observation_id"]),
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            subject_id=str(data["subject_id"]),
            kind=str(data["kind"]),
            result_fingerprint=str(data["result_fingerprint"]),
            observed_at=(
                str(data["observed_at"])
                if data.get("observed_at") is not None
                else None
            ),
            acknowledged=_wire_bool(
                data.get("acknowledged", False), field_name="acknowledged"
            ),
            acknowledged_at=(
                str(data["acknowledged_at"])
                if data.get("acknowledged_at") is not None
                else None
            ),
            note=(str(data["note"]) if data.get("note") is not None else None),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class PlanObservationRecord:
    """Scoped plan observation (fingerprints + metadata only)."""

    observation_id: str
    tenant_id: str
    workspace_id: str
    subject_id: str
    plan_fingerprint: str
    observed_at: str | None = None
    acknowledged: bool = False
    acknowledged_at: str | None = None
    note: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PLAN_OBSERVATION_RECORD_SCHEMA,
            "observation_id": self.observation_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "subject_id": self.subject_id,
            "plan_fingerprint": self.plan_fingerprint,
            "observed_at": self.observed_at,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
            "note": self.note,
            "metadata": _safe_metadata(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PlanObservationRecord:
        return cls(
            observation_id=str(data["observation_id"]),
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            subject_id=str(data["subject_id"]),
            plan_fingerprint=str(data["plan_fingerprint"]),
            observed_at=(
                str(data["observed_at"])
                if data.get("observed_at") is not None
                else None
            ),
            acknowledged=_wire_bool(
                data.get("acknowledged", False), field_name="acknowledged"
            ),
            acknowledged_at=(
                str(data["acknowledged_at"])
                if data.get("acknowledged_at") is not None
                else None
            ),
            note=(str(data["note"]) if data.get("note") is not None else None),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class ImpactEdge:
    """Field-level impact edge: contract field fingerprint → pipeline logical_id."""

    tenant_id: str
    workspace_id: str
    source_fingerprint: str
    target_logical_id: str
    edge_id: str | None = None
    source_kind: str = "contract_field"
    target_kind: str = "pipeline"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": IMPACT_EDGE_SCHEMA,
            "edge_id": self.edge_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "source_kind": self.source_kind,
            "source_fingerprint": self.source_fingerprint,
            "target_kind": self.target_kind,
            "target_logical_id": self.target_logical_id,
            "metadata": _safe_metadata(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ImpactEdge:
        return cls(
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            source_fingerprint=str(data["source_fingerprint"]),
            target_logical_id=str(data["target_logical_id"]),
            edge_id=(str(data["edge_id"]) if data.get("edge_id") is not None else None),
            source_kind=str(data.get("source_kind") or "contract_field"),
            target_kind=str(data.get("target_kind") or "pipeline"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class CacheInvalidationEvent:
    """Scoped cache-invalidation event (metadata / fingerprints only)."""

    event_id: str
    tenant_id: str
    workspace_id: str
    reason: str
    target_fingerprints: Sequence[str] = ()
    created_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CACHE_INVALIDATION_EVENT_SCHEMA,
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "reason": self.reason,
            "target_fingerprints": list(self.target_fingerprints),
            "created_at": self.created_at,
            "metadata": _safe_metadata(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CacheInvalidationEvent:
        targets = data.get("target_fingerprints") or ()
        if isinstance(targets, str):
            targets = (targets,)
        return cls(
            event_id=str(data["event_id"]),
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            reason=str(data["reason"]),
            target_fingerprints=tuple(str(t) for t in targets),
            created_at=(
                str(data["created_at"]) if data.get("created_at") is not None else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


__all__ = [
    "CACHE_INVALIDATION_EVENT_SCHEMA",
    "IMPACT_EDGE_SCHEMA",
    "PLAN_OBSERVATION_RECORD_SCHEMA",
    "RELIABILITY_OBSERVATION_RECORD_SCHEMA",
    "SCHEMA_OBSERVATION_RECORD_SCHEMA",
    "CacheInvalidationEvent",
    "ImpactEdge",
    "ObservationKind",
    "PlanObservationRecord",
    "ReliabilityObservationRecord",
    "SchemaObservationRecord",
    "assert_history_metadata_only",
]
