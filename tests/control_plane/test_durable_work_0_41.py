"""CP3 state-machine conformance for the provider-neutral reference store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EffectRecord,
    EnvironmentRef,
    MemoryDurableWorkStore,
    PreviewWorkspace,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)


def ctx(
    tenant: str = "tenant-a", workspace: str = "workspace-a"
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("worker-a", issuer="tests"),
        tenant=TenantRef(tenant),
        workspace=WorkspaceRef(tenant, workspace),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def test_accept_is_scoped_idempotent_and_creates_an_outbox_record() -> None:
    store = MemoryDurableWorkStore()
    first, created = store.accept(
        ctx(), idempotency_key="same", operation="run.submit", plan_fingerprint="plan-1"
    )
    replay, replay_created = store.accept(
        ctx(), idempotency_key="same", operation="run.submit", plan_fingerprint="plan-1"
    )
    assert created and not replay_created and replay == first
    assert store.pending_outbox(ctx())[0].submission_id == first.submission_id
    with pytest.raises(ControlPlaneError):
        store.accept(
            ctx(),
            idempotency_key="same",
            operation="run.submit",
            plan_fingerprint="plan-2",
        )
    other, other_created = store.accept(
        ctx("tenant-b", "workspace-b"),
        idempotency_key="same",
        operation="run.submit",
        plan_fingerprint="plan-2",
    )
    assert other_created and other.submission_id != first.submission_id


def test_fencing_prevents_stale_attempt_from_advancing_checkpoint() -> None:
    store = MemoryDurableWorkStore()
    submission, _ = store.accept(
        ctx(), idempotency_key="k", operation="run.submit", plan_fingerprint="plan"
    )
    first = store.acquire_lease(
        ctx(), submission.submission_id, owner_id="one", ttl_seconds=1
    )
    # Replace an expired lease deterministically without sleeping.
    store._leases[(*ctx().scope_key, submission.submission_id)] = first.__class__(
        first.submission_id,
        first.tenant_id,
        first.workspace_id,
        first.owner_id,
        first.fencing_token,
        first.acquired_at,
        "2000-01-01T00:00:00Z",
        first.heartbeat_at,
    )
    second = store.acquire_lease(
        ctx(), submission.submission_id, owner_id="two", ttl_seconds=60
    )
    attempt = store.start_attempt(
        ctx(),
        submission.submission_id,
        owner_id="two",
        fencing_token=second.fencing_token,
    )
    checkpoint = store.compare_and_swap_checkpoint(
        ctx(),
        "cursor",
        expected_version=None,
        value_fingerprint="v1",
        attempt_id=attempt.attempt_id,
        fencing_token=second.fencing_token,
    )
    assert checkpoint.version == 1
    with pytest.raises(ControlPlaneError):
        store.compare_and_swap_checkpoint(
            ctx(),
            "cursor",
            expected_version=1,
            value_fingerprint="v2",
            attempt_id=attempt.attempt_id,
            fencing_token=first.fencing_token,
        )
    store.finish_attempt(
        ctx(),
        attempt.attempt_id,
        owner_id="two",
        fencing_token=second.fencing_token,
        status="failed",
    )
    with pytest.raises(ControlPlaneError):
        store.compare_and_swap_checkpoint(
            ctx(),
            "cursor",
            expected_version=1,
            value_fingerprint="v3",
            attempt_id=attempt.attempt_id,
            fencing_token=second.fencing_token,
        )


def test_checkpoint_cas_replay_effect_and_preview_cleanup_fail_closed() -> None:
    store = MemoryDurableWorkStore()
    submission, _ = store.accept(
        ctx(),
        idempotency_key="k",
        operation="run.submit",
        plan_fingerprint="plan",
        revision_id="r1",
        plugin_fingerprint="p1",
        policy_fingerprint="policy1",
        input_snapshot="input1",
    )
    checkpoint = store.compare_and_swap_checkpoint(
        ctx(), "watermark", expected_version=None, value_fingerprint="wm1"
    )
    with pytest.raises(ControlPlaneError):
        store.compare_and_swap_checkpoint(
            ctx(), "watermark", expected_version=None, value_fingerprint="wm2"
        )
    replay = store.replay(
        ctx(), submission.submission_id, checkpoint_id=checkpoint.checkpoint_id
    )
    assert replay.plan_fingerprint == "plan" and replay.input_snapshot == "input1"
    unknown = EffectRecord(
        "effect",
        submission.submission_id,
        "tenant-a",
        "workspace-a",
        "unknown",
        datetime.now(UTC).isoformat(),
    )
    assert store.record_effect(ctx(), unknown).status == "unknown"
    committed = EffectRecord(
        "effect",
        submission.submission_id,
        "tenant-a",
        "workspace-a",
        "committed",
        datetime.now(UTC).isoformat(),
    )
    store.record_effect(ctx(), committed)
    with pytest.raises(ControlPlaneError):
        store.record_effect(ctx(), unknown)
    preview = PreviewWorkspace(
        "preview",
        "tenant-a",
        "workspace-a",
        "r1",
        "r2",
        datetime.now(UTC).isoformat(),
        (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        1,
        "code",
        "plan",
    )
    store.create_preview(ctx(), preview)
    assert store.cleanup_expired_previews(ctx())[0].cleaned_at is not None
    with pytest.raises(ControlPlaneError):
        store.create_preview(ctx("tenant-b", "workspace-b"), preview)
