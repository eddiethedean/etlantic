"""CP2 registry FastAPI routes + registry-backed definitions (0.40 / 040-P)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    LifecycleState,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryEventStore,
    MemoryRegistryProvider,
    MemorySubmissionStore,
    Principal,
    RegistryRevision,
    SecurityDomain,
    TenantRecord,
    TenantRef,
    WorkspaceRecord,
    WorkspaceRef,
    content_fingerprint,
)
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)

pytestmark = pytest.mark.fastapi

REGISTRY_ACTIONS = (
    "registry.tenant.list",
    "registry.tenant.read",
    "registry.tenant.write",
    "registry.workspace.list",
    "registry.workspace.read",
    "registry.workspace.write",
    "registry.revision.list",
    "registry.revision.read",
    "registry.alias.write",
    "registry.promote",
    "definition.list",
    "definition.read",
)


def _ctx(
    tenant: str, workspace: str, subject: str, domain: str = "default"
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject=subject),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id=domain),
    )


def _build(*, with_registry: bool = True, registry_defs: bool = False):
    authz = MemoryAuthorizer()
    registry = MemoryRegistryProvider() if with_registry else None
    defs = MemoryDefinitionRepository()
    ctx_a = _ctx("tenant-a", "ws-1", "alice", domain="domain-a")
    ctx_b = _ctx("tenant-b", "ws-1", "bob", domain="domain-b")
    if registry is not None:
        for ctx in (ctx_a, ctx_b):
            registry.tenants.put(
                ctx,
                TenantRecord(
                    tenant_id=ctx.tenant.tenant_id,
                    security_domain_id=ctx.security_domain.domain_id,
                ),
            )
            registry.workspaces.put(
                ctx,
                WorkspaceRecord(
                    tenant_id=ctx.tenant.tenant_id,
                    workspace_id=ctx.workspace.workspace_id,
                ),
            )
            content = {"owner": ctx.tenant.tenant_id}
            registry.revisions.put_revision(
                ctx,
                RegistryRevision(
                    logical_id="pipe-1",
                    revision_id=f"rev-{ctx.tenant.tenant_id}",
                    tenant_id=ctx.tenant.tenant_id,
                    workspace_id=ctx.workspace.workspace_id,
                    content_fingerprint=content_fingerprint(content),
                    content=content,
                    kind="pipeline",
                ),
            )
    for action in REGISTRY_ACTIONS:
        authz.grant(ctx_a, action)
        authz.grant(ctx_b, action)

    factory = membership_context_factory(
        {
            "alice": ("tenant-a", "ws-1", "development", "domain-a"),
            "bob": ("tenant-b", "ws-1", "development", "domain-b"),
        }
    )
    if registry_defs and registry is not None:
        api = ETLanticAPI.with_registry_definitions(
            authorizer=authz,
            registry=registry,
            submissions=MemorySubmissionStore(),
            events=MemoryEventStore(),
            context_factory=factory,
            principal_dependency=principal_from_header,
        )
    else:
        api = ETLanticAPI(
            authorizer=authz,
            definitions=defs,
            submissions=MemorySubmissionStore(),
            events=MemoryEventStore(),
            context_factory=factory,
            principal_dependency=principal_from_header,
            registry=registry,
        )
    return TestClient(create_app(api)), authz, registry, defs


def test_registry_list_tenants_and_workspaces_scoped() -> None:
    client, _, _, _ = _build()
    alice = client.get("/v1/registry/tenants", headers={"X-Principal": "alice"})
    assert alice.status_code == 200
    ids = {t["tenant_id"] for t in alice.json()["items"]}
    assert ids == {"tenant-a"}

    ws = client.get("/v1/registry/workspaces", headers={"X-Principal": "alice"})
    assert ws.status_code == 200
    assert {w["workspace_id"] for w in ws.json()["items"]} == {"ws-1"}


def test_registry_authz_before_lookup_non_enumeration() -> None:
    client, authz, _, _ = _build()
    # Deny alice tenant read → opaque 404 (resource_in_caller_scope=False).
    authz.grants.discard(("tenant-a", "ws-1", "registry.tenant.read"))
    resp = client.get("/v1/registry/tenants/tenant-a", headers={"X-Principal": "alice"})
    assert resp.status_code == 404

    # Cross-tenant get still 404 after grant restored for self only.
    authz.grant(
        _ctx("tenant-a", "ws-1", "alice", domain="domain-a"), "registry.tenant.read"
    )
    cross = client.get(
        "/v1/registry/tenants/tenant-b", headers={"X-Principal": "alice"}
    )
    assert cross.status_code == 404


def test_registry_revisions_alias_promote() -> None:
    client, _, _, _ = _build()
    headers = {"X-Principal": "alice"}
    listed = client.get("/v1/registry/logicals/pipe-1/revisions", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    got = client.get("/v1/registry/revisions/rev-tenant-a", headers=headers)
    assert got.status_code == 200
    assert got.json()["logical_id"] == "pipe-1"

    alias = client.put(
        "/v1/registry/aliases/prod",
        headers=headers,
        json={"logical_id": "pipe-1", "revision_id": "rev-tenant-a"},
    )
    assert alias.status_code == 200
    assert alias.json()["revision_id"] == "rev-tenant-a"

    promo = client.post(
        "/v1/registry/promotions",
        headers=headers,
        json={
            "logical_id": "pipe-1",
            "from_revision_id": "rev-tenant-a",
            "from_environment": "development",
            "to_environment": "production",
        },
    )
    assert promo.status_code == 200
    body = promo.json()
    assert body["logical_id"] == "pipe-1"
    assert body["to_revision_id"] != "rev-tenant-a"


def test_registry_suspended_fail_closed() -> None:
    client, _, registry, _ = _build()
    assert registry is not None
    ctx = _ctx("tenant-a", "ws-1", "alice", domain="domain-a")
    registry.workspaces.set_lifecycle(ctx, "ws-1", LifecycleState.SUSPENDED)
    resp = client.get(
        "/v1/registry/revisions/rev-tenant-a", headers={"X-Principal": "alice"}
    )
    assert resp.status_code == 403


def test_registry_lifecycle_validation_is_422_not_500() -> None:
    client, _, _, _ = _build()
    headers = {"X-Principal": "alice"}
    tenant = client.put(
        "/v1/registry/tenants/tenant-a",
        headers=headers,
        json={"lifecycle": "paused"},
    )
    workspace = client.put(
        "/v1/registry/workspaces/ws-1",
        headers=headers,
        json={"lifecycle": "paused"},
    )
    assert tenant.status_code == 422
    assert workspace.status_code == 422


def test_registry_without_provider_returns_501() -> None:
    client, _, _, _ = _build(with_registry=False)
    resp = client.get("/v1/registry/tenants", headers={"X-Principal": "alice"})
    assert resp.status_code == 501


def test_definitions_via_registry_backend_stable_paths() -> None:
    client, _, registry, _ = _build(registry_defs=True)
    assert registry is not None
    headers = {"X-Principal": "alice"}
    # Seed via registry-backed DefinitionRepository using put through provider helper.
    from etlantic.control_plane import RegistryDefinitionRepository

    defs = RegistryDefinitionRepository(registry)
    defs.put(
        _ctx("tenant-a", "ws-1", "alice", domain="domain-a"),
        "my-def",
        {"name": "orders"},
    )

    listed = client.get("/v1/definitions", headers=headers)
    assert listed.status_code == 200
    assert {i["definition_id"] for i in listed.json()["items"]} == {"my-def"}

    got = client.get("/v1/definitions/my-def", headers=headers)
    assert got.status_code == 200
    assert got.json()["document"]["name"] == "orders"

    # Bob cannot see Alice's definition (same path, scoped).
    bob = client.get("/v1/definitions/my-def", headers={"X-Principal": "bob"})
    assert bob.status_code == 404


def test_openapi_includes_registry_operation_ids() -> None:
    client, _, _, _ = _build()
    schema = client.app.openapi()
    op_ids = {
        op.get("operationId")
        for path in schema["paths"].values()
        for method, op in path.items()
        if isinstance(op, dict) and not method.startswith("x-")
    }
    expected = {
        "cp_registry_list_tenants",
        "cp_registry_get_tenant",
        "cp_registry_put_tenant",
        "cp_registry_list_workspaces",
        "cp_registry_get_workspace",
        "cp_registry_put_workspace",
        "cp_registry_list_revisions",
        "cp_registry_get_revision",
        "cp_registry_put_alias",
        "cp_registry_promote",
    }
    assert expected <= op_ids
