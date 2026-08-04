"""CP4 quotas, governance, erasure, audit, objectives, attestations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    DeliveryObjective,
    EnvironmentRef,
    GovernanceConstraints,
    MemoryAttestationStore,
    MemoryAuditEvidenceStore,
    MemoryErasureProvider,
    MemoryErasureStore,
    MemoryObjectiveStore,
    MemoryQuotaProvider,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    gate_pre_plan,
    memory_email_provider,
)
from etlantic.control_plane.policy_memory import MemoryPolicyProvider
from etlantic.testing import run_cp4_governance_conformance_suite


def ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("alice", issuer="tests"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "workspace-a"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def test_cp4_governance_conformance_suite() -> None:
    run_cp4_governance_conformance_suite()


def test_quota_noisy_neighbor() -> None:
    quotas = MemoryQuotaProvider()
    quotas.default_limits["concurrency"] = 2
    c = ctx()
    assert quotas.admit(c, resource="concurrency").effect == "allow"
    assert quotas.admit(c, resource="concurrency").effect == "allow"
    assert quotas.admit(c, resource="concurrency").effect == "deny"


def test_governance_boundary_blocks_plan() -> None:
    policy = MemoryPolicyProvider()
    policy.constraints = GovernanceConstraints(residency_regions=("us",))
    with pytest.raises(ControlPlaneError):
        gate_pre_plan(
            ctx(),
            policy=policy,
            attributes={"target_region": "eu"},
            required=True,
        )


def test_erasure_no_false_completion() -> None:
    store = MemoryErasureStore()
    c = ctx()
    req = store.create_request(
        c, subject_key_fingerprint="fp", field_paths=("email",)
    )
    providers = [
        MemoryErasureProvider(provider_id="a"),
        MemoryErasureProvider(provider_id="b", supported=set()),
    ]
    plan = store.plan(c, request_id=req.request_id, providers=providers)
    report = store.execute(c, plan_id=plan.plan_id, providers=providers)
    assert report.status != "completed"


def test_audit_tamper_detected() -> None:
    audit = MemoryAuditEvidenceStore()
    c = ctx()
    audit.append(c, action="x", resource="r")
    assert audit.verify_chain(c)
    audit.tamper_for_tests(c)
    assert not audit.verify_chain(c)


def test_objective_recovery() -> None:
    store = MemoryObjectiveStore()
    c = ctx()
    store.upsert_objective(
        c,
        objective=DeliveryObjective(
            objective_id="o1",
            tenant_id="tenant-a",
            workspace_id="workspace-a",
            pipeline_id="p",
            step_id=None,
            version="1",
            reference="started",
            warning_after_seconds=5,
            hard_after_seconds=10,
        ),
    )
    ref = datetime.now(UTC) - timedelta(seconds=30)
    breached = store.evaluate(
        c, objective_id="o1", reference_at=ref, submission_id="s1"
    )
    assert breached.state == "breached"
    recovered = store.evaluate(
        c,
        objective_id="o1",
        reference_at=ref,
        submission_id="s1",
        completed=True,
    )
    assert recovered.state == "recovered"
    provider = memory_email_provider()
    store.route_notification(
        c,
        evaluation_id=recovered.evaluation_id,
        channel="email",
        destination_ref="ops@example.com",
        authorized_destinations=["ops@example.com"],
        provider=provider,
    )
    assert provider.delivered


def test_forged_schema_observation_rejected() -> None:
    store = MemoryAttestationStore()
    c = ctx()
    obs = store.make_schema_observation(c, schema_fingerprint="s1")
    from dataclasses import replace

    forged = replace(obs, signature="0" * 64)
    with pytest.raises(ControlPlaneError):
        store.put_schema_observation(c, observation=forged)
