"""Concrete list denials, scoped providers, limits and fail-closed responses."""

import importlib
import os
from dataclasses import replace
from unittest.mock import Mock

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuditEvidenceStore,
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
    include_router,
    install_exception_handlers,
    membership_context_factory,
    principal_from_header,
)
from fastapi import FastAPI

pytestmark = pytest.mark.fastapi
HEADERS = {"X-Principal": "alice"}


@pytest.fixture(params=["memory", "sqlmodel"])
def graph(request, tmp_path):
    ctx = ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )
    if request.param == "sqlmodel":
        if os.environ.get("ETLANTIC_REQUIRE_SQLMODEL") == "1":
            importlib.import_module("etlantic_sqlmodel")
        else:
            pytest.importorskip("etlantic_sqlmodel")
        from etlantic_sqlmodel import (
            SQLModelDefinitionRepository,
            SqlModelRegistryProvider,
            apply_migrations,
            create_sqlite_engine,
        )

        engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'visibility.db'}")
        apply_migrations(engine)
        defs, registry = (
            SQLModelDefinitionRepository(engine),
            SqlModelRegistryProvider(engine),
        )
    else:
        defs, registry = MemoryDefinitionRepository(), MemoryRegistryProvider()
    authz = MemoryAuthorizer()
    api = ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        registry=registry,
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        audit=MemoryAuditEvidenceStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    yield ctx, api, authz
    if request.param == "sqlmodel":
        engine.dispose()


def deny(authz, ctx, action, resource):
    authz.forbidden_resources.add((*ctx.scope_key, action, resource))


@pytest.mark.parametrize("embedded", [False, True])
def test_definition_visibility_uses_list_not_read_and_stays_scoped(graph, embedded):
    ctx, api, authz = graph
    for name in ("hidden", "visible", "read-denied"):
        api.definitions.put(ctx, name, {"name": name})
    other = replace(
        ctx, workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-2")
    )
    api.definitions.put(other, "other-workspace", {"name": "other"})
    authz.grant(ctx, "definition.list")
    authz.grant(ctx, "definition.read")
    deny(authz, ctx, "definition.list", "definition:hidden")
    deny(authz, ctx, "definition.read", "definition:read-denied")
    app = FastAPI() if embedded else create_app(api)
    if embedded:
        install_exception_handlers(app)
        include_router(app, api, prefix="/etl")
    prefix = "/etl" if embedded else ""
    with TestClient(app) as client:
        response = client.get(prefix + "/v1/definitions", headers=HEADERS)
        assert response.status_code == 200
        assert {i["definition_id"] for i in response.json()["items"]} == {
            "visible",
            "read-denied",
        }
        assert (
            client.get(
                prefix + "/v1/definitions/read-denied", headers=HEADERS
            ).status_code
            == 403
        )
        assert (
            client.get(
                prefix + "/v1/definitions/other-workspace", headers=HEADERS
            ).status_code
            == 404
        )


@pytest.mark.parametrize("kind", ["definitions", "tenants", "workspaces", "revisions"])
def test_collection_denial_never_accesses_repository(graph, kind, monkeypatch):
    _, api, _ = graph
    if kind == "definitions":
        store, method, path = api.definitions, "list", "/v1/definitions"
    elif kind == "revisions":
        store, method, path = (
            api.registry.revisions,
            "list_revisions",
            "/v1/registry/logicals/demo/revisions",
        )
    else:
        store, method, path = (
            getattr(api.registry, kind),
            "list",
            f"/v1/registry/{kind}",
        )
    lookup = Mock(side_effect=AssertionError("unauthorized repository access"))
    monkeypatch.setattr(store, method, lookup)
    with TestClient(create_app(api)) as client:
        assert client.get(path, headers=HEADERS).status_code in (403, 404)
    lookup.assert_not_called()


