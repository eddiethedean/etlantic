# pyright: reportAttributeAccessIssue=false, reportMissingImports=false, reportOptionalMemberAccess=false, reportPossiblyUnboundVariable=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Regression contracts for workspace-scoped firing deduplication."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
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


def claim(store: Any, ctx: ControlPlaneContext, durable: Any = None) -> Any:
    lease = store.acquire_leader_lease(ctx, owner_id="scheduler", ttl_seconds=60)
    return store.claim_firing(
        ctx,
        schedule_id="shared-schedule",
        revision_id="shared-revision",
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
        schedules = SQLModelScheduleStore(engine)
        durable = SQLModelDurableWorkStore(engine)
    try:
        contexts = [context("workspace-a"), context("workspace-b")]
        firings = []
        for ctx in contexts:
            schedules.create(
                ctx,
                definition_id="definition",
                profile_name="production",
                spec=ScheduleSpec(kind="interval", interval_seconds=60),
                schedule_id="shared-schedule",
            )
            firing, created = claim(schedules, ctx, durable)
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
            schedules = SQLModelScheduleStore(engine)
            durable = SQLModelDurableWorkStore(engine)
        for ctx, original in zip(contexts, firings, strict=True):
            replay, created = claim(schedules, ctx, durable)
            assert not created
            assert replay == original
            assert schedules.list_firings(ctx, "shared-schedule") == (original,)
            assert len(durable.pending_outbox(ctx)) == 1
    finally:
        if engine is not None:
            engine.dispose()


def test_legacy_snapshot_preserves_canonical_firing_and_scope() -> None:
    original_store = MemoryScheduleStore()
    original, created = claim(original_store, context("workspace-a"))
    assert created
    legacy = original_store.dump()
    legacy["firings"] = {original.logical_key: original.to_dict()}

    restored = MemoryScheduleStore()
    restored.load(legacy)
    replay, created = claim(restored, context("workspace-a"))
    assert not created
    assert replay == original
    other, created = claim(restored, context("workspace-b"))
    assert created
    assert other.workspace_id == "workspace-b"
    assert other.firing_id != original.firing_id
