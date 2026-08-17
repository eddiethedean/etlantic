"""FastAPI schedule routes, authz, and non-enumeration (0.47)."""

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
    MemoryDurableWorkStore,
    MemoryEventStore,
    MemoryScheduleStore,
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

SCHEDULE_ACTIONS = (
    "schedule.read",
    "schedule.write",
    "scheduler.health",
    "worker.health",
    "definition.read",
)


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice", issuer="tests"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _client() -> tuple[TestClient, MemoryScheduleStore, MemoryDurableWorkStore]:
    authz = MemoryAuthorizer()
    store = MemoryScheduleStore()
    durable = MemoryDurableWorkStore()
    defs = MemoryDefinitionRepository()
    ctx = _ctx()
    defs.put(ctx, "pipe-1", {"name": "pipe-1"})
    for action in SCHEDULE_ACTIONS:
        authz.grant(ctx, action)
    api = ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
        durable_work=durable,
        schedule_store=store,
    )
    return TestClient(create_app(api)), store, durable


def test_schedule_routes_create_trigger_and_health() -> None:
    client, _store, durable = _client()
    headers = {"X-Principal": "alice"}
    created = client.post(
        "/v1/definitions/pipe-1/schedules",
        headers=headers,
        json={"kind": "interval", "interval_seconds": 60},
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["schedule_id"]
    got = client.get(f"/v1/schedules/{schedule_id}", headers=headers)
    assert got.status_code == 200
    trigger = client.post(f"/v1/schedules/{schedule_id}/trigger", headers=headers)
    assert trigger.status_code == 200
    assert durable.pending_outbox(_ctx())
    health = client.get("/v1/scheduler/health", headers=headers)
    assert health.status_code == 200
    workers = client.get("/v1/workers/health", headers=headers)
    assert workers.status_code == 200
    assert "hosts" not in workers.json()


def test_schedule_store_missing_is_501() -> None:
    authz = MemoryAuthorizer()
    ctx = _ctx()
    authz.grant(ctx, "schedule.read")
    api = ETLanticAPI(
        authorizer=authz,
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    client = TestClient(create_app(api))
    resp = client.get("/v1/schedules/missing", headers={"X-Principal": "alice"})
    assert resp.status_code == 501


def test_worker_health_does_not_enumerate_without_authz() -> None:
    client, _, _ = _client()
    resp = client.get("/v1/workers/health", headers={"X-Principal": "eve"})
    assert resp.status_code in {401, 403, 404}
    if resp.status_code == 200:
        raise AssertionError("unauthorized worker health must not succeed")
    assert "worker-host" not in resp.text
