"""ScheduleStore conformance (memory + SQLModel providers)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    MemoryDurableWorkStore,
    Principal,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)


def _ctx(
    tenant: str = "tenant-a", workspace: str = "workspace-a"
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("scheduler-a", issuer="conformance"),
        tenant=TenantRef(tenant),
        workspace=WorkspaceRef(tenant, workspace),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def run_schedule_store_conformance_suite(store: Any) -> None:
    """Exercise ScheduleStore identity, leader lease, and firing-key invariants."""
    ctx = _ctx()
    spec = ScheduleSpec(kind="interval", interval_seconds=60, timezone="UTC")
    created = store.create(
        ctx,
        definition_id="pipe-1",
        profile_name="test",
        spec=spec,
        next_fire_at=_iso(datetime(2026, 1, 1, 0, 1, tzinfo=UTC)),
    )
    fetched = store.get(ctx, created.schedule_id)
    assert fetched.schedule_id == created.schedule_id
    assert fetched.revision_id == created.revision_id
    listed = store.list_schedules(ctx)
    assert any(item.schedule_id == created.schedule_id for item in listed)

    lease = store.acquire_leader_lease(ctx, owner_id="sched-1", ttl_seconds=30)
    again = store.acquire_leader_lease(ctx, owner_id="sched-1", ttl_seconds=30)
    assert again.fencing_token == lease.fencing_token
    try:
        store.acquire_leader_lease(ctx, owner_id="sched-2", ttl_seconds=30)
        raise AssertionError("second leader must be rejected")
    except ControlPlaneError:
        pass

    now = _iso(datetime(2026, 1, 1, 0, 2, tzinfo=UTC))
    due = store.due_schedules(ctx, now=now)
    assert any(item.schedule_id == created.schedule_id for item in due)

    durable = MemoryDurableWorkStore()
    firing, created_firing = store.claim_firing(
        ctx,
        schedule_id=created.schedule_id,
        revision_id=created.revision_id,
        nominal_fire_time=now,
        owner_id="sched-1",
        fencing_token=lease.fencing_token,
        plan_fingerprint="plan-1",
        durable=durable,
        next_fire_at=_iso(datetime(2026, 1, 1, 0, 3, tzinfo=UTC)),
    )
    assert created_firing
    replay, again_created = store.claim_firing(
        ctx,
        schedule_id=created.schedule_id,
        revision_id=created.revision_id,
        nominal_fire_time=now,
        owner_id="sched-1",
        fencing_token=lease.fencing_token,
        plan_fingerprint="plan-1",
        durable=durable,
    )
    assert not again_created
    assert replay.firing_id == firing.firing_id
    pending = durable.pending_outbox(ctx)
    assert len(pending) == 1
    firings = store.list_firings(ctx, created.schedule_id)
    assert len(firings) == 1

    paused = store.pause(ctx, created.schedule_id)
    assert paused.status == "paused"
    store.resume(ctx, created.schedule_id)
    store.delete(ctx, created.schedule_id)
    try:
        store.get(ctx, created.schedule_id)
        raise AssertionError("deleted schedule must 404")
    except ControlPlaneError:
        pass
