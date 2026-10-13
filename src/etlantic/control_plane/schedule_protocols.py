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
    ScheduleRevisionPolicy,
    ScheduleSpec,
    TimerOwner,
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
    ) -> tuple[str, str]:
        """Invoke the runtime acceptance guard before admitting managed work.

        Its returned callback releases only this admission attempt and must
        run only after a definite CP1 rejection with verified receipt absence.
        Accepted work and uncertain outcomes retain their admission fence.
        """
        ...

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
        revision_policy: ScheduleRevisionPolicy = "pinned",
        workload_identity: Principal | None = None,
        execution_route: str = "local",
        timer_owner: TimerOwner = "local",
        next_fire_at: str | None = None,
    ) -> ScheduleRecord: ...

    def get(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord: ...

    def list_schedules(self, ctx: ControlPlaneContext) -> Sequence[ScheduleRecord]: ...

    def execution_route_reference_count(self, execution_route: str) -> int: ...

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
        execution_route: str | None = None,
        policy_fingerprint: str | None = None,
        durable: DurableWorkStore | None = None,
    ) -> ScheduleRecord: ...

    def transfer_timer_owner(
        self,
        ctx: ControlPlaneContext,
        schedule_id: str,
        *,
        expected_revision_id: str,
        expected_generation: int,
        timer_owner: TimerOwner,
        workload_identity: Principal | None,
        policy_fingerprint: str,
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
        expected_next_fire_at: str | None = None,
        expected_timer_owner: TimerOwner | None = None,
        expected_timer_owner_generation: int | None = None,
        require_active: bool = False,
    ) -> tuple[FiringRecord, bool]:
        """Idempotently claim while checking current schedule state atomically.

        New claims must match the stored revision. Scheduler-owned claims also
        require an active schedule. Existing logical firings remain replayable.
        """
        ...

    def acquire_firing_preparation(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        owner_id: str,
        ttl_seconds: int = 300,
    ) -> tuple[FiringRecord, bool]: ...

    def update_firing_metadata(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        metadata: Mapping[str, object],
        owner_id: str,
        fencing_token: int,
    ) -> FiringRecord: ...

    def release_firing_preparation(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        owner_id: str,
        fencing_token: int,
    ) -> None: ...

    def begin_firing_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        attempt_id: str | None = None,
    ) -> FiringRecord: ...

    def reject_firing_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        attempt_id: str,
    ) -> FiringRecord: ...

    def fail_firing_after_compensated_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        attempt_id: str,
    ) -> FiringRecord: ...

    def fail_firing_preparation(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        owner_id: str,
        fencing_token: int,
    ) -> FiringRecord: ...

    def link_firing_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        submission_id: str,
        plan_fingerprint: str,
        durable: DurableWorkStore,
        preparation_owner_id: str | None = None,
        preparation_fencing_token: int | None = None,
        recovered: bool = False,
    ) -> FiringRecord: ...

    def list_firings(
        self, ctx: ControlPlaneContext, schedule_id: str
    ) -> Sequence[FiringRecord]: ...
