# pyright: reportAttributeAccessIssue=false, reportMissingImports=false, reportOptionalMemberAccess=false, reportPossiblyUnboundVariable=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Regression contracts for workspace-scoped firing deduplication."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    MemoryDurableWorkStore,
    MemoryScheduleStore,
    Principal,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)


def context(workspace: str) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("scheduler"),
        tenant=TenantRef("tenant"),
        workspace=WorkspaceRef("tenant", workspace),
        environment=EnvironmentRef("production"),
        security_domain=SecurityDomain("default"),
    )


def claim(
    store: Any,
    ctx: ControlPlaneContext,
    revision_id: str,
    durable: Any = None,
) -> Any:
    lease = store.acquire_leader_lease(ctx, owner_id="scheduler", ttl_seconds=60)
    return store.claim_firing(
        ctx,
        schedule_id="shared-schedule",
        revision_id=revision_id,
        nominal_fire_time="2026-09-13T00:00:00Z",
        owner_id="scheduler",
        fencing_token=lease.fencing_token,
        plan_fingerprint="plan",
        durable=durable,
    )


@pytest.mark.parametrize("provider", ["memory", "sqlmodel", "postgresql"])
def test_firing_and_durable_submission_are_scoped(
    provider: str, tmp_path: Path
) -> None:
    engine = None
    store_id = f"firing-scope-{os.urandom(6).hex()}"
    if provider == "memory":
        schedules = MemoryScheduleStore()
        durable = MemoryDurableWorkStore()
    else:
        pytest.importorskip("etlantic_sqlmodel")
        from etlantic_sqlmodel.control_plane import (
            SQLModelDurableWorkStore,
            SQLModelScheduleStore,
            create_sqlite_engine,
        )
        from etlantic_sqlmodel.migrations import upgrade

        if provider == "postgresql":
            from sqlalchemy import create_engine

            url = os.environ.get("ETLANTIC_SCOPE_TEST_DATABASE_URL")
            if not url:
                pytest.skip("ETLANTIC_SCOPE_TEST_DATABASE_URL is not configured")

            def make_engine() -> Any:
                return create_engine(url)

        else:
            url = f"sqlite:///{tmp_path / 'scoped.db'}"

            def make_engine() -> Any:
                return create_sqlite_engine(url)

        engine = make_engine()
        upgrade(engine)
        schedules = SQLModelScheduleStore(engine, store_id=store_id)
        durable = SQLModelDurableWorkStore(engine, store_id=store_id)
    try:
        contexts = [context("workspace-a"), context("workspace-b")]
        firings: list[Any] = []
        for ctx in contexts:
            schedule = schedules.create(
                ctx,
                definition_id="definition",
                profile_name="production",
                spec=ScheduleSpec(kind="interval", interval_seconds=60),
                schedule_id="shared-schedule",
            )
            firing, created = claim(schedules, ctx, schedule.revision_id, durable)
            assert created
            assert firing.workspace_id == ctx.workspace.workspace_id
            assert len(durable.pending_outbox(ctx)) == 1
            firings.append(firing)
        assert firings[0].firing_id != firings[1].firing_id
        assert firings[0].submission_id != firings[1].submission_id

        if provider == "memory":
            snapshot = schedules.dump()
            schedules = MemoryScheduleStore()
            schedules.load(snapshot)
        else:
            engine.dispose()
            engine = make_engine()
            schedules = SQLModelScheduleStore(engine, store_id=store_id)
            durable = SQLModelDurableWorkStore(engine, store_id=store_id)
        for ctx, original in zip(contexts, firings, strict=True):
            replay, created = claim(schedules, ctx, original.revision_id, durable)
            assert not created
            assert replay == original
            assert schedules.list_firings(ctx, "shared-schedule") == (original,)
            assert len(durable.pending_outbox(ctx)) == 1
    finally:
        if engine is not None:
            engine.dispose()


def test_legacy_snapshot_preserves_canonical_firing_and_scope() -> None:
    original_store = MemoryScheduleStore()
    first_ctx = context("workspace-a")
    first_schedule = original_store.create(
        first_ctx,
        definition_id="definition",
        profile_name="production",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        schedule_id="shared-schedule",
    )
    original, created = claim(original_store, first_ctx, first_schedule.revision_id)
    assert created
    legacy = original_store.dump()
    legacy["firings"] = {original.logical_key: original.to_dict()}

    restored = MemoryScheduleStore()
    restored.load(legacy)
    replay, created = claim(restored, first_ctx, original.revision_id)
    assert not created
    assert replay == original
    other_ctx = context("workspace-b")
    other_schedule = restored.create(
        other_ctx,
        definition_id="definition",
        profile_name="production",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        schedule_id="shared-schedule",
    )
    other, created = claim(restored, other_ctx, other_schedule.revision_id)
    assert created
    assert other.workspace_id == "workspace-b"
    assert other.firing_id != original.firing_id


