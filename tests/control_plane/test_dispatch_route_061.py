from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest

from etlantic.control_plane import (
    MAX_REMOTE_RUN_ID_LENGTH,
    ControlPlaneContext,
    ControlPlaneError,
    DispatchReconciliation,
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
    execution_route_backend,
    execution_route_binding,
    validate_execution_route,
)


def _ecs_route() -> str:
    return "ecs:" + "a" * 64


def test_ecs_dispatch_codec_uses_generic_remote_identity() -> None:
    route = _ecs_route()
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/etlantic/task-id"
    record = DispatchRecord(
        submission_id="submission-1",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        execution_route=route,
        binding_fingerprint="a" * 64,
        plan_fingerprint="b" * 64,
        envelope_sha256="c" * 64,
        generation=1,
        creation_key="etlantic-idempotency-key",
        created_at="2026-10-14T12:00:00Z",
        updated_at="2026-10-14T12:00:00Z",
        status="dispatched",
        backend_kind="ecs",
        remote_run_id=task_arn,
        creation_started_at="2026-10-14T11:59:59Z",
    )

    restored = DispatchRecord.from_dict(record.to_dict())

    assert restored == record
    assert restored.remote_run_id == task_arn
    assert restored.prefect_flow_run_id is None
    assert restored.creation_started_at == "2026-10-14T11:59:59Z"
    assert execution_route_backend(route) == "ecs"
    assert execution_route_binding(route) == "a" * 64


def test_ecs_reconciliation_never_populates_prefect_alias() -> None:
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/etlantic/task-id"
    item = DispatchReconciliation(
        from_generation=1,
        to_generation=2,
        prefect_flow_run_id=None,
        authorized_at="2026-10-14T12:00:00Z",
        principal_subject="operator",
        principal_issuer="tests",
        evidence_sha256="d" * 64,
        backend_kind="ecs",
        remote_run_id=task_arn,
    )

    restored = DispatchReconciliation.from_dict(item.to_dict())

    assert restored.remote_run_id == task_arn
    assert restored.prefect_flow_run_id is None


def test_unknown_execution_backend_stays_fail_closed() -> None:
    with pytest.raises(ValueError, match="execution_route"):
        validate_execution_route("batch:" + "a" * 64)


def _durable_context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("dispatcher", issuer="tests"),
        tenant=TenantRef("dispatch-tenant"),
        workspace=WorkspaceRef("dispatch-tenant", "dispatch-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("default"),
    )


def _insert_ecs_dispatch(
    store: MemoryDurableWorkStore,
    ctx: ControlPlaneContext,
    *,
    status: Literal[
        "pending",
        "dispatched",
        "leased",
        "uncertain",
        "reconciliation_required",
        "settled",
    ],
    submission_status: Literal[
        "accepted",
        "cancel_requested",
        "cancelled",
        "completed",
        "failed",
    ] = "accepted",
    remote_run_id: str | None = None,
    lease_expires_at: str | None = None,
) -> DispatchRecord:
    route = _ecs_route()
    submission_id = "submission-ecs"
    submission = SubmissionRecord(
        submission_id=submission_id,
        tenant_id=ctx.tenant.tenant_id,
        workspace_id=ctx.workspace.workspace_id,
        principal_subject=ctx.principal.subject,
        principal_issuer=ctx.principal.issuer,
        operation="run.submit",
        idempotency_key="ecs-idempotency",
        created_at="2026-10-14T12:00:00Z",
        plan_fingerprint="b" * 64,
        input_snapshot="opaque-snapshot",
        status=submission_status,
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
        creation_key="ecs-creation-key",
        created_at="2026-10-14T12:00:00Z",
        updated_at="2026-10-14T12:00:00Z",
        status=status,
        lease_owner_id="stale-dispatcher" if status == "leased" else None,
        lease_fencing_token=1 if status == "leased" else 0,
        lease_expires_at=lease_expires_at,
        backend_kind="ecs",
        remote_run_id=remote_run_id,
        creation_started_at=(
            "2026-10-14T12:00:00Z"
            if status in {"uncertain", "leased", "reconciliation_required"}
            else None
        ),
    )
    store.load(
        {
            "submissions": {
                json.dumps([*ctx.scope_key, submission_id]): submission.to_dict()
            },
            "dispatches": {
                json.dumps([*ctx.scope_key, submission_id]): dispatch.to_dict()
            },
            "outbox": {
                json.dumps([*ctx.scope_key, "outbox-ecs"]): OutboxRecord(
                    outbox_id="outbox-ecs",
                    submission_id=submission_id,
                    tenant_id=ctx.tenant.tenant_id,
                    workspace_id=ctx.workspace.workspace_id,
                    created_at="2026-10-14T12:00:00Z",
                    payload_fingerprint="e" * 64,
                ).to_dict()
            },
        }
    )
    return dispatch


