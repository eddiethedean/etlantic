"""CP4 erasure / audit / objective / attestation conformance helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    DeliveryObjective,
    EnvironmentRef,
    MemoryAttestationStore,
    MemoryAuditEvidenceStore,
    MemoryErasureProvider,
    MemoryErasureStore,
    MemoryObjectiveStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    assert_no_subject_values,
    memory_webhook_provider,
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


def run_cp4_governance_conformance_suite(
    *,
    erasure: Any | None = None,
    audit: Any | None = None,
    objectives: Any | None = None,
    attestations: Any | None = None,
) -> None:
    """Exercise erasure, audit integrity, objectives, and attestations."""
    erasure = erasure or MemoryErasureStore()
    audit = audit or MemoryAuditEvidenceStore()
    objectives = objectives or MemoryObjectiveStore()
    attestations = attestations or MemoryAttestationStore()
    ctx = _ctx()

    # Erasure — legal hold and no false completion.
    held = erasure.create_request(
        ctx,
        subject_key_fingerprint="subj-fp-1",
        field_paths=("email", "phone"),
        legal_hold=True,
    )
    assert held.status == "blocked"
    try:
        erasure.plan(ctx, request_id=held.request_id, providers=[])
        raise AssertionError("legal hold must block plan")
    except ControlPlaneError:
        pass

    req = erasure.create_request(
        ctx,
        subject_key_fingerprint="subj-fp-2",
        field_paths=("email",),
    )
    good = MemoryErasureProvider(provider_id="p-good")
    bad = MemoryErasureProvider(
        provider_id="p-bad", supported={"lookup"}, fail_actions=set()
    )
    plan = erasure.plan(
        ctx, request_id=req.request_id, providers=[good, bad], actions=("delete",)
    )
    report = erasure.execute(ctx, plan_id=plan.plan_id, providers=[good, bad])
    assert report.status != "completed"
    assert not report.reconciled
    blob = report.to_dict()
    assert_no_subject_values(blob, forbidden=["alice@example.com", "raw-subject"])

    # Audit chain.
    r1 = audit.append(ctx, action="policy.decide", resource="plan-1")
    r2 = audit.append(ctx, action="approval.decide", resource="appr-1")
    assert audit.verify_chain(ctx)
    assert r1.record_hash == r2.prev_hash
    exported = audit.export(ctx)
    other = MemoryAuditEvidenceStore()
    other_ctx = _ctx()
    restored = other.restore(other_ctx, export=exported)
    assert restored == 2
    assert other.verify_chain(other_ctx)
    audit.tamper_for_tests(ctx)
    assert not audit.verify_chain(ctx)

    # Objectives — dedupe + authorized routing.
    obj = DeliveryObjective(
        objective_id="obj-1",
        tenant_id=ctx.tenant.tenant_id,
        workspace_id=ctx.workspace.workspace_id,
        pipeline_id="pipe-1",
        step_id=None,
        version="1",
        reference="started",
        warning_after_seconds=10,
        hard_after_seconds=20,
    )
    objectives.upsert_objective(ctx, objective=obj)
    ref = datetime.now(UTC) - timedelta(seconds=30)
    ev1 = objectives.evaluate(
        ctx, objective_id="obj-1", reference_at=ref, submission_id="sub-1"
    )
    assert ev1.state == "breached"
    ev2 = objectives.evaluate(
        ctx, objective_id="obj-1", reference_at=ref, submission_id="sub-1"
    )
    assert ev2.evaluation_id == ev1.evaluation_id
    provider = memory_webhook_provider()
    note = objectives.route_notification(
        ctx,
        evaluation_id=ev1.evaluation_id,
        channel="webhook",
        destination_ref="hooks/ops",
        authorized_destinations=["hooks/ops"],
        provider=provider,
    )
    assert note.delivered
    try:
        objectives.route_notification(
            ctx,
            evaluation_id=ev1.evaluation_id,
            channel="webhook",
            destination_ref="hooks/evil",
            authorized_destinations=["hooks/ops"],
            provider=provider,
        )
        raise AssertionError("unauthorized destination")
    except ControlPlaneError:
        pass

    # Attestations.
    plan_fp = "plan-att"
    rev = "rev-att"
    pol = "pol-att"
    plugin = "plugin-att"
    for kind, subject in (
        ("plan", plan_fp),
        ("revision", rev),
        ("policy_bundle", pol),
        ("plugin", plugin),
    ):
        att = attestations.make_attestation(ctx, kind=kind, subject_fingerprint=subject)
        attestations.put(ctx, attestation=att)
    results = attestations.verify_plan(
        ctx,
        plan_fingerprint=plan_fp,
        revision_id=rev,
        policy_fingerprint=pol,
        plugin_fingerprints=[plugin],
    )
    assert all(r.ok for r in results)

    obs = attestations.make_schema_observation(
        ctx, schema_fingerprint="schema-1", environment="dev"
    )
    attestations.put_schema_observation(ctx, observation=obs)
    ok = attestations.verify_schema_observation(
        ctx, observation_id=obs.observation_id, expected_environment="dev"
    )
    assert ok.ok
    bad_env = attestations.verify_schema_observation(
        ctx, observation_id=obs.observation_id, expected_environment="prod"
    )
    assert not bad_env.ok


__all__ = ["run_cp4_governance_conformance_suite"]
