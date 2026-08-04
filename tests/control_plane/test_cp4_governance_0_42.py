"""CP4 quotas, governance, erasure, audit, objectives, attestations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

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
    req = store.create_request(c, subject_key_fingerprint="fp", field_paths=("email",))
    providers = [
        MemoryErasureProvider(provider_id="a"),
        MemoryErasureProvider(provider_id="b", supported=set()),
    ]
    plan = store.plan(c, request_id=req.request_id, providers=providers)
    report = store.execute(c, plan_id=plan.plan_id, providers=providers)
    assert report.status != "completed"


def test_erasure_empty_providers_not_completed() -> None:
    store = MemoryErasureStore()
    c = ctx()
    req = store.create_request(c, subject_key_fingerprint="fp", field_paths=("email",))
    plan = store.plan(c, request_id=req.request_id, providers=[])
    report = store.execute(c, plan_id=plan.plan_id, providers=[])
    assert report.status != "completed"
    assert report.reconciled is False
    assert report.results == ()


def test_quota_wrr_idle_owner_does_not_starve() -> None:
    quotas = MemoryQuotaProvider()
    quotas.default_limits["concurrency"] = 100
    a = ctx()
    b = ControlPlaneContext(
        principal=Principal("bob", issuer="tests"),
        tenant=TenantRef("tenant-b"),
        workspace=WorkspaceRef("tenant-b", "workspace-b"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )
    # Seed A as ring member (used > 0) then only B admits under pressure.
    assert quotas.admit(a, resource="concurrency").effect == "allow"
    assert quotas.admit(b, resource="concurrency").effect == "allow"
    quotas.shared_pressure = True
    quotas._rr_cursor = 0  # A owns first slot when A weight default 1
    allowed_b = 0
    for _ in range(8):
        if quotas.admit(b, resource="concurrency").effect == "allow":
            allowed_b += 1
    assert allowed_b >= 1


def test_attestation_put_scope_mismatch() -> None:
    store = MemoryAttestationStore.for_tests()
    c = ctx()
    other = ControlPlaneContext(
        principal=Principal("alice", issuer="tests"),
        tenant=TenantRef("tenant-b"),
        workspace=WorkspaceRef("tenant-b", "workspace-b"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )
    att = store.make_attestation(c, kind="plan", subject_fingerprint="fp")
    with pytest.raises(ControlPlaneError, match="scope mismatch"):
        store.put(other, attestation=att)


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
    store = MemoryAttestationStore.for_tests()
    c = ctx()
    obs = store.make_schema_observation(c, schema_fingerprint="s1")
    from dataclasses import replace

    forged = replace(obs, signature="0" * 64)
    with pytest.raises(ControlPlaneError):
        store.put_schema_observation(c, observation=forged)


def test_quota_weighted_rr_under_shared_pressure() -> None:
    quotas = MemoryQuotaProvider()
    quotas.default_limits["concurrency"] = 100
    a = ctx()
    b = ControlPlaneContext(
        principal=Principal("bob", issuer="tests"),
        tenant=TenantRef("tenant-b"),
        workspace=WorkspaceRef("tenant-b", "workspace-b"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )
    quotas.weights[("tenant-a", "workspace-a")] = 2
    quotas.weights[("tenant-b", "workspace-b")] = 1
    # Seed both as active competitors before enabling shared pressure.
    assert quotas.admit(a, resource="concurrency").effect == "allow"
    assert quotas.admit(b, resource="concurrency").effect == "allow"
    quotas.shared_pressure = True
    quotas._rr_cursor = 0
    allowed_a = 0
    allowed_b = 0
    deferred = 0
    for _ in range(30):
        da = quotas.admit(a, resource="concurrency")
        if da.effect == "allow":
            allowed_a += 1
        elif da.reason == "fairness deferred":
            deferred += 1
        db = quotas.admit(b, resource="concurrency")
        if db.effect == "allow":
            allowed_b += 1
        elif db.reason == "fairness deferred":
            deferred += 1
    assert deferred > 0
    assert allowed_a > allowed_b


def test_erasure_cli_store_round_trip(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from etlantic.cli import app

    store_path = tmp_path / "erasure.json"
    runner = CliRunner()
    planned = runner.invoke(
        app,
        [
            "erasure",
            "plan",
            "--subject-key-fingerprint",
            "fp-cli",
            "--field",
            "email",
            "--store",
            str(store_path),
            "--format",
            "json",
        ],
    )
    assert planned.exit_code == 0, planned.output
    assert store_path.exists()
    import json

    payload = json.loads(planned.output)
    request_id = payload["request"]["request_id"]
    status = runner.invoke(
        app,
        [
            "erasure",
            "status",
            request_id,
            "--store",
            str(store_path),
            "--format",
            "json",
        ],
    )
    assert status.exit_code == 0, status.output
    body = json.loads(status.output)
    assert body["request_id"] == request_id
    assert body["status"] in ("pending", "planned", "blocked")


def test_connector_package_version_matches_release() -> None:
    from etlantic import __version__
    from etlantic_sql.connectors import PACKAGE_VERSION as sql_v

    assert sql_v == __version__ == "0.44.0"
    try:
        from etlantic_s3.connectors import PACKAGE_VERSION as s3_v

        assert s3_v == __version__
    except ImportError:
        pass