def test_stopped_ecs_dispatch_rearms_through_attempt_recovery() -> None:
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/cluster/stopped"
    dispatch = _insert_ecs_dispatch(
        store,
        ctx,
        status="dispatched",
        remote_run_id=task_arn,
    )
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

    assert (
        store.rearm_ecs_dispatch_after_remote_stop(
            ctx,
            dispatch.submission_id,
            expected_generation=dispatch.generation,
            expected_remote_run_id=task_arn,
        )
        is None
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
        expected_remote_run_id=task_arn,
    )

    assert rearmed is not None
    assert rearmed.status == "pending"
    assert rearmed.generation == dispatch.generation + 1
    assert rearmed.remote_run_id is None
    assert rearmed.last_error_code == "ecs_task_stopped_after_claim"
    assert store.list_attempts(ctx, dispatch.submission_id) == [attempt]
    assert store.get_effect(ctx, effect.effect_id) == effect
    assert (
        store.rearm_ecs_dispatch_after_remote_stop(
            ctx,
            dispatch.submission_id,
            expected_generation=dispatch.generation,
            expected_remote_run_id=task_arn,
        )
        is None
    )


def test_exhausted_ecs_dispatch_can_be_rearmed_for_managed_recovery() -> None:
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    first_task = "arn:aws:ecs:us-east-1:123456789012:task/cluster/first"
    dispatch = _insert_ecs_dispatch(
        store,
        ctx,
        status="dispatched",
        remote_run_id=first_task,
    )
    lease = store.acquire_lease(
        ctx, dispatch.submission_id, owner_id="recovery-worker", ttl_seconds=30
    )
    attempt = store.start_attempt(
        ctx,
        dispatch.submission_id,
        owner_id="recovery-worker",
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
        owner_id="recovery-worker",
        fencing_token=lease.fencing_token,
    )
    store.release_lease(
        ctx,
        dispatch.submission_id,
        owner_id="recovery-worker",
        fencing_token=lease.fencing_token,
    )

    current = store.rearm_ecs_dispatch_after_remote_stop(
        ctx,
        dispatch.submission_id,
        expected_generation=1,
        expected_remote_run_id=first_task,
    )
    assert current is not None and current.generation == 2
    for generation in (2, 3):
        claim = store.claim_dispatch(
            ctx, dispatch.submission_id, owner_id=f"dispatcher-{generation}"
        )
        assert claim is not None
        task_arn = f"arn:aws:ecs:us-east-1:123456789012:task/cluster/task-{generation}"
        store.link_dispatch(
            ctx,
            dispatch.submission_id,
            owner_id=f"dispatcher-{generation}",
            fencing_token=claim.lease_fencing_token,
            remote_run_id=task_arn,
        )
        current = store.rearm_ecs_dispatch_after_remote_stop(
            ctx,
            dispatch.submission_id,
            expected_generation=generation,
            expected_remote_run_id=task_arn,
        )
        assert current is not None

    assert current.status == "reconciliation_required"
    reconciled = store.rearm_reconciliation_required_dispatch(
        ctx,
        dispatch.submission_id,
        expected_generation=current.generation,
        expected_remote_run_id=task_arn,
        evidence_sha256="d" * 64,
    )

    assert reconciled.status == "pending"
    assert reconciled.generation == 4
    assert reconciled.reconciliation_history[-1].evidence_sha256 == "d" * 64
    assert store.list_attempts(ctx, dispatch.submission_id)[0].attempt_id == (
        attempt.attempt_id
    )
    assert store.get_effect(ctx, effect.effect_id) == effect


