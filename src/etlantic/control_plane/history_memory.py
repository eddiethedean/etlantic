"""In-memory history and impact stores (CP2 / 040-H)."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.history_models import (
    CacheInvalidationEvent,
    ImpactEdge,
    ObservationKind,
    PlanObservationRecord,
    ReliabilityObservationRecord,
    SchemaObservationRecord,
    assert_history_metadata_only,
)
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _scope_match(
    ctx: ControlPlaneContext,
    *,
    tenant_id: str,
    workspace_id: str,
) -> bool:
    return (
        tenant_id == ctx.tenant.tenant_id and workspace_id == ctx.workspace.workspace_id
    )


def _redact_meta(metadata: dict[str, Any] | Any) -> dict[str, Any]:
    redacted = redact_control_plane_payload(dict(metadata or {}))
    if not isinstance(redacted, dict):
        return {}
    return redacted


@dataclass
class MemoryHistoryStore:
    """In-memory :class:`HistoryStore` with tenant/workspace isolation."""

    _schema: dict[tuple[str, str, str], SchemaObservationRecord] = field(
        default_factory=dict
    )
    _reliability: dict[tuple[str, str, str], ReliabilityObservationRecord] = field(
        default_factory=dict
    )
    _plan: dict[tuple[str, str, str], PlanObservationRecord] = field(
        default_factory=dict
    )
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def append_schema_observation(
        self,
        ctx: ControlPlaneContext,
        record: SchemaObservationRecord,
    ) -> SchemaObservationRecord:
        if not _scope_match(
            ctx, tenant_id=record.tenant_id, workspace_id=record.workspace_id
        ):
            raise ControlPlaneError.not_found(
                "Schema observation not found",
                extensions={"observation_id": record.observation_id},
            )
        assert_history_metadata_only(record.metadata)
        key = (*ctx.scope_key, record.observation_id)
        with self._lock:
            if key in self._schema:
                raise ControlPlaneError.conflict(
                    "Schema observation already exists",
                    extensions={"observation_id": record.observation_id},
                )
            stored = replace(
                record,
                field_fingerprints=dict(record.field_fingerprints),
                observed_at=record.observed_at or _utcnow_iso(),
                metadata=_redact_meta(record.metadata),
            )
            self._schema[key] = stored
            return deepcopy(stored)

    def append_reliability_observation(
        self,
        ctx: ControlPlaneContext,
        record: ReliabilityObservationRecord,
    ) -> ReliabilityObservationRecord:
        if not _scope_match(
            ctx, tenant_id=record.tenant_id, workspace_id=record.workspace_id
        ):
            raise ControlPlaneError.not_found(
                "Reliability observation not found",
                extensions={"observation_id": record.observation_id},
            )
        assert_history_metadata_only(record.metadata)
        key = (*ctx.scope_key, record.observation_id)
        with self._lock:
            if key in self._reliability:
                raise ControlPlaneError.conflict(
                    "Reliability observation already exists",
                    extensions={"observation_id": record.observation_id},
                )
            stored = replace(
                record,
                observed_at=record.observed_at or _utcnow_iso(),
                metadata=_redact_meta(record.metadata),
            )
            self._reliability[key] = stored
            return deepcopy(stored)

    def append_plan_observation(
        self,
        ctx: ControlPlaneContext,
        record: PlanObservationRecord,
    ) -> PlanObservationRecord:
        if not _scope_match(
            ctx, tenant_id=record.tenant_id, workspace_id=record.workspace_id
        ):
            raise ControlPlaneError.not_found(
                "Plan observation not found",
                extensions={"observation_id": record.observation_id},
            )
        assert_history_metadata_only(record.metadata)
        key = (*ctx.scope_key, record.observation_id)
        with self._lock:
            if key in self._plan:
                raise ControlPlaneError.conflict(
                    "Plan observation already exists",
                    extensions={"observation_id": record.observation_id},
                )
            stored = replace(
                record,
                observed_at=record.observed_at or _utcnow_iso(),
                metadata=_redact_meta(record.metadata),
            )
            self._plan[key] = stored
            return deepcopy(stored)

    def list_schema_observations(
        self,
        ctx: ControlPlaneContext,
        *,
        subject_id: str | None = None,
    ) -> Sequence[SchemaObservationRecord]:
        tenant_id, workspace_id = ctx.scope_key
        with self._lock:
            out = [
                deepcopy(rec)
                for (t, w, _), rec in self._schema.items()
                if t == tenant_id
                and w == workspace_id
                and (subject_id is None or rec.subject_id == subject_id)
            ]
            return sorted(out, key=lambda r: r.observation_id)

    def list_reliability_observations(
        self,
        ctx: ControlPlaneContext,
        *,
        subject_id: str | None = None,
    ) -> Sequence[ReliabilityObservationRecord]:
        tenant_id, workspace_id = ctx.scope_key
        with self._lock:
            out = [
                deepcopy(rec)
                for (t, w, _), rec in self._reliability.items()
                if t == tenant_id
                and w == workspace_id
                and (subject_id is None or rec.subject_id == subject_id)
            ]
            return sorted(out, key=lambda r: r.observation_id)

    def list_plan_observations(
        self,
        ctx: ControlPlaneContext,
        *,
        subject_id: str | None = None,
    ) -> Sequence[PlanObservationRecord]:
        tenant_id, workspace_id = ctx.scope_key
        with self._lock:
            out = [
                deepcopy(rec)
                for (t, w, _), rec in self._plan.items()
                if t == tenant_id
                and w == workspace_id
                and (subject_id is None or rec.subject_id == subject_id)
            ]
            return sorted(out, key=lambda r: r.observation_id)

    def get_schema_observation(
        self,
        ctx: ControlPlaneContext,
        observation_id: str,
    ) -> SchemaObservationRecord:
        key = (*ctx.scope_key, observation_id)
        with self._lock:
            record = self._schema.get(key)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Schema observation not found",
                    extensions={"observation_id": observation_id},
                )
            return deepcopy(record)

    def get_reliability_observation(
        self,
        ctx: ControlPlaneContext,
        observation_id: str,
    ) -> ReliabilityObservationRecord:
        key = (*ctx.scope_key, observation_id)
        with self._lock:
            record = self._reliability.get(key)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Reliability observation not found",
                    extensions={"observation_id": observation_id},
                )
            return deepcopy(record)

    def get_plan_observation(
        self,
        ctx: ControlPlaneContext,
        observation_id: str,
    ) -> PlanObservationRecord:
        key = (*ctx.scope_key, observation_id)
        with self._lock:
            record = self._plan.get(key)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Plan observation not found",
                    extensions={"observation_id": observation_id},
                )
            return deepcopy(record)

    def acknowledge_baseline(
        self,
        ctx: ControlPlaneContext,
        observation_id: str,
        *,
        kind: ObservationKind = "schema",
        note: str | None = None,
    ) -> SchemaObservationRecord | ReliabilityObservationRecord | PlanObservationRecord:
        """Mark an observation acknowledged without touching registry revisions."""
        key = (*ctx.scope_key, observation_id)
        now = _utcnow_iso()
        safe_note = redact_control_plane_text(note) if note is not None else None
        with self._lock:
            if kind == "schema":
                record = self._schema.get(key)
                if record is None:
                    raise ControlPlaneError.not_found(
                        "Schema observation not found",
                        extensions={"observation_id": observation_id},
                    )
                updated = replace(
                    record,
                    acknowledged=True,
                    acknowledged_at=now,
                    note=safe_note if note is not None else record.note,
                )
                self._schema[key] = updated
                return deepcopy(updated)
            if kind == "reliability":
                record = self._reliability.get(key)
                if record is None:
                    raise ControlPlaneError.not_found(
                        "Reliability observation not found",
                        extensions={"observation_id": observation_id},
                    )
                updated = replace(
                    record,
                    acknowledged=True,
                    acknowledged_at=now,
                    note=safe_note if note is not None else record.note,
                )
                self._reliability[key] = updated
                return deepcopy(updated)
            if kind == "plan":
                record = self._plan.get(key)
                if record is None:
                    raise ControlPlaneError.not_found(
                        "Plan observation not found",
                        extensions={"observation_id": observation_id},
                    )
                updated = replace(
                    record,
                    acknowledged=True,
                    acknowledged_at=now,
                    note=safe_note if note is not None else record.note,
                )
                self._plan[key] = updated
                return deepcopy(updated)
            raise ControlPlaneError.not_found(
                "Observation not found",
                extensions={"observation_id": observation_id, "kind": kind},
            )


@dataclass
class MemoryImpactIndex:
    """In-memory :class:`ImpactIndex` returning metadata-only dependents."""

    _edges: dict[tuple[str, str, str], ImpactEdge] = field(default_factory=dict)
    _invalidations: dict[tuple[str, str, str], CacheInvalidationEvent] = field(
        default_factory=dict
    )
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def register_edge(self, ctx: ControlPlaneContext, edge: ImpactEdge) -> ImpactEdge:
        if not _scope_match(
            ctx, tenant_id=edge.tenant_id, workspace_id=edge.workspace_id
        ):
            raise ControlPlaneError.not_found(
                "Impact edge not found",
                extensions={"target_logical_id": edge.target_logical_id},
            )
        assert_history_metadata_only(edge.metadata)
        edge_id = edge.edge_id or f"edge-{uuid.uuid4().hex[:16]}"
        key = (*ctx.scope_key, edge_id)
        with self._lock:
            if key in self._edges:
                raise ControlPlaneError.conflict(
                    "Impact edge already exists",
                    extensions={"edge_id": edge_id},
                )
            stored = replace(
                edge,
                edge_id=edge_id,
                metadata=_redact_meta(edge.metadata),
            )
            self._edges[key] = stored
            return deepcopy(stored)

    def dependents(
        self,
        ctx: ControlPlaneContext,
        source_fingerprint: str,
    ) -> Sequence[ImpactEdge]:
        tenant_id, workspace_id = ctx.scope_key
        with self._lock:
            out = [
                deepcopy(edge)
                for (t, w, _), edge in self._edges.items()
                if t == tenant_id
                and w == workspace_id
                and edge.source_fingerprint == source_fingerprint
            ]
            # Metadata only — strip any accidental non-meta fields via to_dict.
            return sorted(out, key=lambda e: (e.target_logical_id, e.edge_id or ""))

    def record_invalidation(
        self,
        ctx: ControlPlaneContext,
        event: CacheInvalidationEvent,
    ) -> CacheInvalidationEvent:
        if not _scope_match(
            ctx, tenant_id=event.tenant_id, workspace_id=event.workspace_id
        ):
            raise ControlPlaneError.not_found(
                "Cache invalidation event not found",
                extensions={"event_id": event.event_id},
            )
        assert_history_metadata_only(event.metadata)
        key = (*ctx.scope_key, event.event_id)
        with self._lock:
            if key in self._invalidations:
                raise ControlPlaneError.conflict(
                    "Cache invalidation event already exists",
                    extensions={"event_id": event.event_id},
                )
            stored = replace(
                event,
                target_fingerprints=tuple(event.target_fingerprints),
                created_at=event.created_at or _utcnow_iso(),
                metadata=_redact_meta(event.metadata),
            )
            self._invalidations[key] = stored
            return deepcopy(stored)

    def list_invalidations(
        self,
        ctx: ControlPlaneContext,
    ) -> Sequence[CacheInvalidationEvent]:
        tenant_id, workspace_id = ctx.scope_key
        with self._lock:
            return sorted(
                (
                    deepcopy(ev)
                    for (t, w, _), ev in self._invalidations.items()
                    if t == tenant_id and w == workspace_id
                ),
                key=lambda e: e.event_id,
            )


__all__ = [
    "MemoryHistoryStore",
    "MemoryImpactIndex",
]
