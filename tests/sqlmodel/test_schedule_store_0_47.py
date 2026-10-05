# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""SQLModel ScheduleStore + migration 004."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from etlantic.control_plane import (
    ControlPlaneContext,
    DurableWorkStore,
    EnvironmentRef,
    FakeScheduleClock,
    FiringRecord,
    Principal,
    ScheduleSpec,
    ScheduleStore,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    firing_key,
)
from etlantic.control_plane.schedule_models import FiringStatus
from etlantic.runtime.scheduler_service import SchedulerService
from etlantic.testing import run_schedule_store_conformance_suite
from etlantic_sqlmodel.control_plane import (
    SQLModelDurableWorkStore,
    SQLModelScheduleStore,
    create_sqlite_engine,
)
from etlantic_sqlmodel.migrations import apply_migrations, current_version

pytestmark = pytest.mark.sqlmodel


def test_sqlmodel_schedule_store_conformance(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'sched.db'}")
    assert apply_migrations(engine) == "014_cp1_complete_principal_idempotency_0_56"
    assert current_version(engine) == "014_cp1_complete_principal_idempotency_0_56"
    run_schedule_store_conformance_suite(SQLModelScheduleStore(engine))


def test_sqlmodel_schedule_occurrence_policy_survives_store_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "schedule-occurrence-policy.db"
    engine = create_sqlite_engine(f"sqlite:///{database}")
    apply_migrations(engine)
    schedules = SQLModelScheduleStore(engine)
    ctx = ControlPlaneContext(
        principal=Principal("schedule-author"),
        tenant=TenantRef("policy-tenant"),
        workspace=WorkspaceRef("policy-tenant", "policy-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("policy-domain"),
    )
    workload = Principal(
        "nightly-scheduler", issuer="trusted-scheduler", kind="workload"
    )
    record = schedules.create(
        ctx,
        definition_id="policy-pipeline",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        revision_policy="latest-approved",
        workload_identity=workload,
        parameter_refs={"transform.limit": "param://limits/limit@v3"},
        secret_refs={
            "warehouse": {
                "provider": "vault",
                "name": "prod/warehouse",
                "key": "password",
                "version": "v7",
            }
        },
        next_fire_at="2026-10-01T12:00:00Z",
    )
    lease = schedules.acquire_leader_lease(
        ctx, owner_id="policy-scheduler", ttl_seconds=30
    )
    snapshot = {
        "selected_definition_revision_id": "defrev-approved-v3",
        "trigger_principal": workload.to_dict(),
        "parameter_fingerprint": "a" * 64,
        "reference_fingerprint": "b" * 64,
        "policy_fingerprint": "c" * 64,
    }
    firing, created = schedules.claim_firing(
        ctx,
        schedule_id=record.schedule_id,
        revision_id=record.revision_id,
        nominal_fire_time="2026-10-01T12:00:00Z",
        owner_id="policy-scheduler",
        fencing_token=lease.fencing_token,
        plan_fingerprint="managed-admission-pending",
        metadata=snapshot,
    )
    assert created
    engine.dispose()

    reopened_engine = create_sqlite_engine(f"sqlite:///{database}")
    reopened = SQLModelScheduleStore(reopened_engine)
    restored = reopened.get(ctx, record.schedule_id)
    restored_firing = reopened.list_firings(ctx, record.schedule_id)[0]
    assert restored.revision_policy == "latest-approved"
    assert restored.workload_identity == workload
    assert restored.parameter_refs == record.parameter_refs
    assert restored.secret_refs == record.secret_refs
    assert restored_firing.firing_id == firing.firing_id
    assert restored_firing.metadata == snapshot
    reopened_engine.dispose()


def test_sqlmodel_atomic_firing_with_durable(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'both.db'}")
    apply_migrations(engine)
    schedules = SQLModelScheduleStore(engine)
    durable = SQLModelDurableWorkStore(engine)
    from datetime import UTC, datetime

    from etlantic.control_plane import (
        ControlPlaneContext,
        EnvironmentRef,
        Principal,
        ScheduleSpec,
        SecurityDomain,
        TenantRef,
        WorkspaceRef,
    )

    ctx = ControlPlaneContext(
        principal=Principal("s"),
        tenant=TenantRef("t"),
        workspace=WorkspaceRef("t", "w"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("d"),
    )
    rec = schedules.create(
        ctx,
        definition_id="p",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at="2026-01-01T00:01:00Z",
    )
    lease = schedules.acquire_leader_lease(ctx, owner_id="s1", ttl_seconds=30)
    firing, created = schedules.claim_firing(
        ctx,
        schedule_id=rec.schedule_id,
        revision_id=rec.revision_id,
        nominal_fire_time="2026-01-01T00:01:00Z",
        owner_id="s1",
        fencing_token=lease.fencing_token,
        plan_fingerprint="plan",
        durable=durable,
        next_fire_at="2026-01-01T00:02:00Z",
    )
    assert created
    assert firing.submission_id
    _replay, again = schedules.claim_firing(
        ctx,
        schedule_id=rec.schedule_id,
        revision_id=rec.revision_id,
        nominal_fire_time="2026-01-01T00:01:00Z",
        owner_id="s1",
        fencing_token=lease.fencing_token,
        plan_fingerprint="plan",
        durable=durable,
    )
    assert not again
    assert len(durable.pending_outbox(ctx)) == 1
    _ = datetime, UTC


def test_sqlmodel_links_managed_occurrence_after_verified_acceptance(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'managed-link.db'}")
    apply_migrations(engine)
    schedules = SQLModelScheduleStore(engine)
    durable = SQLModelDurableWorkStore(engine)
    ctx = ControlPlaneContext(
        principal=Principal("managed-scheduler"),
        tenant=TenantRef("managed-tenant"),
        workspace=WorkspaceRef("managed-tenant", "managed-workspace"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("managed-schedule"),
    )
    pinned_revision = "definition-revision-pinned"
    nominal_fire_time = "2026-01-01T00:01:00Z"
    schedule = schedules.create(
        ctx,
        definition_id="managed-pipeline",
        profile_name="test",
        definition_revision_id=pinned_revision,
        spec=ScheduleSpec(kind="interval", interval_seconds=60, overlap="queue"),
        next_fire_at="2026-01-01T00:01:00Z",
    )
    submission, created_submission = durable.accept(
        ctx,
        idempotency_key="schedule-"
        + hashlib.sha256(
            firing_key(
                schedule.schedule_id, schedule.revision_id, nominal_fire_time
            ).encode("utf-8")
        ).hexdigest(),
        operation="run.submit",
        plan_fingerprint="f" * 64,
        revision_id=pinned_revision,
        input_snapshot='{"schema":"etlantic.execution_envelope/1"}',
    )
    assert created_submission
    firing, created_firing = schedules.claim_firing(
        ctx,
        schedule_id=schedule.schedule_id,
        revision_id=schedule.revision_id,
        nominal_fire_time=nominal_fire_time,
        owner_id="gateway",
        fencing_token=0,
        plan_fingerprint="managed-admission-pending",
        durable=durable,
        next_fire_at=schedule.next_fire_at,
        require_leader_lease=False,
        admit_submission=False,
    )
    assert created_firing
    assert firing.submission_id is None
    # A fast worker or cancellation may move CP3 past "accepted" before the
    # scheduler records its firing link. The lineage link remains valid.
    durable.cancel_submission(ctx, submission.submission_id)

    linked = schedules.link_firing_submission(
        ctx,
        firing.firing_id,
        submission_id=submission.submission_id,
        plan_fingerprint=submission.plan_fingerprint,
        durable=durable,
    )
    assert linked.submission_id == submission.submission_id
    assert linked.metadata["definition_revision_id"] == pinned_revision
    assert linked.metadata["plan_fingerprint"] == "f" * 64
    recovered = SQLModelScheduleStore(engine).list_firings(ctx, schedule.schedule_id)
    assert recovered == (linked,)
    assert len(durable.pending_outbox(ctx)) == 1


def test_sqlmodel_firing_claim_rechecks_pause_after_due_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'pause-race.db'}")
    apply_migrations(engine)
    schedules = SQLModelScheduleStore(engine)
    ctx = ControlPlaneContext(
        principal=Principal("schedule-pause-race"),
        tenant=TenantRef("pause-race-tenant"),
        workspace=WorkspaceRef("pause-race-tenant", "pause-race-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("pause-race-domain"),
    )
    due_at = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    schedule = schedules.create(
        ctx,
        definition_id="pause-race-pipeline",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at=due_at.isoformat().replace("+00:00", "Z"),
    )
    durable = SQLModelDurableWorkStore(engine)
    original_claim = cast(ScheduleStore, schedules).claim_firing
    paused = False

    def pause_then_claim(
        call_ctx: ControlPlaneContext,
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
    ) -> tuple[FiringRecord, bool]:
        nonlocal paused
        if not paused:
            paused = True
            schedules.pause(ctx, schedule.schedule_id)
        return original_claim(
            call_ctx,
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
        )

    monkeypatch.setattr(schedules, "claim_firing", pause_then_claim)
    service = SchedulerService(
        schedules,
        durable=durable,
        clock=FakeScheduleClock(due_at),
        owner_id="pause-race-scheduler",
    )

    assert service.tick(ctx) == 0
    assert schedules.get(ctx, schedule.schedule_id).status == "paused"
    assert schedules.list_firings(ctx, schedule.schedule_id) == ()
    assert durable.pending_outbox(ctx) == []
    engine.dispose()