def test_terminal_unlinked_ecs_dispatch_settles_only_after_attempt_finishes() -> None:
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    dispatch = _insert_ecs_dispatch(store, ctx, status="uncertain")
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

    assert (
        store.settle_terminal_ecs_dispatch(
            ctx,
            dispatch.submission_id,
            expected_generation=dispatch.generation,
        )
        is None
    )
    store.release_lease(
        ctx,
        dispatch.submission_id,
        owner_id="fast-worker",
        fencing_token=lease.fencing_token,
    )
    assert (
        store.settle_terminal_ecs_dispatch(
            ctx,
            dispatch.submission_id,
            expected_generation=dispatch.generation,
        )
        is None
    )
    assert (
        store.execution_route_workload(ctx, dispatch.execution_route).drained is False
    )
    store.mark_published(ctx, "outbox-ecs")

    candidates = store.dispatched_for_reconciliation(
        ctx,
        execution_route=dispatch.execution_route,
        limit=10,
    )
    assert [item.submission_id for item in candidates] == [dispatch.submission_id]
    settled = store.settle_terminal_ecs_dispatch(
        ctx,
        dispatch.submission_id,
        expected_generation=dispatch.generation,
    )

    assert settled is not None
    assert settled.status == "settled"
    assert settled.remote_run_id is None
    workload = store.execution_route_workload(ctx, dispatch.execution_route)
    assert workload.incomplete_dispatches == 0
    assert workload.drained is True


def test_terminal_ecs_dispatch_without_attempt_cannot_be_settled() -> None:
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    dispatch = _insert_ecs_dispatch(
        store,
        ctx,
        status="uncertain",
        submission_status="completed",
    )

    assert (
        store.settle_terminal_ecs_dispatch(
            ctx,
            dispatch.submission_id,
            expected_generation=dispatch.generation,
        )
        is None
    )
    assert store.get_dispatch(ctx, dispatch.submission_id).status == "uncertain"


def test_linked_ecs_terminal_dispatch_remains_reconcilable_until_outbox_cleanup() -> (
    None
):
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    dispatch = _insert_ecs_dispatch(
        store,
        ctx,
        status="dispatched",
        submission_status="completed",
        remote_run_id="arn:aws:ecs:us-east-1:123456789012:task/cluster/completed",
    )

    candidates = store.dispatched_for_reconciliation(
        ctx, execution_route=dispatch.execution_route, limit=10
    )

    assert [item.submission_id for item in candidates] == [dispatch.submission_id]
    assert store.pending_outbox(
        ctx,
        execution_route=dispatch.execution_route,
        terminal_only=True,
        submission_id=dispatch.submission_id,
    )
    store.mark_published(ctx, "outbox-ecs")
    assert not store.dispatched_for_reconciliation(
        ctx, execution_route=dispatch.execution_route, limit=10
    )


def test_expired_ecs_lease_remains_recoverable_after_cancellation() -> None:
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    dispatch = _insert_ecs_dispatch(
        store,
        ctx,
        status="leased",
        submission_status="cancel_requested",
        lease_expires_at="2000-01-01T00:00:00Z",
    )

    pending = store.pending_dispatches(
        ctx, execution_route=dispatch.execution_route, limit=1
    )
    assert [item.submission_id for item in pending] == [dispatch.submission_id]

    claim = store.claim_dispatch(ctx, dispatch.submission_id, owner_id="recovery")
    assert claim is not None
    assert claim.status == "leased"
    assert claim.lease_fencing_token == 2


