"""ScheduleStore protocol, leader leases, and polling wake-up."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.schedule_models import (
    FiringRecord,
    ScheduleRecord,
    ScheduleSpec,
)


@dataclass(frozen=True, slots=True)
class SchedulerLeaderLease:
    """Timer-leadership lease, distinct from CP3 execution leases."""

    owner_id: str
    fencing_token: int
    expires_at: str
    heartbeat_at: str
    tenant_id: str
    workspace_id: str


@runtime_checkable
class WakeTransport(Protocol):
    def notify(self) -> None: ...


class PollingWakeTransport:
    """Reference wake-up: scheduler polls due timers (no broker)."""

    def notify(self) -> None:
        return None


@runtime_checkable
class ScheduleStore(Protocol):
    def create(
        self,
        ctx: ControlPlaneContext,
        *,
        definition_id: str,
        profile_name: str,
        spec: ScheduleSpec,
        schedule_id: str | None = None,
        policy_fingerprint: str = "",
        parameter_refs: dict[str, str] | None = None,
        secret_refs: dict[str, str] | None = None,
        next_fire_at: str | None = None,
    ) -> ScheduleRecord: ...

    def get(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord: ...

    def list_schedules(self, ctx: ControlPlaneContext) -> Sequence[ScheduleRecord]: ...

    def pause(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord: ...

    def resume(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord: ...

    def delete(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord: ...

    def acquire_leader_lease(
        self,
        ctx: ControlPlaneContext,
        *,
        owner_id: str,
        ttl_seconds: int,
    ) -> SchedulerLeaderLease: ...

    def heartbeat_leader(
        self,
        ctx: ControlPlaneContext,
        *,
        owner_id: str,
        fencing_token: int,
        ttl_seconds: int,
    ) -> SchedulerLeaderLease: ...

    def release_leader(
        self,
        ctx: ControlPlaneContext,
        *,
        owner_id: str,
        fencing_token: int,
    ) -> None: ...

    def due_schedules(
        self, ctx: ControlPlaneContext, *, now: str
    ) -> Sequence[ScheduleRecord]: ...

    def claim_firing(
        self,
        ctx: ControlPlaneContext,
        *,
        schedule_id: str,
        revision_id: str,
        nominal_fire_time: str,
        owner_id: str,
        fencing_token: int,
        plan_fingerprint: str,
        durable: DurableWorkStore | None = None,
        next_fire_at: str | None = None,
        require_leader_lease: bool = True,
    ) -> tuple[FiringRecord, bool]: ...

    def list_firings(
        self, ctx: ControlPlaneContext, schedule_id: str
    ) -> Sequence[FiringRecord]: ...
