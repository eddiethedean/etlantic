"""Scheduler dual-replica, execution-host, and import-graph tests."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
from etlantic.runtime.execution_host import ExecutionHost, UnknownCommitError
from etlantic.runtime.scheduler_service import SchedulerService


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("sched", issuer="tests"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "ws-1"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def test_dual_replica_one_durable_firing() -> None:
    store = MemoryScheduleStore()
    durable = MemoryDurableWorkStore()
    clock = FakeScheduleClock(datetime(2026, 1, 1, 0, 2, tzinfo=UTC))
    ctx = _ctx()
    rec = store.create(
        ctx,
        definition_id="pipe-1",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at="2026-01-01T00:01:00Z",
    )
    left = SchedulerService(store, durable=durable, clock=clock, owner_id="sched-left")
    right = SchedulerService(
        store, durable=durable, clock=clock, owner_id="sched-right"
    )
    left.tick(ctx)
    right.tick(ctx)
    firings = store.list_firings(ctx, rec.schedule_id)
    assert len(firings) == 1
    assert len(durable.pending_outbox(ctx)) == 1


def test_execution_host_default_runner_completes_submission() -> None:
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    submission, _ = durable.accept(
        ctx,
        idempotency_key="default-runner",
        operation="schedule.fire",
        plan_fingerprint="plan",
    )
    host = ExecutionHost(durable, owner_id="w1")
    assert host.tick(ctx) == 1
    assert durable.submission_status(ctx, submission.submission_id) == "completed"


def test_execution_host_completes_and_unknown_commit_does_not_retry() -> None:
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    submission, _ = durable.accept(
        ctx,
        idempotency_key="k1",
        operation="schedule.fire",
        plan_fingerprint="plan",
    )
    host = ExecutionHost(durable, owner_id="w1")
    assert host.tick(ctx) == 1
    replay = durable.pending_outbox(ctx)
    assert replay == []

    lost_sub, _ = durable.accept(
        ctx,
        idempotency_key="k2",
        operation="schedule.fire",
        plan_fingerprint="plan",
    )

    def boom(**_: object) -> None:
        raise UnknownCommitError()

    host2 = ExecutionHost(durable, owner_id="w2", runner=boom)
    host2.tick(ctx)
    # Unknown commit is lost; outbox already published so no auto-retry.
    assert durable.pending_outbox(ctx) == []
    _ = lost_sub, submission


def test_execution_host_module_does_not_import_fastapi() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "etlantic"
        / "runtime"
        / "execution_host.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert "fastapi" not in names
    assert "etlantic_fastapi" not in names


def test_manual_trigger_does_not_require_leader_lease() -> None:
    store = MemoryScheduleStore()
    durable = MemoryDurableWorkStore()
    clock = FakeScheduleClock(datetime(2026, 1, 1, 0, 2, tzinfo=UTC))
    ctx = _ctx()
    rec = store.create(
        ctx,
        definition_id="pipe-1",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at="2026-01-01T00:01:00Z",
    )
    scheduler = SchedulerService(
        store, durable=durable, clock=clock, owner_id="sched-1"
    )
    scheduler.tick(ctx)
    now = clock.now().isoformat().replace("+00:00", "Z")
    firing, created = store.claim_firing(
        ctx,
        schedule_id=rec.schedule_id,
        revision_id=rec.revision_id,
        nominal_fire_time=now,
        owner_id="gateway",
        fencing_token=0,
        plan_fingerprint="manual",
        durable=durable,
        require_leader_lease=False,
    )
    assert created
    assert firing.status == "accepted"


def test_scheduler_drain_stops_ticks() -> None:
    store = MemoryScheduleStore()
    service = SchedulerService(
        store,
        clock=FakeScheduleClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    service.drain()
    assert service.tick(_ctx()) == 0
    _ = timedelta