@pytest.mark.parametrize(
    ("status", "remote_run_id"),
    [
        ("uncertain", None),
        ("leased", None),
        ("reconciliation_required", None),
        (
            "dispatched",
            "arn:aws:ecs:us-east-1:123456789012:task/cluster/task-1",
        ),
    ],
)
def test_ecs_cancellation_stays_open_until_remote_identity_is_resolved(
    status: Literal["uncertain", "leased", "reconciliation_required", "dispatched"],
    remote_run_id: str | None,
) -> None:
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    dispatch = _insert_ecs_dispatch(
        store,
        ctx,
        status=status,
        submission_status="cancel_requested",
        remote_run_id=remote_run_id,
        lease_expires_at="2000-01-01T00:00:00Z" if status == "leased" else None,
    )

    assert store.reconcile_cancelled_submissions(ctx, limit=1) == []
    assert (
        store.get_submission(ctx, dispatch.submission_id).status == "cancel_requested"
    )
    assert store.get_dispatch(ctx, dispatch.submission_id).status == status
    if status != "dispatched":
        pending = store.pending_dispatches(
            ctx, execution_route=dispatch.execution_route, limit=1
        )
        assert [item.submission_id for item in pending] == [dispatch.submission_id]


def test_ecs_dispatch_persists_task_arns_for_long_cluster_names() -> None:
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    dispatch = _insert_ecs_dispatch(store, ctx, status="pending")
    cluster_name = "c" * 200
    task_arn = f"arn:aws:ecs:us-east-1:123456789012:task/{cluster_name}/{'a' * 32}"
    assert len(task_arn) > 256
    assert len(task_arn) <= MAX_REMOTE_RUN_ID_LENGTH

    now = datetime(2026, 10, 15, 12, tzinfo=UTC)
    claim = store.claim_dispatch(
        ctx, dispatch.submission_id, owner_id="long-arn", now=now
    )
    assert claim is not None
    linked = store.link_dispatch(
        ctx,
        dispatch.submission_id,
        owner_id="long-arn",
        fencing_token=claim.lease_fencing_token,
        remote_run_id=task_arn,
        now=now,
    )

    restored = MemoryDurableWorkStore()
    restored.load(store.dump())
    assert restored.get_dispatch(ctx, dispatch.submission_id).remote_run_id == task_arn
    assert DispatchRecord.from_dict(linked.to_dict()) == linked


def test_ecs_uncertain_dispatch_expires_and_operator_rearm_starts_new_token_window() -> (
    None
):
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    dispatch = _insert_ecs_dispatch(store, ctx, status="pending")
    first_attempt = datetime(2026, 10, 14, 12, tzinfo=UTC)

    claim = store.claim_dispatch(
        ctx, dispatch.submission_id, owner_id="ecs-worker", now=first_attempt
    )
    assert claim is not None
    assert claim.creation_started_at == "2026-10-14T12:00:00Z"
    uncertain = store.release_dispatch(
        ctx,
        dispatch.submission_id,
        owner_id="ecs-worker",
        fencing_token=claim.lease_fencing_token,
        outcome_uncertain=True,
        error_code="ecs_run_task_uncertain",
        now=first_attempt,
    )
    assert uncertain.status == "uncertain"

    expired = store.quarantine_expired_ecs_dispatch(
        ctx,
        dispatch.submission_id,
        expected_generation=1,
        expected_creation_started_at=claim.creation_started_at,
        safe_retry_deadline=first_attempt + timedelta(hours=23),
        now=first_attempt + timedelta(hours=24),
    )
    assert expired.status == "reconciliation_required"
    assert expired.remote_run_id is None

    rearmed = store.rearm_reconciliation_required_dispatch(
        ctx,
        dispatch.submission_id,
        expected_generation=1,
        expected_remote_run_id=None,
        evidence_sha256="d" * 64,
        now=first_attempt + timedelta(hours=24),
    )
    assert rearmed.generation == 2
    assert rearmed.status == "pending"
    assert rearmed.creation_started_at is None


