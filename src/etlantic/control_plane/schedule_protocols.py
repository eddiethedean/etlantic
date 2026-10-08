"""ScheduleStore protocol, leader leases, and polling wake-up."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.models import ControlPlaneContext, Principal
from etlantic.control_plane.schedule_models import (
    FiringRecord,
    FiringStatus,
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
class ScheduledOccurrenceService(Protocol):
    """Canonical preparation, acceptance, and recovery for managed firings."""

    def prepare_scheduled_occurrence(
        self,
        ctx: ControlPlaneContext,
        schedule: ScheduleRecord,
        nominal_fire_time: str,
        existing_firing: FiringRecord | None = None,
    ) -> ScheduleRecord: ...

    def submit_scheduled_run(
        self,
        ctx: ControlPlaneContext,
        schedule: ScheduleRecord,
        nominal_fire_time: str,
    ) -> tuple[str, str]: ...

    def recover_scheduled_occurrence(
        self,
        ctx: ControlPlaneContext,
        schedule: ScheduleRecord,
        nominal_fire_time: str,
    ) -> tuple[str, str] | None: ...


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
        definition_revision_id: str | None = None,
        parameter_refs: dict[str, str] | None = None,
        secret_refs: dict[str, Mapping[str, object] | str] | None = None,
        revision_policy: str = "pinned",
        workload_identity: Principal | None = None,
        next_fire_at: str | None = None,
    ) -> ScheduleRecord: ...

    def get(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord: ...

    def list_schedules(self, ctx: ControlPlaneContext) -> Sequence[ScheduleRecord]: ...

    def pause(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord: ...

    def resume(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord: ...

    def amend(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        *,
        expected_revision_id: str,
        spec: ScheduleSpec,
        next_fire_at: str | None,
        durable: DurableWorkStore | None = None,
    ) -> ScheduleRecord: ...

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
        admit_submission: bool = True,
        skip_status: FiringStatus | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> tuple[FiringRecord, bool]:
        """Idempotently claim while checking current schedule state atomically.

        New claims must match the stored revision. Scheduler-owned claims also
        require an active schedule. Existing logical firings remain replayable.
        """
        ...

    def link_firing_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        submission_id: str,
        plan_fingerprint: str,
        durable: DurableWorkStore,
    ) -> FiringRecord: ...

    def list_firings(
        self, ctx: ControlPlaneContext, schedule_id: str
    ) -> Sequence[FiringRecord]: ...
