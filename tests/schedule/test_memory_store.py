"""Memory ScheduleStore conformance."""

from __future__ import annotations

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryScheduleStore,
    Principal,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.testing import run_schedule_store_conformance_suite


def test_memory_schedule_store_conformance() -> None:
    run_schedule_store_conformance_suite(MemoryScheduleStore())


def test_legacy_submission_fence_survives_new_attempt_rejection() -> None:
    store = MemoryScheduleStore()
    ctx = ControlPlaneContext(
        principal=Principal("scheduler"),
        tenant=TenantRef("tenant"),
        workspace=WorkspaceRef("tenant", "workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("domain"),
    )
    nominal = "2026-10-01T12:00:00Z"
    schedule = store.create(
        ctx,
        definition_id="pipe",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at=nominal,
    )
    firing, _ = store.claim_firing(
        ctx,
        schedule_id=schedule.schedule_id,
        revision_id=schedule.revision_id,
        nominal_fire_time=nominal,
        owner_id="scheduler",
        fencing_token=0,
        plan_fingerprint="managed-admission-pending",
        require_leader_lease=False,
        admit_submission=False,
    )
    snapshot = store.dump()
    for row in snapshot["firings"].values():
        row["schema"] = "etlantic.firing/3"
        row["submission_started"] = True
        del row["submission_attempt_ids"]
    restored = MemoryScheduleStore()
    restored.load(snapshot)
    preparation, acquired = restored.acquire_firing_preparation(
        ctx, firing.firing_id, owner_id="new-owner"
    )
    assert acquired
    restored.begin_firing_submission(
        ctx,
        firing.firing_id,
        owner_id="new-owner",
        fencing_token=preparation.preparation_fencing_token,
        attempt_id="new-attempt",
    )
    rejected = restored.reject_firing_submission(
        ctx, firing.firing_id, attempt_id="new-attempt"
    )
    assert rejected.submission_started
    assert rejected.submission_attempt_ids == ("legacy-untracked-admission",)


def test_local_submission_fence_survives_legacy_schedule_snapshot_writer() -> None:
    store = MemoryScheduleStore()
    ctx = ControlPlaneContext(
        principal=Principal("scheduler"),
        tenant=TenantRef("tenant"),
        workspace=WorkspaceRef("tenant", "workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("domain"),
    )
    nominal = "2026-10-01T12:00:00Z"
    schedule = store.create(
        ctx,
        definition_id="pipe",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at=nominal,
    )
    firing, _ = store.claim_firing(
        ctx,
        schedule_id=schedule.schedule_id,
        revision_id=schedule.revision_id,
        nominal_fire_time=nominal,
        owner_id="scheduler",
        fencing_token=0,
        plan_fingerprint="managed-admission-pending",
        require_leader_lease=False,
        admit_submission=False,
    )
    preparation, acquired = store.acquire_firing_preparation(
        ctx, firing.firing_id, owner_id="submitter"
    )
    assert acquired
    store.begin_firing_submission(
        ctx,
        firing.firing_id,
        owner_id="submitter",
        fencing_token=preparation.preparation_fencing_token,
        attempt_id="in-flight-admission",
    )

    snapshot = store.dump()
    row = next(iter(snapshot["schedules"].values()))
    assert row["revision_policy"] == "admission_fenced"
    assert row["timer_revision_policy"] == "pinned"
    # 0.58 accepts only pinned/latest-approved here, so its reader fails closed.
    assert row["revision_policy"] not in {"pinned", "latest-approved"}

    restored = MemoryScheduleStore()
    restored.load(snapshot)
    pending = restored.list_firings(ctx, schedule.schedule_id)[0]
    assert pending.submission_started
    assert pending.submission_attempt_ids == ("in-flight-admission",)

    restored.reject_firing_submission(
        ctx, firing.firing_id, attempt_id="in-flight-admission"
    )
    unfenced_row = next(iter(restored.dump()["schedules"].values()))
    assert unfenced_row["revision_policy"] == "pinned"