def test_expired_ecs_token_can_be_quarantined_under_its_live_claim() -> None:
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    created = datetime(2026, 10, 14, 12, tzinfo=UTC)
    dispatch = _insert_ecs_dispatch(store, ctx, status="uncertain")
    claim = store.claim_dispatch(
        ctx,
        dispatch.submission_id,
        owner_id="ecs-worker",
        now=created + timedelta(minutes=49),
    )
    assert claim is not None

    with pytest.raises(ValueError, match="owner_id and fencing_token"):
        store.quarantine_expired_ecs_dispatch(
            ctx,
            dispatch.submission_id,
            expected_generation=claim.generation,
            expected_creation_started_at=claim.creation_started_at,
            safe_retry_deadline=created + timedelta(minutes=50),
            owner_id="ecs-worker",
            now=created + timedelta(hours=2),
        )
    with pytest.raises(ControlPlaneError, match="lease was lost"):
        store.quarantine_expired_ecs_dispatch(
            ctx,
            dispatch.submission_id,
            expected_generation=claim.generation,
            expected_creation_started_at=claim.creation_started_at,
            safe_retry_deadline=created + timedelta(minutes=50),
            owner_id="stale-worker",
            fencing_token=claim.lease_fencing_token,
            now=created + timedelta(hours=2),
        )

    quarantined = store.quarantine_expired_ecs_dispatch(
        ctx,
        dispatch.submission_id,
        expected_generation=claim.generation,
        expected_creation_started_at=claim.creation_started_at,
        safe_retry_deadline=created + timedelta(minutes=50),
        owner_id="ecs-worker",
        fencing_token=claim.lease_fencing_token,
        now=created + timedelta(hours=2),
    )

    assert quarantined.status == "reconciliation_required"
    assert quarantined.lease_owner_id is None


def test_cancelled_ecs_submission_waits_until_stopped_is_durably_confirmed() -> None:
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    dispatch = _insert_ecs_dispatch(
        store,
        ctx,
        status="dispatched",
        submission_status="cancel_requested",
        remote_run_id="arn:aws:ecs:us-east-1:123456789012:task/cluster/task-1",
    )

    assert store.reconcile_cancelled_submissions(ctx, limit=1) == []
    assert (
        store.get_submission(ctx, dispatch.submission_id).status == "cancel_requested"
    )

    cancelled = store.confirm_dispatch_cancelled(
        ctx,
        dispatch.submission_id,
        expected_generation=dispatch.generation,
        expected_remote_run_id=dispatch.remote_run_id or "",
    )
    assert cancelled.status == "cancelled"
    assert [
        item.submission_id
        for item in store.reconcile_cancelled_submissions(ctx, limit=1)
    ] == [dispatch.submission_id]
    assert store.get_submission(ctx, dispatch.submission_id).status == "cancelled"


def test_stopped_ecs_cancellation_waits_for_execution_lease_cleanup() -> None:
    ctx = _durable_context()
    store = MemoryDurableWorkStore()
    dispatch = _insert_ecs_dispatch(
        store,
        ctx,
        status="dispatched",
        remote_run_id="arn:aws:ecs:us-east-1:123456789012:task/cluster/task-lease",
    )
    lease = store.acquire_lease(
        ctx, dispatch.submission_id, owner_id="stopped-worker", ttl_seconds=30
    )
    store.start_attempt(
        ctx,
        dispatch.submission_id,
        owner_id="stopped-worker",
        fencing_token=lease.fencing_token,
    )
    store.cancel_submission(ctx, dispatch.submission_id)

    waiting = store.confirm_dispatch_cancelled(
        ctx,
        dispatch.submission_id,
        expected_generation=dispatch.generation,
        expected_remote_run_id=dispatch.remote_run_id or "",
    )
    assert waiting.status == "dispatched"
    assert waiting.last_error_code == "ecs_cancel_waiting_for_execution_lease"
    assert store.reconcile_cancelled_submissions(ctx, limit=1) == []

    store.release_lease(
        ctx,
        dispatch.submission_id,
        owner_id="stopped-worker",
        fencing_token=lease.fencing_token,
    )
    confirmed = store.confirm_dispatch_cancelled(
        ctx,
        dispatch.submission_id,
        expected_generation=dispatch.generation,
        expected_remote_run_id=dispatch.remote_run_id or "",
    )
    assert confirmed.status == "cancelled"
    assert [
        item.submission_id
        for item in store.dispatched_for_reconciliation(
            ctx, execution_route=dispatch.execution_route, limit=10
        )
    ] == [dispatch.submission_id]
    assert [
        item.submission_id
        for item in store.reconcile_cancelled_submissions(ctx, limit=1)
    ] == [dispatch.submission_id]
    assert store.list_attempts(ctx, dispatch.submission_id)[0].status == "lost"
    assert (
        store.get_effect(ctx, f"{dispatch.submission_id}:execution").status == "unknown"
    )
