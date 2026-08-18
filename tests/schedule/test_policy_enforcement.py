"""Schedule overlap, misfire, and effective-window enforcement."""

from __future__ import annotations

from datetime import UTC, datetime

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    FakeScheduleClock,
    MemoryDurableWorkStore,
    MemoryScheduleStore,
    Principal,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.runtime.scheduler_service import SchedulerService


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("sched", issuer="tests"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "ws-1"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def test_overlap_skip_while_submission_inflight() -> None:
    store = MemoryScheduleStore()
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    rec = store.create(
        ctx,
        definition_id="pipe-1",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60, overlap="skip"),
        next_fire_at="2026-01-01T00:01:00Z",
    )
    lease = store.acquire_leader_lease(ctx, owner_id="sched-1", ttl_seconds=30)
    first, created = store.claim_firing(
        ctx,
        schedule_id=rec.schedule_id,
        revision_id=rec.revision_id,
        nominal_fire_time="2026-01-01T00:01:00Z",
        owner_id="sched-1",
        fencing_token=lease.fencing_token,
        plan_fingerprint="plan",
        durable=durable,
        next_fire_at="2026-01-01T00:02:00Z",
    )
    assert created and first.status == "accepted"
    assert len(durable.pending_outbox(ctx)) == 1
    second, again = store.claim_firing(
        ctx,
        schedule_id=rec.schedule_id,
        revision_id=rec.revision_id,
        nominal_fire_time="2026-01-01T00:02:00Z",
        owner_id="sched-1",
        fencing_token=lease.fencing_token,
        plan_fingerprint="plan",
        durable=durable,
        next_fire_at="2026-01-01T00:03:00Z",
    )
    assert again
    assert second.status == "skipped_overlap"
    assert len(durable.pending_outbox(ctx)) == 1


def test_misfire_skip_does_not_accept_durable_work() -> None:
    store = MemoryScheduleStore()
    durable = MemoryDurableWorkStore()
    clock = FakeScheduleClock(datetime(2026, 1, 1, 0, 5, tzinfo=UTC))
    ctx = _ctx()
    rec = store.create(
        ctx,
        definition_id="pipe-1",
        profile_name="test",
        spec=ScheduleSpec(
            kind="interval", interval_seconds=60, misfire="skip", overlap="queue"
        ),
        next_fire_at="2026-01-01T00:01:00Z",
    )
    service = SchedulerService(
        store, durable=durable, clock=clock, owner_id="sched-1"
    )
    assert service.tick(ctx) == 1
    firings = store.list_firings(ctx, rec.schedule_id)
    assert len(firings) == 1
    assert firings[0].status == "skipped_misfire"
    assert durable.pending_outbox(ctx) == []


def test_effective_window_skip_outside_window() -> None:
    store = MemoryScheduleStore()
    durable = MemoryDurableWorkStore()
    clock = FakeScheduleClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    ctx = _ctx()
    window_end = "2025-12-31T23:00:00Z"
    rec = store.create(
        ctx,
        definition_id="pipe-1",
        profile_name="test",
        spec=ScheduleSpec(
            kind="interval",
            interval_seconds=60,
            window_end=window_end,
            overlap="queue",
        ),
        next_fire_at="2026-01-01T00:01:00Z",
    )
    service = SchedulerService(
        store, durable=durable, clock=clock, owner_id="sched-1"
    )
    assert service.tick(ctx) == 1
    firings = store.list_firings(ctx, rec.schedule_id)
    assert len(firings) == 1
    assert firings[0].status == "skipped_window"
    assert durable.pending_outbox(ctx) == []
