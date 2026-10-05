"""Scheduler dual-replica, execution-host, and import-graph tests."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from time import sleep
from typing import Any, cast

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    DurableWorkStore,
    EnvironmentRef,
    FakeScheduleClock,
    FiringRecord,
    MemoryDurableWorkStore,
    MemoryScheduleStore,
    Principal,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.schedule_models import FiringStatus
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.execution_host import ExecutionHost, UnknownCommitError
from etlantic.runtime.request import RunIntent
from etlantic.runtime.scheduler_service import SchedulerService
from etlantic.runtime.state import RunStatus


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("sched", issuer="tests"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "ws-1"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


@pytest.mark.parametrize("ttl_seconds", [True, 0, -1, 1.5, None])
def test_worker_and_scheduler_reject_invalid_lease_ttls(ttl_seconds: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        ExecutionHost(MemoryDurableWorkStore(), ttl_seconds=cast(Any, ttl_seconds))
    with pytest.raises(ValueError, match="positive integer"):
        SchedulerService(MemoryScheduleStore(), ttl_seconds=cast(Any, ttl_seconds))


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


def test_wake_outage_after_firing_commit_is_recoverable_without_duplicate() -> None:
    class FailFirstWake:
        calls = 0

        def notify(self) -> None:
            self.calls += 1
            if self.calls == 1:
                raise OSError("simulated wake transport outage")

    ctx = _ctx()
    due_at = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    schedules = MemoryScheduleStore()
    durable = MemoryDurableWorkStore()
    rec = schedules.create(
        ctx,
        definition_id="wake-outage-pipeline",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at=due_at.isoformat().replace("+00:00", "Z"),
    )
    wake = FailFirstWake()
    service = SchedulerService(
        schedules,
        durable=durable,
        clock=FakeScheduleClock(due_at),
        owner_id="wake-outage-scheduler",
        wake=wake,
    )

    with pytest.raises(OSError, match="wake transport outage"):
        service.tick(ctx)
    committed_firings = schedules.list_firings(ctx, rec.schedule_id)
    committed_outbox = durable.pending_outbox(ctx)
    assert len(committed_firings) == 1
    assert committed_firings[0].status == "accepted"
    assert committed_firings[0].submission_id == committed_outbox[0].submission_id

    # Simulate process replacement from both durable snapshots. The next scan
    # sees the advanced schedule cursor and cannot enqueue a second occurrence.
    recovered_schedules = MemoryScheduleStore()
    recovered_schedules.load(schedules.dump())
    recovered_durable = MemoryDurableWorkStore()
    recovered_durable.load(durable.dump())
    restarted = SchedulerService(
        recovered_schedules,
        durable=recovered_durable,
        clock=FakeScheduleClock(due_at),
        owner_id="wake-outage-scheduler",
    )
    assert restarted.tick(ctx) == 0
    assert recovered_schedules.list_firings(ctx, rec.schedule_id) == tuple(
        committed_firings
    )
    assert [item.submission_id for item in recovered_durable.pending_outbox(ctx)] == [
        committed_outbox[0].submission_id
    ]


def test_failed_due_occurrence_does_not_starve_other_schedules() -> None:
    ctx = _ctx()
    store = MemoryScheduleStore()
    due_at = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    broken = store.create(
        ctx,
        definition_id="broken-occurrence",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at=due_at.isoformat().replace("+00:00", "Z"),
    )
    healthy = store.create(
        ctx,
        definition_id="healthy-occurrence",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at=due_at.isoformat().replace("+00:00", "Z"),
    )

    def prepare_occurrence(
        _ctx: ControlPlaneContext,
        schedule: Any,
        _nominal_fire_time: str,
        _firing: FiringRecord | None,
    ) -> Any:
        if schedule.definition_id == "broken-occurrence":
            raise RuntimeError("simulated occurrence preparation failure")
        return schedule

    service = SchedulerService(
        store,
        durable=MemoryDurableWorkStore(),
        clock=FakeScheduleClock(due_at),
        occurrence_preparer=prepare_occurrence,
    )

    assert service.tick(ctx) == 1
    assert store.list_firings(ctx, broken.schedule_id) == ()
    assert len(store.list_firings(ctx, healthy.schedule_id)) == 1


def test_due_scan_cannot_admit_firing_after_schedule_is_paused() -> None:
    class PauseBeforeClaimStore(MemoryScheduleStore):
        pause_before_claim = True

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
            if self.pause_before_claim:
                self.pause_before_claim = False
                self.pause(ctx, schedule_id)
            return super().claim_firing(
                ctx,
                schedule_id=schedule_id,
                revision_id=revision_id,
                nominal_fire_time=nominal_fire_time,
                owner_id=owner_id,
                fencing_token=fencing_token,
                plan_fingerprint=plan_fingerprint,
                durable=durable,
                next_fire_at=next_fire_at,
                require_leader_lease=require_leader_lease,
                admit_submission=admit_submission,
                skip_status=skip_status,
                metadata=metadata,
            )

    ctx = _ctx()
    store = PauseBeforeClaimStore()
    durable = MemoryDurableWorkStore()
    due_at = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    rec = store.create(
        ctx,
        definition_id="pipe-pause-race",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at=due_at.isoformat().replace("+00:00", "Z"),
    )
    service = SchedulerService(
        store,
        durable=durable,
        clock=FakeScheduleClock(due_at),
        owner_id="pause-race-scheduler",
    )

    assert service.tick(ctx) == 0
    assert store.get(ctx, rec.schedule_id).status == "paused"
    assert store.list_firings(ctx, rec.schedule_id) == ()
    assert durable.pending_outbox(ctx) == []


def test_execution_host_uses_the_packaged_runtime_adapter_by_default() -> None:
    durable = MemoryDurableWorkStore()
    host = ExecutionHost(durable, owner_id="w1")
    assert host.runner is not None
    assert host.runner.__class__.__name__ == "ManagedExecutionAdapter"


def _report(*, status: RunStatus = RunStatus.SUCCEEDED) -> PipelineRunReport:
    return PipelineRunReport(
        pipeline_id="pipe-1",
        plan_id="plan-1",
        run_id="run-1",
        intent=RunIntent.STANDARD,
        profile="development",
        status=status,
        started_at=datetime.now(UTC),
        plan_fingerprint="plan",
    )


def test_execution_host_completes_and_unknown_commit_does_not_retry() -> None:
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    submission, _ = durable.accept(
        ctx,
        idempotency_key="k1",
        operation="schedule.fire",
        plan_fingerprint="plan",
    )

    def complete(_ctx: ControlPlaneContext, **_: object) -> PipelineRunReport:
        return _report()

    host = ExecutionHost(durable, owner_id="w1", runner=complete)
    assert host.tick(ctx) == 1
    replay = durable.pending_outbox(ctx)
    assert replay == []

    lost_sub, _ = durable.accept(
        ctx,
        idempotency_key="k2",
        operation="schedule.fire",
        plan_fingerprint="plan",
    )

    def boom(_ctx: ControlPlaneContext, **_: object) -> None:
        raise UnknownCommitError()

    host2 = ExecutionHost(durable, owner_id="w2", runner=boom)
    host2.tick(ctx)
    # Unknown commit is lost and not retried automatically.
    assert durable.pending_outbox(ctx) == []
    _ = lost_sub, submission


def test_execution_host_does_not_acknowledge_a_noop_runner() -> None:
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    submission, _ = durable.accept(
        ctx,
        idempotency_key="noop",
        operation="run.submit",
        plan_fingerprint="plan",
    )

    def no_op_runner(_ctx: ControlPlaneContext, **_kwargs: object) -> None:
        return None

    host = ExecutionHost(durable, owner_id="w1", runner=no_op_runner)

    assert host.tick(ctx) == 1
    assert durable.get_submission(ctx, submission.submission_id).status == "failed"
    assert durable.pending_outbox(ctx) == []


def test_execution_host_persists_actual_effect_receipt() -> None:
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    submission, _ = durable.accept(
        ctx,
        idempotency_key="success",
        operation="run.submit",
        plan_fingerprint="plan",
    )

    def success_runner(
        _ctx: ControlPlaneContext, **_kwargs: object
    ) -> PipelineRunReport:
        return _report()

    host = ExecutionHost(durable, owner_id="w1", runner=success_runner)

    assert host.tick(ctx) == 1
    assert durable.get_submission(ctx, submission.submission_id).status == "completed"
    effect = durable.get_effect(ctx, f"{submission.submission_id}:execution")
    assert effect.status == "committed"
    assert effect.idempotency_evidence


def test_execution_host_renews_lease_during_long_running_work() -> None:
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    submission, _ = durable.accept(
        ctx,
        idempotency_key="long-worker",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    started = Event()
    allow_finish = Event()
    calls = 0

    def runner(_ctx: ControlPlaneContext, **_: object) -> PipelineRunReport:
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            assert allow_finish.wait(timeout=4)
        return _report()

    first = ExecutionHost(
        durable, owner_id="long-worker-1", ttl_seconds=1, runner=runner
    )
    second = ExecutionHost(
        durable, owner_id="long-worker-2", ttl_seconds=1, runner=runner
    )
    results: list[int] = []
    worker = Thread(target=lambda: results.append(first.tick(ctx)))
    worker.start()
    try:
        assert started.wait(timeout=2)
        sleep(1.2)
        # The initial lease would have expired without the background heartbeat.
        assert second.tick(ctx) == 0
        assert calls == 1
    finally:
        allow_finish.set()
        worker.join(timeout=4)

    assert not worker.is_alive()
    assert results == [1]
    assert durable.get_submission(ctx, submission.submission_id).status == "completed"


def test_execution_host_cooperatively_cancels_in_flight_run() -> None:
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    submission, _ = durable.accept(
        ctx,
        idempotency_key="cancel-worker",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    started = Event()

    def runner(
        _ctx: ControlPlaneContext, *, cancel_event: Event, **_: object
    ) -> PipelineRunReport:
        started.set()
        assert cancel_event.wait(timeout=3)
        return _report(status=RunStatus.CANCELLED)

    host = ExecutionHost(
        durable, owner_id="cancel-worker", ttl_seconds=1, runner=runner
    )
    worker = Thread(target=lambda: host.tick(ctx))
    worker.start()
    assert started.wait(timeout=2)
    durable.cancel_submission(ctx, submission.submission_id)
    worker.join(timeout=4)

    assert not worker.is_alive()
    assert durable.get_submission(ctx, submission.submission_id).status == "cancelled"
    assert durable.list_attempts(ctx, submission.submission_id)[0].status == "cancelled"
    assert durable.get_effect(ctx, f"{submission.submission_id}:execution").status == (
        "unknown"
    )
    assert durable.pending_outbox(ctx) == []


def test_worker_reconciles_terminal_submission_after_outbox_ack_crash() -> None:
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    submission, _ = durable.accept(
        ctx,
        idempotency_key="ack-crash",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    lease = durable.acquire_lease(
        ctx, submission.submission_id, owner_id="crashed-worker", ttl_seconds=30
    )
    attempt = durable.start_attempt(
        ctx,
        submission.submission_id,
        owner_id="crashed-worker",
        fencing_token=lease.fencing_token,
    )
    durable.finish_attempt(
        ctx,
        attempt.attempt_id,
        owner_id="crashed-worker",
        fencing_token=lease.fencing_token,
        status="completed",
    )
    assert durable.pending_outbox(ctx) == []

    assert ExecutionHost(durable, owner_id="reconciler").tick(ctx) == 0
    assert durable.reconcile_terminal_outbox(ctx) == []
    outbox_rows = list(durable.dump()["outbox"].values())
    assert len(outbox_rows) == 1
    assert outbox_rows[0]["published_at"] is not None


def test_queued_cancellation_is_terminal_without_starting_a_worker() -> None:
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    submission, _ = durable.accept(
        ctx,
        idempotency_key="cancel-queued",
        operation="run.submit",
        plan_fingerprint="plan",
    )

    assert durable.cancel_submission(ctx, submission.submission_id).status == (
        "cancel_requested"
    )

    def forbidden_runner(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("cancelled work was executed")

    assert (
        ExecutionHost(
            durable,
            owner_id="cancel-queued-worker",
            runner=forbidden_runner,
        ).tick(ctx)
        == 0
    )
    assert durable.get_submission(ctx, submission.submission_id).status == "cancelled"
    assert durable.pending_outbox(ctx) == []
    with pytest.raises(ControlPlaneError, match="Effect not found"):
        durable.get_effect(ctx, f"{submission.submission_id}:execution")


def test_expired_in_flight_cancellation_is_reconciled_after_worker_death() -> None:
    durable = MemoryDurableWorkStore()
    ctx = _ctx()
    submission, _ = durable.accept(
        ctx,
        idempotency_key="cancel-abandoned",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    lease = durable.acquire_lease(
        ctx, submission.submission_id, owner_id="abandoned-worker", ttl_seconds=1
    )
    durable.start_attempt(
        ctx,
        submission.submission_id,
        owner_id="abandoned-worker",
        fencing_token=lease.fencing_token,
    )
    assert durable.cancel_submission(ctx, submission.submission_id).status == (
        "cancel_requested"
    )
    sleep(1.1)

    assert ExecutionHost(durable, owner_id="cancel-reconciler").tick(ctx) == 0
    assert durable.get_submission(ctx, submission.submission_id).status == "cancelled"
    assert durable.list_attempts(ctx, submission.submission_id)[0].status == "lost"
    assert durable.get_effect(ctx, f"{submission.submission_id}:execution").status == (
        "unknown"
    )
    assert durable.pending_outbox(ctx) == []


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
        spec=ScheduleSpec(kind="interval", interval_seconds=60, overlap="queue"),
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
