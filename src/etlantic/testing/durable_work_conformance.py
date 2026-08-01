"""Durable-work provider conformance helpers (CP3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    DiffRecord,
    EffectRecord,
    EnvironmentRef,
    PreviewWorkspace,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    namespaced_checkpoint_id,
)


def _ctx(
    tenant: str = "tenant-a", workspace: str = "workspace-a"
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("worker-a", issuer="conformance"),
        tenant=TenantRef(tenant),
        workspace=WorkspaceRef(tenant, workspace),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def run_durable_work_conformance_suite(store: Any) -> None:
    """Exercise core DurableWorkStore invariants against any provider."""
    context = _ctx()
    submission, created = store.accept(
        context,
        idempotency_key="conf-1",
        operation="run.submit",
        plan_fingerprint="plan",
        schema_baseline_id="base-1",
        schema_observation_fingerprint="obs-1",
    )
    assert created
    replayed, again = store.accept(
        context,
        idempotency_key="conf-1",
        operation="run.submit",
        plan_fingerprint="plan",
        schema_baseline_id="base-1",
        schema_observation_fingerprint="obs-1",
    )
    assert not again and replayed.submission_id == submission.submission_id
    pending = store.pending_outbox(context)
    assert pending and pending[0].submission_id == submission.submission_id
    store.mark_published(context, pending[0].outbox_id)

    lease = store.acquire_lease(
        context, submission.submission_id, owner_id="host-1", ttl_seconds=30
    )
    attempt = store.start_attempt(
        context,
        submission.submission_id,
        owner_id="host-1",
        fencing_token=lease.fencing_token,
        context={"deadline": "soon"},
    )
    assert "plan_fingerprint" in attempt.context
    checkpoint_id = namespaced_checkpoint_id("cursor", "orders")
    checkpoint = store.compare_and_swap_checkpoint(
        context,
        checkpoint_id,
        expected_version=None,
        value_fingerprint="v1",
        attempt_id=attempt.attempt_id,
        fencing_token=lease.fencing_token,
        schema_baseline_id="base-1",
    )
    assert checkpoint.version == 1
    explanation = store.explain_transition(
        context, checkpoint_id, expected_version=1, value_fingerprint="v2"
    )
    assert explanation.would_succeed
    store.finish_attempt(
        context,
        attempt.attempt_id,
        owner_id="host-1",
        fencing_token=lease.fencing_token,
        status="completed",
    )
    store.release_lease(
        context,
        submission.submission_id,
        owner_id="host-1",
        fencing_token=lease.fencing_token,
    )

    unknown = EffectRecord(
        "effect-1",
        submission.submission_id,
        "tenant-a",
        "workspace-a",
        "unknown",
        datetime.now(UTC).isoformat(),
        metadata={"api_token": "secret"},
    )
    stored = store.record_effect(context, unknown)
    assert stored.metadata.get("api_token") == "***"
    try:
        store.record_effect(
            context,
            EffectRecord(
                "effect-1",
                submission.submission_id,
                "tenant-a",
                "workspace-a",
                "pending",
                datetime.now(UTC).isoformat(),
            ),
        )
        raise AssertionError("unknown effect must fail closed")
    except ControlPlaneError:
        pass

    replay = store.replay(
        context, submission.submission_id, checkpoint_id=checkpoint_id
    )
    assert replay.schema_baseline_id == "base-1"
    repair = store.plan_repair(
        context,
        submission.submission_id,
        checkpoint_id=checkpoint_id,
        invalidated_partition_ids=("p1",),
    )
    assert repair.kind == "repair" and repair.minimum_safe_closure == ("p1",)

    preview = PreviewWorkspace(
        "prev-1",
        "tenant-a",
        "workspace-a",
        "r1",
        "r2",
        datetime.now(UTC).isoformat(),
        (datetime.now(UTC) + timedelta(seconds=60)).isoformat(),
        2,
        "code",
        "plan",
        commit_ref="abc123",
    )
    store.create_preview(context, preview)
    stale = store.mark_preview_stale(context, "prev-1", code_fingerprint="other")
    assert stale.stale
    store.record_preview_diff(
        context,
        DiffRecord(
            "diff-1",
            "prev-1",
            "tenant-a",
            "workspace-a",
            datetime.now(UTC).isoformat(),
            plan_diff_fingerprint="pd",
        ),
    )
    ack = store.acknowledge_baseline(
        context,
        schema_baseline_id="base-1",
        observation_fingerprint="obs-1",
        expected_version=None,
        submission_id=submission.submission_id,
    )
    assert ack.version == 1