@pytest.mark.parametrize("kind", ["tenants", "workspaces", "revisions"])
def test_registry_concrete_denials(graph, kind):
    ctx, api, authz = graph
    api.registry.tenants.put(
        ctx, TenantRecord(tenant_id="tenant-a", security_domain_id="default")
    )
    api.registry.workspaces.put(
        ctx, WorkspaceRecord(tenant_id="tenant-a", workspace_id="ws-1")
    )
    other = replace(
        ctx, workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-2")
    )
    api.registry.workspaces.put(
        other, WorkspaceRecord(tenant_id="tenant-a", workspace_id="ws-2")
    )
    content = {"name": "demo"}
    for name in ("hidden", "visible"):
        api.registry.revisions.put_revision(
            ctx,
            RegistryRevision(
                logical_id="demo",
                revision_id=name,
                tenant_id="tenant-a",
                workspace_id="ws-1",
                content=content,
                content_fingerprint=content_fingerprint(content),
                kind="pipeline",
            ),
        )
    singular = {
        "tenants": "tenant",
        "workspaces": "workspace",
        "revisions": "revision",
    }[kind]
    action = f"registry.{singular}.list"
    authz.grant(ctx, action)
    denied_id = {"tenants": "tenant-a", "workspaces": "ws-1", "revisions": "hidden"}[
        kind
    ]
    deny(authz, ctx, action, f"registry:{singular}:{denied_id}")
    if kind == "workspaces":
        # Workspace directories intentionally list across the caller's tenant;
        # the concrete list decision governs visibility in another workspace.
        deny(authz, ctx, action, "registry:workspace:ws-2")
    path = (
        "/v1/registry/logicals/demo/revisions"
        if kind == "revisions"
        else f"/v1/registry/{kind}"
    )
    with TestClient(create_app(api)) as client:
        response = client.get(path, headers=HEADERS)
        assert response.status_code == 200
        ids = {i[f"{singular}_id"] for i in response.json()["items"]}
        assert denied_id not in ids
        if kind == "revisions":
            assert ids == {"visible"}
        if kind == "workspaces":
            assert "ws-2" not in ids


def test_authorization_failure_after_visible_item_returns_no_partial_result(
    graph, monkeypatch
):
    ctx, api, authz = graph
    authz.grant(ctx, "definition.list")
    for name in ("a-visible", "z-failure"):
        api.definitions.put(ctx, name, {"name": name})
    original = authz.authorize

    def authorize(ctx, action, resource):
        if resource == "definition:z-failure":
            raise RuntimeError("secret-service-sentinel")
        return original(ctx, action, resource)

    monkeypatch.setattr(authz, "authorize", authorize)
    with TestClient(create_app(api)) as client:
        response = client.get("/v1/definitions", headers=HEADERS)
        assert response.status_code == 503
        assert "a-visible" not in response.text
        assert "secret-service-sentinel" not in response.text


def test_audit_visibility_before_existing_limit_and_prefix_growth(graph):
    ctx, api, authz = graph
    authz.grant(ctx, "audit.read")
    for index in range(102):
        record_id = f"record-{index}"
        api.audit.append(ctx, action="test", resource="test", record_id=record_id)
        if index < 101:
            deny(authz, ctx, "audit.read", f"audit:record:{record_id}")
    with TestClient(create_app(api)) as client:
        response = client.get("/v1/audit?limit=1", headers=HEADERS)
        assert response.status_code == 200
        assert [i["record_id"] for i in response.json()["records"]] == ["record-101"]


def test_durable_outbox_visibility_before_existing_limit(graph):
    from etlantic.control_plane import MemoryDurableWorkStore

    ctx, api, authz = graph
    api.durable_work = MemoryDurableWorkStore()
    authz.grant(ctx, "durable.outbox.read")
    for index in range(3):
        api.durable_work.accept(
            ctx,
            idempotency_key=f"key-{index}",
            operation="test",
            plan_fingerprint="plan",
        )
    records = api.durable_work.pending_outbox(ctx)
    for record in records[:2]:
        deny(authz, ctx, "durable.outbox.read", f"durable:outbox:{record.outbox_id}")
    with TestClient(create_app(api)) as client:
        response = client.get("/v1/durable/outbox?limit=1", headers=HEADERS)
        assert response.status_code == 200
        assert [i["outbox_id"] for i in response.json()] == [records[2].outbox_id]


@pytest.mark.parametrize(
    "path,field,action,resource",
    [
        (
            "/v1/schema/observations",
            "history_store",
            "schema.observations.list",
            "schema:observation:hidden",
        ),
        (
            "/v1/reliability",
            "history_store",
            "reliability.list",
            "reliability:observation:hidden",
        ),
        (
            "/v1/definitions/demo/schedules",
            "schedule_store",
            "schedule.read",
            "schedule:hidden",
        ),
        (
            "/v1/schedules/demo/firings",
            "schedule_store",
            "schedule.read",
            "schedule:firing:hidden",
        ),
    ],
)
def test_other_collection_denials_happen_before_item_serialization(
    graph, path, field, action, resource
):
    ctx, api, authz = graph
    authz.grant(ctx, action)
    deny(authz, ctx, action, resource)
    record = Mock(
        observation_id="hidden",
        schedule_id="hidden",
        firing_id="hidden",
        definition_id="demo",
    )
    record.to_dict.side_effect = AssertionError("denied record was serialized")
    store = Mock()
    store.list_schema_observations.return_value = [record]
    store.list_reliability_observations.return_value = [record]
    store.list_schedules.return_value = [record]
    store.list_firings.return_value = [record]
    setattr(api, field, store)
    with TestClient(create_app(api)) as client:
        response = client.get(path, headers=HEADERS)
        assert response.status_code == 200
        assert "hidden" not in response.text
    record.to_dict.assert_not_called()
