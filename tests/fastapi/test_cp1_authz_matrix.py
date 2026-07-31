"""Two-tenant authz / non-enumeration matrix for CP1 read routes."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryEventStore,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)

pytestmark = pytest.mark.fastapi

ACTIONS = (
    "definition.list",
    "definition.read",
    "definition.validate",
    "definition.plan",
    "run.submit",
    "run.read",
    "run.cancel",
    "run.report",
    "run.artifacts",
    "run.lineage",
    "run.events",
    "schema.observations.list",
    "schema.observations.ack",
    "reliability.list",
)


def _ctx(tenant: str, workspace: str, subject: str) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject=subject),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _app() -> tuple[TestClient, MemoryAuthorizer, MemoryDefinitionRepository]:
    authz = MemoryAuthorizer()
    defs = MemoryDefinitionRepository()
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
    )
    a = _ctx("tenant-a", "ws-1", "alice")
    b = _ctx("tenant-b", "ws-1", "bob")
    defs.put(a, "shared-name", {"owner": "a"})
    defs.put(b, "shared-name", {"owner": "b"})
    defs.put(a, "only-a", {"owner": "a"})
    defs.put(b, "only-b", {"owner": "b"})
    for action in ACTIONS:
        authz.grant(a, action)
        authz.grant(b, action)
    return TestClient(create_app(api)), authz, defs


def test_list_and_get_are_tenant_scoped() -> None:
    client, _, _ = _app()
    alice = client.get("/v1/definitions", headers={"X-Principal": "alice"})
    bob = client.get("/v1/definitions", headers={"X-Principal": "bob"})
    assert alice.status_code == 200
    assert bob.status_code == 200
    alice_ids = {i["definition_id"] for i in alice.json()["items"]}
    bob_ids = {i["definition_id"] for i in bob.json()["items"]}
    assert alice_ids == {"shared-name", "only-a"}
    assert bob_ids == {"shared-name", "only-b"}

    a_get = client.get("/v1/definitions/only-a", headers={"X-Principal": "alice"})
    assert a_get.status_code == 200
    assert a_get.json()["document"]["owner"] == "a"

    # Cross-tenant: opaque not_found (non-enumeration).
    cross = client.get("/v1/definitions/only-a", headers={"X-Principal": "bob"})
    assert cross.status_code == 404


def test_validate_and_plan_matrix() -> None:
    client, _, _ = _app()
    ok = client.post(
        "/v1/definitions/only-a/validate", headers={"X-Principal": "alice"}
    )
    assert ok.status_code == 200
    assert ok.json()["ok"] is True

    cross = client.post(
        "/v1/definitions/only-a/validate", headers={"X-Principal": "bob"}
    )
    assert cross.status_code == 404

    plan_ok = client.post(
        "/v1/definitions/only-a/plan", headers={"X-Principal": "alice"}
    )
    assert plan_ok.status_code == 200
    assert plan_ok.json()["ok"] is True

    plan_cross = client.post(
        "/v1/definitions/only-a/plan", headers={"X-Principal": "bob"}
    )
    assert plan_cross.status_code == 404


def test_in_scope_forbidden_is_403() -> None:
    client, authz, _ = _app()
    a = _ctx("tenant-a", "ws-1", "alice")
    authz.forbidden_resources.add(
        (
            a.tenant.tenant_id,
            a.workspace.workspace_id,
            "definition.read",
            "definition:only-a",
        )
    )
    resp = client.get("/v1/definitions/only-a", headers={"X-Principal": "alice"})
    assert resp.status_code == 403


def test_in_scope_run_forbid_is_403() -> None:
    client, authz, _ = _app()
    headers = {"X-Principal": "alice", "Idempotency-Key": "forbid-run"}
    submit = client.post("/v1/definitions/only-a/runs", headers=headers, json={})
    assert submit.status_code == 202
    run_id = submit.json()["resource_id"]
    authz.forbidden_resources.add(("tenant-a", "ws-1", "run.read", f"run:{run_id}"))
    resp = client.get(f"/v1/runs/{run_id}", headers={"X-Principal": "alice"})
    assert resp.status_code == 403


def test_unauthenticated_is_401() -> None:
    client, _, _ = _app()
    resp = client.get("/v1/definitions")
    assert resp.status_code == 401


def test_health_and_ready() -> None:
    client, _, _ = _app()
    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
