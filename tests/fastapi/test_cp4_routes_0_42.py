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
    "approval.decide",
    "quota.admit",
    "erasure.write",
    "audit.read",
    "audit.export",
    "attestation.verify",
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


def _client() -> TestClient:
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
        attestations=MemoryAttestationStore(),
    )
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


def test_erasure_and_audit_routes() -> None:
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
    client.post(
        "/v1/policy/decide",
        json={"hook": "pre_plan"},
        headers={"X-Principal": "alice"},
    )
    listed = client.get("/v1/audit", headers={"X-Principal": "alice"})
    assert listed.status_code == 200
    assert "records" in listed.json()
