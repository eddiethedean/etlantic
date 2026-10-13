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
    """Exercise ScheduleStore identity, lease, and admission-fence invariants."""
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

    pending_schedule = store.create(
        ctx,
        definition_id="pipe-pending",
        profile_name="test",
        spec=spec,
        next_fire_at=now,
    )
    pending, pending_created = store.claim_firing(
        ctx,
        schedule_id=pending_schedule.schedule_id,
        revision_id=pending_schedule.revision_id,
        nominal_fire_time=now,
        owner_id="sched-1",
        fencing_token=lease.fencing_token,
        plan_fingerprint="managed-admission-pending",
        durable=durable,
        admit_submission=False,
    )
    assert pending_created
    preparation, acquired = store.acquire_firing_preparation(
        ctx, pending.firing_id, owner_id="submitter-1"
    )
    assert acquired
    started = store.begin_firing_submission(
        ctx,
        pending.firing_id,
        owner_id="submitter-1",
        fencing_token=preparation.preparation_fencing_token,
    )
    assert started.submission_started
    try:
        store.fail_firing_preparation(
            ctx,
            pending.firing_id,
            owner_id="submitter-1",
            fencing_token=preparation.preparation_fencing_token,
        )
        raise AssertionError("submission-started firing cannot fail preparation")
    except ControlPlaneError as exc:
        assert exc.extensions.get("reason") == "occurrence_submission_started"
    pending_after = next(
        item
        for item in store.list_firings(ctx, pending_schedule.schedule_id)
        if item.firing_id == pending.firing_id
    )
    assert pending_after.status == "accepted"
    assert pending_after.submission_started

    # A new owner may start admission while an expired/released owner's
    # acceptance is still in flight. Rejecting either attempt clears only it.
    first_attempt = started.submission_attempt_ids[-1]
    store.release_firing_preparation(
        ctx,
        pending.firing_id,
        owner_id="submitter-1",
        fencing_token=preparation.preparation_fencing_token,
    )
    new_preparation, acquired = store.acquire_firing_preparation(
        ctx, pending.firing_id, owner_id="submitter-2"
    )
    assert acquired
    second = store.begin_firing_submission(
        ctx,
        pending.firing_id,
        owner_id="submitter-2",
        fencing_token=new_preparation.preparation_fencing_token,
    )
    second_attempt = second.submission_attempt_ids[-1]
    remaining = store.reject_firing_submission(
        ctx, pending.firing_id, attempt_id=second_attempt
    )
    assert remaining.submission_started
    assert remaining.submission_attempt_ids == (first_attempt,)
    try:
        store.fail_firing_preparation(
            ctx,
            pending.firing_id,
            owner_id="submitter-2",
            fencing_token=new_preparation.preparation_fencing_token,
        )
        raise AssertionError("older in-flight admission must remain fenced")
    except ControlPlaneError as exc:
        assert exc.extensions.get("reason") == "occurrence_submission_started"
    cleared = store.reject_firing_submission(
        ctx, pending.firing_id, attempt_id=first_attempt
    )
    assert not cleared.submission_started
    assert not cleared.submission_attempt_ids
    # Late duplicate rejection is idempotent and needs no current prep lease.
    store.reject_firing_submission(ctx, pending.firing_id, attempt_id=second_attempt)
    terminal = store.fail_firing_preparation(
        ctx,
        pending.firing_id,
        owner_id="submitter-2",
        fencing_token=new_preparation.preparation_fencing_token,
    )
    assert terminal.status == "failed_preparation"

    compensated_schedule = store.create(
        ctx,
        definition_id="pipe-compensated",
        profile_name="test",
        spec=spec,
        next_fire_at=now,
    )
    compensated, _ = store.claim_firing(
        ctx,
        schedule_id=compensated_schedule.schedule_id,
        revision_id=compensated_schedule.revision_id,
        nominal_fire_time=now,
        owner_id="sched-1",
        fencing_token=lease.fencing_token,
        plan_fingerprint="managed-admission-pending",
        durable=durable,
        admit_submission=False,
    )
    first_lease, acquired = store.acquire_firing_preparation(
        ctx, compensated.firing_id, owner_id="submitter-1"
    )
    assert acquired
    store.begin_firing_submission(
        ctx,
        compensated.firing_id,
        owner_id="submitter-1",
        fencing_token=first_lease.preparation_fencing_token,
        attempt_id="compensated-first",
    )
    store.release_firing_preparation(
        ctx,
        compensated.firing_id,
        owner_id="submitter-1",
        fencing_token=first_lease.preparation_fencing_token,
    )
    second_lease, acquired = store.acquire_firing_preparation(
        ctx, compensated.firing_id, owner_id="submitter-2"
    )
    assert acquired
    store.begin_firing_submission(
        ctx,
        compensated.firing_id,
        owner_id="submitter-2",
        fencing_token=second_lease.preparation_fencing_token,
        attempt_id="compensated-second",
    )
    remaining = store.fail_firing_after_compensated_submission(
        ctx, compensated.firing_id, attempt_id="compensated-first"
    )
    assert remaining.status == "accepted"
    assert remaining.submission_attempt_ids == ("compensated-second",)
    compensated_terminal = store.fail_firing_after_compensated_submission(
        ctx, compensated.firing_id, attempt_id="compensated-second"
    )
    assert compensated_terminal.status == "failed_preparation"
    assert not compensated_terminal.submission_started
    assert not compensated_terminal.submission_attempt_ids

    failed_schedule = store.create(
        ctx,
        definition_id="pipe-failed",
        profile_name="test",
        spec=spec,
        next_fire_at=now,
    )
    unstarted, failed_created = store.claim_firing(
        ctx,
        schedule_id=failed_schedule.schedule_id,
        revision_id=failed_schedule.revision_id,
        nominal_fire_time=now,
        owner_id="sched-1",
        fencing_token=lease.fencing_token,
        plan_fingerprint="managed-admission-pending",
        durable=durable,
        admit_submission=False,
    )
    assert failed_created
    unstarted_lease, unstarted_acquired = store.acquire_firing_preparation(
        ctx, unstarted.firing_id, owner_id="submitter-2"
    )
    assert unstarted_acquired
    failed = store.fail_firing_preparation(
        ctx,
        unstarted.firing_id,
        owner_id="submitter-2",
        fencing_token=unstarted_lease.preparation_fencing_token,
    )
    assert failed.status == "failed_preparation"
    try:
        store.begin_firing_submission(
            ctx,
            unstarted.firing_id,
            owner_id="submitter-2",
            fencing_token=unstarted_lease.preparation_fencing_token,
        )
        raise AssertionError("failed firing cannot begin managed submission")
    except ControlPlaneError as exc:
        assert exc.status == 409

    paused = store.pause(ctx, created.schedule_id)
    assert paused.status == "paused"
    store.resume(ctx, created.schedule_id)
    store.delete(ctx, created.schedule_id)
    try:
        store.get(ctx, created.schedule_id)
        raise AssertionError("deleted schedule must 404")
    except ControlPlaneError as exc:
        assert exc.status == 404
    assert all(
        item.schedule_id != created.schedule_id for item in store.list_schedules(ctx)
    )
    for mutation in (store.pause, store.resume, store.delete):
        try:
            mutation(ctx, created.schedule_id)
            raise AssertionError("deleted schedule mutation must 404")
        except ControlPlaneError as exc:
            assert exc.status == 404