@pytest.mark.parametrize("provider", ["memory", "sqlite", "postgresql"])
def test_pause_after_due_scan_blocks_stale_firing_claim(
    provider: str, tmp_path: Path
) -> None:
    engine = None
    store_id = f"phase056-pause-race-{provider}-{os.urandom(6).hex()}"
    if provider == "memory":
        schedules = MemoryScheduleStore()
        durable = MemoryDurableWorkStore()
    else:
        pytest.importorskip("etlantic_sqlmodel")
        from etlantic_sqlmodel.control_plane import (
            SQLModelDurableWorkStore,
            SQLModelScheduleStore,
            create_sqlite_engine,
        )
        from etlantic_sqlmodel.migrations import upgrade

        if provider == "postgresql":
            from sqlalchemy import create_engine

            url = os.environ.get("ETLANTIC_SCOPE_TEST_DATABASE_URL")
            if not url:
                pytest.skip("ETLANTIC_SCOPE_TEST_DATABASE_URL is not configured")
            engine = create_engine(url)
        else:
            engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'pause-race.db'}")
        upgrade(engine)
        schedules = SQLModelScheduleStore(engine, store_id=store_id)
        durable = SQLModelDurableWorkStore(engine, store_id=store_id)

    ctx = context("pause-race-workspace")
    schedule_id = f"pause-race-{provider}-{os.urandom(6).hex()}"
    try:
        schedule = schedules.create(
            ctx,
            definition_id="definition",
            profile_name="production",
            spec=ScheduleSpec(kind="interval", interval_seconds=60),
            schedule_id=schedule_id,
            next_fire_at="2026-01-01T00:00:00Z",
        )
        leader = schedules.acquire_leader_lease(
            ctx, owner_id="scheduler", ttl_seconds=60
        )
        scanned = schedules.due_schedules(ctx, now="2026-01-01T00:00:01Z")
        assert [item.schedule_id for item in scanned] == [schedule_id]

        paused = schedules.pause(ctx, schedule_id)
        assert paused.status == "paused"
        assert paused.revision_id == schedule.revision_id
        with pytest.raises(ControlPlaneError) as rejected:
            schedules.claim_firing(
                ctx,
                schedule_id=schedule_id,
                revision_id=scanned[0].revision_id,
                nominal_fire_time="2026-01-01T00:00:00Z",
                owner_id=leader.owner_id,
                fencing_token=leader.fencing_token,
                plan_fingerprint="f" * 64,
                durable=durable,
            )
        assert rejected.value.extensions.get("reason") == "schedule_not_active"
        assert schedules.list_firings(ctx, schedule_id) == ()
        assert not durable.pending_outbox(ctx)

        resumed = schedules.resume(ctx, schedule_id)
        assert resumed.status == "active"
        assert resumed.revision_id == schedule.revision_id
        firing, created = schedules.claim_firing(
            ctx,
            schedule_id=schedule_id,
            revision_id=scanned[0].revision_id,
            nominal_fire_time="2026-01-01T00:00:00Z",
            owner_id=leader.owner_id,
            fencing_token=leader.fencing_token,
            plan_fingerprint="f" * 64,
            durable=durable,
        )
        assert created
        assert firing.revision_id == schedule.revision_id
        assert firing.submission_id is not None
        assert len(durable.pending_outbox(ctx)) == 1

        with pytest.raises(ControlPlaneError) as active_amendment:
            schedules.amend(
                ctx,
                schedule_id,
                expected_revision_id=schedule.revision_id,
                spec=ScheduleSpec(kind="interval", interval_seconds=120),
                next_fire_at="2026-01-01T00:01:00Z",
                durable=durable,
            )
        assert active_amendment.value.extensions.get("reason") == "active_firing"
        with pytest.raises(ControlPlaneError) as stale_amendment:
            schedules.amend(
                ctx,
                schedule_id,
                expected_revision_id="stale-revision",
                spec=ScheduleSpec(kind="interval", interval_seconds=120),
                next_fire_at="2026-01-01T00:01:00Z",
                durable=durable,
            )
        assert stale_amendment.value.extensions.get("reason") == "stale_revision"

        worker_lease = durable.acquire_lease(
            ctx,
            firing.submission_id,
            owner_id="schedule-worker",
            ttl_seconds=60,
        )
        attempt = durable.start_attempt(
            ctx,
            firing.submission_id,
            owner_id=worker_lease.owner_id,
            fencing_token=worker_lease.fencing_token,
        )
        durable.finish_attempt(
            ctx,
            attempt.attempt_id,
            owner_id=worker_lease.owner_id,
            fencing_token=worker_lease.fencing_token,
            status="completed",
        )

        amended = schedules.amend(
            ctx,
            schedule_id,
            expected_revision_id=schedule.revision_id,
            spec=ScheduleSpec(kind="interval", interval_seconds=120),
            next_fire_at="2026-01-01T00:01:00Z",
            durable=durable,
        )
        assert amended.revision_id != schedule.revision_id
        assert amended.metadata["amends_revision_id"] == schedule.revision_id
        assert amended.spec.interval_seconds == 120
        assert amended.status == "active"
        assert schedules.list_firings(ctx, schedule_id) == (firing,)
        with pytest.raises(ControlPlaneError) as stale_firing:
            schedules.claim_firing(
                ctx,
                schedule_id=schedule_id,
                revision_id=schedule.revision_id,
                nominal_fire_time="2026-01-01T00:01:00Z",
                owner_id=leader.owner_id,
                fencing_token=leader.fencing_token,
                plan_fingerprint="f" * 64,
                durable=durable,
            )
        assert stale_firing.value.extensions.get("reason") == "stale_revision"
    finally:
        if engine is not None:
            engine.dispose()
