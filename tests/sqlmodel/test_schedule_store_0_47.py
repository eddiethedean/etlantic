# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""SQLModel ScheduleStore + migration 004."""

from __future__ import annotations

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
    assert apply_migrations(engine) == "012_bounded_event_tombstone_retention_0_56"
    assert current_version(engine) == "012_bounded_event_tombstone_retention_0_56"
    run_schedule_store_conformance_suite(SQLModelScheduleStore(engine))


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
