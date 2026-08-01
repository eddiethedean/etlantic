"""CP3 state-machine conformance for the provider-neutral reference store."""

from __future__ import annotations

from dataclasses import replace
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
    ShadowRunRecord,
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


def test_accept_idempotency_is_issuer_qualified_and_rejects_empty_inputs() -> None:
    store = MemoryDurableWorkStore()
    first, _ = store.accept(
        ctx(), idempotency_key="same", operation="run.submit", plan_fingerprint="plan"
    )
    different_issuer = ControlPlaneContext(
        principal=Principal("worker-a", issuer="another-issuer"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "workspace-a"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )
    second, created = store.accept(
        different_issuer,
        idempotency_key="same",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    assert created and second.submission_id != first.submission_id
    assert first.principal_issuer == "tests"
    with pytest.raises(ValueError, match="plan_fingerprint"):
        store.accept(
            ctx(), idempotency_key="k", operation="run.submit", plan_fingerprint=" "
        )


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


def test_cancellation_and_terminal_state_prevent_new_execution() -> None:
    store = MemoryDurableWorkStore()
    submission, _ = store.accept(
        ctx(), idempotency_key="cancel", operation="run.submit", plan_fingerprint="plan"
    )
    assert (
        store.cancel_submission(ctx(), submission.submission_id).status
        == "cancel_requested"
    )
    with pytest.raises(ControlPlaneError, match="not eligible"):
        store.acquire_lease(
            ctx(), submission.submission_id, owner_id="one", ttl_seconds=30
        )

    completed, _ = store.accept(
        ctx(), idempotency_key="done", operation="run.submit", plan_fingerprint="plan"
    )
    lease = store.acquire_lease(
        ctx(), completed.submission_id, owner_id="one", ttl_seconds=30
    )
    attempt = store.start_attempt(
        ctx(),
        completed.submission_id,
        owner_id="one",
        fencing_token=lease.fencing_token,
    )
    with pytest.raises(ControlPlaneError, match="already has a running"):
        store.start_attempt(
            ctx(),
            completed.submission_id,
            owner_id="one",
            fencing_token=lease.fencing_token,
        )
    store.finish_attempt(
        ctx(),
        attempt.attempt_id,
        owner_id="one",
        fencing_token=lease.fencing_token,
        status="completed",
    )
    with pytest.raises(ControlPlaneError, match="not eligible"):
        store.acquire_lease(
            ctx(), completed.submission_id, owner_id="two", ttl_seconds=30
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
        reconciliation_evidence="sink query matched",
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
        (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
        1,
        "code",
        "plan",
    )
    store.create_preview(ctx(), preview)
    store._previews[(*ctx().scope_key, preview.preview_id)] = replace(
        preview, expires_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    )
    assert store.cleanup_expired_previews(ctx())[0].cleaned_at is not None
    with pytest.raises(ControlPlaneError):
        store.create_preview(ctx("tenant-b", "workspace-b"), preview)


def test_replay_rejects_another_submission_checkpoint_and_expired_preview() -> None:
    store = MemoryDurableWorkStore()
    first, _ = store.accept(
        ctx(), idempotency_key="one", operation="run.submit", plan_fingerprint="one"
    )
    second, _ = store.accept(
        ctx(), idempotency_key="two", operation="run.submit", plan_fingerprint="two"
    )
    lease = store.acquire_lease(
        ctx(), first.submission_id, owner_id="one", ttl_seconds=30
    )
    attempt = store.start_attempt(
        ctx(), first.submission_id, owner_id="one", fencing_token=lease.fencing_token
    )
    checkpoint = store.compare_and_swap_checkpoint(
        ctx(),
        "owned",
        expected_version=None,
        value_fingerprint="v1",
        attempt_id=attempt.attempt_id,
        fencing_token=lease.fencing_token,
    )
    with pytest.raises(ControlPlaneError, match="another submission"):
        store.replay(
            ctx(), second.submission_id, checkpoint_id=checkpoint.checkpoint_id
        )
    expired = PreviewWorkspace(
        "expired",
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
    with pytest.raises(ValueError, match="expiry"):
        store.create_preview(ctx(), expired)


def test_unknown_effect_cannot_be_retried_without_reconciliation() -> None:
    store = MemoryDurableWorkStore()
    submission, _ = store.accept(
        ctx(), idempotency_key="effect", operation="run.submit", plan_fingerprint="plan"
    )
    unknown = EffectRecord(
        "effect",
        submission.submission_id,
        "tenant-a",
        "workspace-a",
        "unknown",
        datetime.now(UTC).isoformat(),
        metadata={"api_token": "super-secret-token"},
    )
    stored = store.record_effect(ctx(), unknown)
    assert stored.metadata == {"api_token": "***"}
    with pytest.raises(ControlPlaneError, match="reconciliation"):
        store.record_effect(ctx(), replace(unknown, status="pending", metadata={}))
    with pytest.raises(ControlPlaneError, match="reconciliation"):
        store.record_effect(ctx(), replace(unknown, status="committed", metadata={}))
    assert (
        store.record_effect(
            ctx(),
            replace(
                unknown,
                status="committed",
                reconciliation_evidence="sink query matched",
                metadata={},
            ),
        ).status
        == "committed"
    )


def test_admission_release_repair_preview_shadow_and_conformance() -> None:
    limited = MemoryDurableWorkStore(admission_limit=1)
    first, _ = limited.accept(
        ctx(), idempotency_key="a", operation="run.submit", plan_fingerprint="plan"
    )
    with pytest.raises(ControlPlaneError, match="admission"):
        limited.accept(
            ctx(), idempotency_key="b", operation="run.submit", plan_fingerprint="plan"
        )
    lease = limited.acquire_lease(
        ctx(), first.submission_id, owner_id="one", ttl_seconds=30
    )
    attempt = limited.start_attempt(
        ctx(),
        first.submission_id,
        owner_id="one",
        fencing_token=lease.fencing_token,
        context={"deadline": "soon"},
    )
    assert attempt.context["plan_fingerprint"] == "plan"
    limited.release_lease(
        ctx(),
        first.submission_id,
        owner_id="one",
        fencing_token=lease.fencing_token,
    )
    with pytest.raises(ControlPlaneError, match="Stale"):
        limited.heartbeat(
            ctx(),
            first.submission_id,
            owner_id="one",
            fencing_token=lease.fencing_token,
            ttl_seconds=30,
        )

    store = MemoryDurableWorkStore()
    submission, _ = store.accept(
        ctx(),
        idempotency_key="repair",
        operation="run.submit",
        plan_fingerprint="plan",
        schema_baseline_id="base",
        schema_observation_fingerprint="obs",
    )
    resume = store.plan_resume(ctx(), submission.submission_id)
    assert resume.kind == "resume"
    repair = store.plan_repair(
        ctx(),
        submission.submission_id,
        invalidated_partition_ids=("p1",),
        reusable_artifact_ids=("art",),
    )
    assert repair.minimum_safe_closure == ("p1",)
    backfill = store.plan_backfill(
        ctx(), submission.submission_id, partition_ids=("p1", "p2")
    )
    assert backfill.kind == "backfill"
    explained = store.explain_transition(
        ctx(), "cursor:orders", expected_version=None, value_fingerprint="v1"
    )
    assert explained.would_succeed
    checkpoint = store.compare_and_swap_checkpoint(
        ctx(),
        "cursor:orders",
        expected_version=None,
        value_fingerprint="v1",
        schema_baseline_id="base",
    )
    assert checkpoint.schema_baseline_id == "base"
    diag = store.diagnose_checkpoint(
        ctx(), "cursor:orders", kind="corruption", detail="bad"
    )
    assert diag.kind == "corruption"
    ack = store.acknowledge_baseline(
        ctx(),
        schema_baseline_id="base",
        observation_fingerprint="obs",
        expected_version=None,
        submission_id=submission.submission_id,
    )
    with pytest.raises(ControlPlaneError, match="Baseline"):
        store.acknowledge_baseline(
            ctx(),
            schema_baseline_id="base",
            observation_fingerprint="obs2",
            expected_version=None,
        )
    assert ack.version == 1
    replay = store.replay(ctx(), submission.submission_id)
    assert replay.schema_observation_fingerprint == "obs"

    preview = PreviewWorkspace(
        "pv",
        "tenant-a",
        "workspace-a",
        "r1",
        "r2",
        datetime.now(UTC).isoformat(),
        (datetime.now(UTC) + timedelta(seconds=60)).isoformat(),
        1,
        "code",
        "plan",
        pull_request_ref="42",
    )
    store.create_preview(ctx(), preview)
    with pytest.raises(ControlPlaneError, match="quota"):
        store.create_preview(ctx(), replace(preview, preview_id="pv2"))
    stale = store.mark_preview_stale(ctx(), "pv", plan_fingerprint="other")
    assert stale.stale and "plan_fingerprint" in (stale.stale_reason or "")
    effect = store.record_effect(
        ctx(),
        EffectRecord(
            "shadow-effect",
            submission.submission_id,
            "tenant-a",
            "workspace-a",
            "committed",
            datetime.now(UTC).isoformat(),
            authoritative=False,
        ),
    )
    with pytest.raises(ControlPlaneError, match="Stale preview"):
        store.authorize_shadow_run(
            ctx(),
            ShadowRunRecord(
                "shadow",
                "pv",
                submission.submission_id,
                "tenant-a",
                "workspace-a",
                "reviewer",
                datetime.now(UTC).isoformat(),
                effect_ids=(effect.effect_id,),
            ),
        )
    # refresh non-stale preview for shadow
    store._previews[(*ctx().scope_key, "pv")] = replace(
        preview, stale=False, stale_reason=None
    )
    shadow = store.authorize_shadow_run(
        ctx(),
        ShadowRunRecord(
            "shadow",
            "pv",
            submission.submission_id,
            "tenant-a",
            "workspace-a",
            "reviewer",
            datetime.now(UTC).isoformat(),
            effect_ids=(effect.effect_id,),
        ),
    )
    assert shadow.production_authority is False
    with pytest.raises(ControlPlaneError, match="production authority"):
        store.authorize_shadow_run(
            ctx(),
            ShadowRunRecord(
                "shadow2",
                "pv",
                submission.submission_id,
                "tenant-a",
                "workspace-a",
                "reviewer",
                datetime.now(UTC).isoformat(),
                production_authority=True,
            ),
        )

    from etlantic.testing import run_durable_work_conformance_suite

    run_durable_work_conformance_suite(MemoryDurableWorkStore())
