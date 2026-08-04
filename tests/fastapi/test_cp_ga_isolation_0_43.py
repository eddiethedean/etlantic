"""FastAPI CP-GA two-tenant isolation (0.43)."""

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
    "definition.read",
    "run.submit",
    "run.read",
    "run.cancel",
    "run.events",
    "run.report",
    "policy.decide",
    "audit.read",
    "erasure.write",
    "erasure.read",
    "reliability.list",
)


def _ctx(tenant: str, subject: str) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject=subject, issuer="tests"),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _client(*, bob_has_pipe: bool = True) -> TestClient:
    authz = MemoryAuthorizer()
    alice = _ctx("tenant-a", "alice")
    bob = _ctx("tenant-b", "bob")
    for action in ACTIONS:
        authz.grant(alice, action)
        authz.grant(bob, action)
    defs = MemoryDefinitionRepository()
    defs.put(alice, "pipe", {"name": "pipe-a", "owner": "alice"})
    if bob_has_pipe:
        defs.put(bob, "pipe", {"name": "pipe-b", "owner": "bob"})
    api = ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {
                "alice": ("tenant-a", "ws-1", "development", "default"),
                "bob": ("tenant-b", "ws-1", "development", "default"),
            }
        ),
        principal_dependency=principal_from_header,
        policy=MemoryPolicyProvider(),
        approvals=MemoryApprovalStore(),
        quotas=MemoryQuotaProvider(),
        erasure=MemoryErasureStore(),
        audit=MemoryAuditEvidenceStore(),
        attestations=MemoryAttestationStore.for_tests(),
        objectives=MemoryObjectiveStore(),
    )
    return TestClient(create_app(api))


def test_cross_tenant_run_is_opaque_404() -> None:
    client = _client()
    submit = client.post(
        "/v1/definitions/pipe/runs",
        headers={"X-Principal": "alice", "Idempotency-Key": "ga-1"},
        json={},
    )
    assert submit.status_code == 202
    run_id = submit.json()["resource_id"]

    leaked = client.get(f"/v1/runs/{run_id}", headers={"X-Principal": "bob"})
    assert leaked.status_code == 404
    body = leaked.json()
    assert "tenant-a" not in str(body).lower()


def test_cross_tenant_definition_is_opaque_404() -> None:
    # Alice owns "pipe"; Bob has no definition with that id → opaque 404.
    client = _client(bob_has_pipe=False)
    alice_doc = client.get("/v1/definitions/pipe", headers={"X-Principal": "alice"})
    assert alice_doc.status_code == 200
    assert alice_doc.json()["document"]["owner"] == "alice"

    leaked = client.get("/v1/definitions/pipe", headers={"X-Principal": "bob"})
    assert leaked.status_code == 404
    body = str(leaked.json()).lower()
    assert "pipe-a" not in body
    assert "alice" not in body
    assert "tenant-a" not in body


def test_reliability_stub_exposes_experimental() -> None:
    client = _client()
    resp = client.get("/v1/reliability", headers={"X-Principal": "alice"})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("experimental") is True
