"""FastAPI CP4 route smoke tests."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryApprovalStore,
    MemoryAttestationStore,
    MemoryAuditEvidenceStore,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryErasureStore,
    MemoryEventStore,
    MemoryObjectiveStore,
    MemoryPolicyProvider,
    MemoryQuotaProvider,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_fastapi import ETLanticAPI, create_app, principal_from_header
from etlantic_fastapi.auth import membership_context_factory

pytestmark = pytest.mark.fastapi

ACTIONS = (
    "policy.decide",
    "approval.write",
    "approval.read",
    "approval.decide",
    "quota.admit",
    "quota.release",
    "quota.admin",
    "erasure.write",
    "erasure.execute",
    "erasure.read",
    "audit.read",
    "audit.export",
    "attestation.write",
    "attestation.verify",
    "objective.write",
    "objective.read",
    "objective.evaluate",
    "objective.notify",
    "definition.read",
    "run.submit",
    "run.read",
)


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice", issuer="tests"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _client(
    *,
    policy: MemoryPolicyProvider | None = None,
    quotas: MemoryQuotaProvider | None = None,
    objectives: MemoryObjectiveStore | None = None,
) -> TestClient:
    authz = MemoryAuthorizer()
    ctx = _ctx()
    for action in ACTIONS:
        authz.grant(ctx, action)
    api = ETLanticAPI(
        authorizer=authz,
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
        policy=policy if policy is not None else MemoryPolicyProvider(),
        approvals=MemoryApprovalStore(),
        quotas=quotas if quotas is not None else MemoryQuotaProvider(),
        erasure=MemoryErasureStore(),
        audit=MemoryAuditEvidenceStore(),
        attestations=MemoryAttestationStore.for_tests(),
        objectives=objectives if objectives is not None else MemoryObjectiveStore(),
    )
    defs = api.definitions
    defs.put(ctx, "pipe-1", {"name": "pipe-1"})
    return TestClient(create_app(api))


def test_policy_decide_route() -> None:
    client = _client()
    resp = client.post(
        "/v1/policy/decide",
        json={"hook": "pre_plan", "plan_fingerprint": "p1"},
        headers={"X-Principal": "alice"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["effect"] in ("allow", "deny", "require_approval")
    assert body["policy_fingerprint"]


def test_erasure_plan_execute_and_audit_routes() -> None:
    client = _client()
    erased = client.post(
        "/v1/erasure/requests",
        json={
            "subject_key_fingerprint": "fp-1",
            "field_paths": ["email"],
        },
        headers={"X-Principal": "alice"},
    )
    assert erased.status_code == 200
    request_id = erased.json()["request_id"]
    planned = client.post(
        f"/v1/erasure/requests/{request_id}/plan",
        json={"providers": ["local"]},
        headers={"X-Principal": "alice"},
    )
    assert planned.status_code == 200
    plan_id = planned.json()["plan_id"]
    executed = client.post(
        f"/v1/erasure/plans/{plan_id}/execute",
        json={"providers": ["local"]},
        headers={"X-Principal": "alice"},
    )
    assert executed.status_code == 200
    report_id = executed.json()["report_id"]
    report = client.get(
        f"/v1/erasure/reports/{report_id}",
        headers={"X-Principal": "alice"},
    )
    assert report.status_code == 200
    listed = client.get("/v1/audit", headers={"X-Principal": "alice"})
    assert listed.status_code == 200
    assert "records" in listed.json()


def test_missing_cp4_provider_returns_problem_details_501() -> None:
    authz = MemoryAuthorizer()
    ctx = _ctx()
    authz.grant(ctx, "policy.decide")
    api = ETLanticAPI(
        authorizer=authz,
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
        policy=None,
    )
    client = TestClient(create_app(api))
    resp = client.post(
        "/v1/policy/decide",
        json={"hook": "pre_plan"},
        headers={"X-Principal": "alice"},
    )
    assert resp.status_code == 501
    body = resp.json()
    assert body.get("code") == "PMCP501" or "PMCP501" in str(body)


def test_submit_gated_by_policy_deny() -> None:
    policy = MemoryPolicyProvider()
    policy.set_rule("pre_submit", "deny")
    client = _client(policy=policy)
    resp = client.post(
        "/v1/definitions/pipe-1/runs",
        headers={"X-Principal": "alice", "Idempotency-Key": "deny-1"},
        json={"payload": {"plan_fingerprint": "plan-x"}},
    )
    assert resp.status_code in (403, 409)
    body = resp.json()
    assert "PMCP" in str(body.get("code") or body)


def test_quota_admit_deny_and_release() -> None:
    quotas = MemoryQuotaProvider()
    quotas.default_limits["concurrency"] = 1
    client = _client(quotas=quotas)
    headers = {"X-Principal": "alice"}
    first = client.post(
        "/v1/quotas/admit",
        json={"resource": "concurrency"},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json()["effect"] == "allow"
    second = client.post(
        "/v1/quotas/admit",
        json={"resource": "concurrency"},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["effect"] == "deny"
    released = client.post(
        "/v1/quotas/release",
        json={"resource": "concurrency"},
        headers=headers,
    )
    assert released.status_code == 200


def test_approvals_get_and_objectives_routes() -> None:
    client = _client()
    headers = {"X-Principal": "alice"}
    created = client.post(
        "/v1/approvals",
        json={
            "plan_fingerprint": "plan-1",
            "policy_fingerprint": "pol-1",
            "hook": "pre_promote",
        },
        headers=headers,
    )
    assert created.status_code == 200
    approval_id = created.json()["approval_id"]
    got = client.get(f"/v1/approvals/{approval_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["approval_id"] == approval_id

    put = client.post(
        "/v1/objectives",
        json={
            "objective_id": "obj-1",
            "pipeline_id": "pipe-1",
            "warning_after_seconds": 5,
            "hard_after_seconds": 10,
            "reference": "started",
        },
        headers=headers,
    )
    assert put.status_code == 200, put.text
    fetched = client.get("/v1/objectives/obj-1", headers=headers)
    assert fetched.status_code == 200
    evaluated = client.post(
        "/v1/objectives/obj-1/evaluate",
        json={"reference_at": "2020-01-01T00:00:00+00:00", "submission_id": "s1"},
        headers=headers,
    )
    assert evaluated.status_code == 200
    assert evaluated.json()["state"] in (
        "on_track",
        "warning",
        "breached",
        "recovered",
        "acknowledged",
    )


def test_attestation_put_and_verify_plan() -> None:
    store = MemoryAttestationStore.for_tests()
    from etlantic.control_plane.attestation_models import Attestation, sign_payload

    att = Attestation(
        attestation_id="att-1",
        kind="plan",
        subject_fingerprint="plan-fp",
        signature="",
        signer_id="tests",
        tenant_id="tenant-a",
        workspace_id="ws-1",
    )
    signed = Attestation(
        attestation_id=att.attestation_id,
        kind=att.kind,
        subject_fingerprint=att.subject_fingerprint,
        signature=sign_payload(store.signing_secret, att.signing_payload()),
        signer_id=att.signer_id,
        tenant_id=att.tenant_id,
        workspace_id=att.workspace_id,
    )
    authz = MemoryAuthorizer()
    ctx = _ctx()
    for action in ACTIONS:
        authz.grant(ctx, action)
    api = ETLanticAPI(
        authorizer=authz,
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
        policy=MemoryPolicyProvider(),
        approvals=MemoryApprovalStore(),
        quotas=MemoryQuotaProvider(),
        erasure=MemoryErasureStore(),
        audit=MemoryAuditEvidenceStore(),
        attestations=store,
        objectives=MemoryObjectiveStore(),
    )
    client = TestClient(create_app(api))
    resp = client.post(
        "/v1/attestations",
        json=signed.to_dict(),
        headers={"X-Principal": "alice"},
    )
    assert resp.status_code == 200, resp.text
    verified = client.post(
        "/v1/attestations/verify-plan",
        json={
            "plan_fingerprint": "plan-fp",
            "revision_id": "rev-1",
            "policy_fingerprint": "pol-1",
        },
        headers={"X-Principal": "alice"},
    )
    assert verified.status_code == 200
    assert "results" in verified.json()
