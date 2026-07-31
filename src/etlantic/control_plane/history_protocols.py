"""History and impact protocols (CP2 / 040-H).

Every method takes an immutable
:class:`~etlantic.control_plane.models.ControlPlaneContext`. Histories store
fingerprints and metadata only; acknowledging a baseline never mutates
:class:`~etlantic.control_plane.registry_models.RegistryRevision` content.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from etlantic.control_plane.history_models import (
    CacheInvalidationEvent,
    ImpactEdge,
    ObservationKind,
    PlanObservationRecord,
    ReliabilityObservationRecord,
    SchemaObservationRecord,
)
from etlantic.control_plane.models import ControlPlaneContext


@runtime_checkable
class HistoryStore(Protocol):
    """Scoped, append-mostly observation history (metadata / fingerprints only)."""

    def append_schema_observation(
        self,
        ctx: ControlPlaneContext,
        record: SchemaObservationRecord,
    ) -> SchemaObservationRecord:
        """Append a schema observation inside ``ctx`` scope."""
        ...

    def append_reliability_observation(
        self,
        ctx: ControlPlaneContext,
        record: ReliabilityObservationRecord,
    ) -> ReliabilityObservationRecord:
        """Append a reliability observation inside ``ctx`` scope."""
        ...

    def append_plan_observation(
        self,
        ctx: ControlPlaneContext,
        record: PlanObservationRecord,
    ) -> PlanObservationRecord:
        """Append a plan observation inside ``ctx`` scope."""
        ...

    def list_schema_observations(
        self,
        ctx: ControlPlaneContext,
        *,
        subject_id: str | None = None,
    ) -> Sequence[SchemaObservationRecord]:
        """List schema observations inside ``ctx`` scope."""
        ...

    def list_reliability_observations(
        self,
        ctx: ControlPlaneContext,
        *,
        subject_id: str | None = None,
    ) -> Sequence[ReliabilityObservationRecord]:
        """List reliability observations inside ``ctx`` scope."""
        ...

    def list_plan_observations(
        self,
        ctx: ControlPlaneContext,
        *,
        subject_id: str | None = None,
    ) -> Sequence[PlanObservationRecord]:
        """List plan observations inside ``ctx`` scope."""
        ...

    def get_schema_observation(
        self,
        ctx: ControlPlaneContext,
        observation_id: str,
    ) -> SchemaObservationRecord:
        """Fetch a schema observation inside ``ctx`` scope."""
        ...

    def get_reliability_observation(
        self,
        ctx: ControlPlaneContext,
        observation_id: str,
    ) -> ReliabilityObservationRecord:
        """Fetch a reliability observation inside ``ctx`` scope."""
        ...

    def get_plan_observation(
        self,
        ctx: ControlPlaneContext,
        observation_id: str,
    ) -> PlanObservationRecord:
        """Fetch a plan observation inside ``ctx`` scope."""
        ...

    def acknowledge_baseline(
        self,
        ctx: ControlPlaneContext,
        observation_id: str,
        *,
        kind: ObservationKind = "schema",
        note: str | None = None,
    ) -> SchemaObservationRecord | ReliabilityObservationRecord | PlanObservationRecord:
        """Acknowledge an observation as an operational baseline.

        Does **not** mutate registry revision content or promote the
        observation to contract authority.
        """
        ...


@runtime_checkable
class ImpactIndex(Protocol):
    """Scoped field-level impact index and cache-invalidation events."""

    def register_edge(self, ctx: ControlPlaneContext, edge: ImpactEdge) -> ImpactEdge:
        """Register a dependency edge inside ``ctx`` scope."""
        ...

    def dependents(
        self,
        ctx: ControlPlaneContext,
        source_fingerprint: str,
    ) -> Sequence[ImpactEdge]:
        """Return dependents of a contract-field fingerprint (metadata only)."""
        ...

    def record_invalidation(
        self,
        ctx: ControlPlaneContext,
        event: CacheInvalidationEvent,
    ) -> CacheInvalidationEvent:
        """Record a cache-invalidation event inside ``ctx`` scope."""
        ...

    def list_invalidations(
        self,
        ctx: ControlPlaneContext,
    ) -> Sequence[CacheInvalidationEvent]:
        """List cache-invalidation events inside ``ctx`` scope."""
        ...


__all__ = [
    "HistoryStore",
    "ImpactIndex",
]
