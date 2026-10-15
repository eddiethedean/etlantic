"""SQLModel persistence for fenced ECS dispatch recovery (0.61)."""

from __future__ import annotations

import json
from typing import Literal

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from etlantic.control_plane import (
    ControlPlaneContext,
    DispatchRecord,
    EffectRecord,
    EnvironmentRef,
    MemoryDurableWorkStore,
    OutboxRecord,
    Principal,
    SecurityDomain,
    SubmissionRecord,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel.control_plane import (
    SQLModelDurableWorkStore,
    create_durable_tables,
)
from sqlmodel import Session

pytestmark = pytest.mark.sqlmodel


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("ecs-recovery-test", issuer="tests"),
        tenant=TenantRef("ecs-recovery-tenant"),
        workspace=WorkspaceRef("ecs-recovery-tenant", "ecs-recovery-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("internal"),
    )


def _store_with_dispatch(
    *,
    status: Literal["dispatched", "uncertain"],
    remote_run_id: str | None,
) -> tuple[Engine, SQLModelDurableWorkStore, ControlPlaneContext, DispatchRecord]:
    engine = create_engine("sqlite://")
    create_durable_tables(engine)
    store = SQLModelDurableWorkStore(engine, store_id=f"ecs-recovery-{status}")
    ctx = _ctx()
    route = "ecs:" + "a" * 64
    submission_id = f"submission-{status}"
    timestamp = "2026-10-14T12:00:00Z"
    submission = SubmissionRecord(
        submission_id=submission_id,
        tenant_id=ctx.tenant.tenant_id,
        workspace_id=ctx.workspace.workspace_id,
        principal_subject=ctx.principal.subject,
        principal_issuer=ctx.principal.issuer,
        operation="run.submit",
        idempotency_key=f"idempotency-{status}",
        created_at=timestamp,
        plan_fingerprint="b" * 64,
        status="accepted",
        execution_route=route,
    )
    dispatch = DispatchRecord(
        submission_id=submission_id,
        tenant_id=ctx.tenant.tenant_id,
        workspace_id=ctx.workspace.workspace_id,
        execution_route=route,
        binding_fingerprint="a" * 64,
        plan_fingerprint="b" * 64,
        envelope_sha256="c" * 64,
        generation=1,
        creation_key=f"creation-{status}",
        created_at=timestamp,
        updated_at=timestamp,
        status=status,
        backend_kind="ecs",
        remote_run_id=remote_run_id,
    )

    def seed(memory: MemoryDurableWorkStore) -> None:
        memory.load(
            {
                "submissions": {
                    json.dumps([*ctx.scope_key, submission_id]): submission.to_dict()
                },
                "dispatches": {
                    json.dumps([*ctx.scope_key, submission_id]): dispatch.to_dict()
                },
                "outbox": {
                    json.dumps([*ctx.scope_key, f"outbox-{status}"]): OutboxRecord(
                        outbox_id=f"outbox-{status}",
                        submission_id=submission_id,
                        tenant_id=ctx.tenant.tenant_id,
                        workspace_id=ctx.workspace.workspace_id,
                        created_at=timestamp,
                        payload_fingerprint="d" * 64,
                    ).to_dict()
                },
            }
        )

    with Session(engine) as session:
        store.apply_in_transaction(session, seed)
        session.commit()
    return engine, store, ctx, dispatch


def test_sqlmodel_rearms_stopped_ecs_dispatch_with_attempt_history() -> None:
    engine, store, ctx, dispatch = _store_with_dispatch(
        status="dispatched",
        remote_run_id="arn:aws:ecs:us-east-1:123456789012:task/cluster/stopped",
    )
    try:
        lease = store.acquire_lease(
            ctx, dispatch.submission_id, owner_id="stopped-worker", ttl_seconds=30
        )
        attempt = store.start_attempt(
            ctx,
            dispatch.submission_id,
            owner_id="stopped-worker",
            fencing_token=lease.fencing_token,
        )
        effect = EffectRecord(
            effect_id=f"{dispatch.submission_id}:execution",
            submission_id=dispatch.submission_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            status="unknown",
            recorded_at="2026-10-14T12:01:00Z",
        )
        store.record_attempt_effect(
            ctx,
            effect,
            attempt_id=attempt.attempt_id,
            owner_id="stopped-worker",
            fencing_token=lease.fencing_token,
        )
        store.release_lease(
            ctx,
            dispatch.submission_id,
            owner_id="stopped-worker",
            fencing_token=lease.fencing_token,
        )

        rearmed = store.rearm_ecs_dispatch_after_remote_stop(
            ctx,
            dispatch.submission_id,
            expected_generation=dispatch.generation,
            expected_remote_run_id=str(dispatch.remote_run_id),
        )

        assert rearmed is not None
        assert rearmed.generation == dispatch.generation + 1
        assert rearmed.status == "pending"
        assert store.list_attempts(ctx, dispatch.submission_id) == [attempt]
        assert store.get_effect(ctx, effect.effect_id) == effect
    finally:
        engine.dispose()


def test_sqlmodel_settles_unlinked_ecs_dispatch_after_terminal_attempt() -> None:
    engine, store, ctx, dispatch = _store_with_dispatch(
        status="uncertain",
        remote_run_id=None,
    )
    try:
        lease = store.acquire_lease(
            ctx, dispatch.submission_id, owner_id="fast-worker", ttl_seconds=30
        )
        attempt = store.start_attempt(
            ctx,
            dispatch.submission_id,
            owner_id="fast-worker",
            fencing_token=lease.fencing_token,
        )
        store.finish_attempt(
            ctx,
            attempt.attempt_id,
            owner_id="fast-worker",
            fencing_token=lease.fencing_token,
            status="completed",
        )
        store.release_lease(
            ctx,
            dispatch.submission_id,
            owner_id="fast-worker",
            fencing_token=lease.fencing_token,
        )
        store.mark_published(ctx, "outbox-uncertain")

        settled = store.settle_terminal_ecs_dispatch(
            ctx,
            dispatch.submission_id,
            expected_generation=dispatch.generation,
        )

        assert settled is not None
        assert settled.status == "settled"
        assert store.execution_route_workload(ctx, dispatch.execution_route).drained
    finally:
        engine.dispose()
