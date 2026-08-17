"""SQLModel ScheduleStore + migration 004."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

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
    assert apply_migrations(engine) == "004_schedules_0_47"
    assert current_version(engine) == "004_schedules_0_47"
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
