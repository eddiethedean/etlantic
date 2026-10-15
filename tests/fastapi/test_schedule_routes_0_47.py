# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""FastAPI schedule routes, authz, and non-enumeration (0.47)."""

from __future__ import annotations

import asyncio
import json
from threading import get_ident
from types import SimpleNamespace
from typing import Any, cast

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx2")

from fastapi.routing import APIRoute
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
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    TriggerEnvelope,
    WorkspaceRef,
    external_occurrence_id,
)
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)
from etlantic_fastapi.schedule_routes import register_schedule_routes
from fastapi import APIRouter, Request, Response

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


def test_schedule_delete_releases_the_canonical_schedule_record() -> None:
    client, store, _durable = _client()
    headers = {"X-Principal": "alice"}
    created = client.post(
        "/v1/definitions/pipe-1/schedules",
        headers=headers,
        json={"kind": "interval", "interval_seconds": 60},
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["schedule_id"]

    deleted = client.delete(f"/v1/schedules/{schedule_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleted"
    assert store.list_schedules(_ctx()) == ()
    assert (
        client.get(f"/v1/schedules/{schedule_id}", headers=headers).status_code == 404
    )


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


def test_schedule_amendment_is_revision_guarded() -> None:
    client, _store, _durable = _client()
    request_client: Any = cast(Any, client)
    headers = {"X-Principal": "alice"}
    created = request_client.post(
        "/v1/definitions/pipe-1/schedules",
        headers=headers,
        json={"kind": "interval", "interval_seconds": 60},
    )
    assert created.status_code == 201, created.text
    schedule = created.json()
    schedule_id = schedule["schedule_id"]
    old_revision = schedule["revision_id"]

    amended_response = request_client.post(
        f"/v1/schedules/{schedule_id}/amend",
        headers=headers,
        json={
            "expected_revision_id": old_revision,
            "spec": {"kind": "interval", "interval_seconds": 120},
        },
    )
    assert amended_response.status_code == 200, amended_response.text
    amended = amended_response.json()
    assert amended["revision_id"] != old_revision
    assert amended["metadata"]["amends_revision_id"] == old_revision
    assert amended["spec"]["interval_seconds"] == 120

    stale = request_client.post(
        f"/v1/schedules/{schedule_id}/amend",
        headers=headers,
        json={
            "expected_revision_id": old_revision,
            "spec": {"kind": "interval", "interval_seconds": 180},
        },
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["extensions"]["reason"] == "stale_revision"


def test_schedule_route_transfer_accepts_only_the_managed_boolean() -> None:
    from etlantic.control_plane.errors import ControlPlaneError
    from etlantic_fastapi.schedule_routes import register_schedule_routes
    from fastapi import APIRouter, FastAPI

    class _Schedule:
        def to_dict(self) -> dict[str, Any]:
            return {"execution_route": "prefect:" + "a" * 64}

    class _ScheduleService:
        transfer_execution_route: bool | None = None
        timer_binding_fingerprint: str | None = None

        def authorize(self, *_args: object) -> None:
            return None

        def amend(
            self,
            _ctx: ControlPlaneContext,
            _schedule_id: str,
            *,
            expected_revision_id: str,
            spec: Any,
            transfer_execution_route: bool = False,
            timer_binding_fingerprint: str | None = None,
        ) -> _Schedule:
            assert expected_revision_id == "revision-a"
            assert isinstance(spec, ScheduleSpec)
            self.transfer_execution_route = transfer_execution_route
            self.timer_binding_fingerprint = timer_binding_fingerprint
            return _Schedule()

    class _API:
        def __init__(self) -> None:
            self.schedule_service = _ScheduleService()

        def get_schedule_service(self) -> _ScheduleService:
            return self.schedule_service

    api = _API()
    router = APIRouter()
    register_schedule_routes(router, api, lambda: _ctx())
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    headers = {"X-Principal": "alice"}
    binding_fingerprint = "a" * 64
    response = client.post(
        "/v1/schedules/schedule-a/amend",
        headers=headers,
        json={
            "expected_revision_id": "revision-a",
            "spec": {"kind": "interval", "interval_seconds": 120},
            "transfer_execution_route": True,
            "timer_binding_fingerprint": binding_fingerprint,
        },
    )
    assert response.status_code == 200, response.text
    assert api.schedule_service.transfer_execution_route is True
    assert api.schedule_service.timer_binding_fingerprint == binding_fingerprint
    assert response.json()["execution_route"] == "prefect:" + "a" * 64

    with pytest.raises(ControlPlaneError) as invalid_flag:
        client.post(
            "/v1/schedules/schedule-a/amend",
            headers=headers,
            json={
                "expected_revision_id": "revision-a",
                "spec": {"kind": "interval", "interval_seconds": 120},
                "transfer_execution_route": "true",
            },
        )
    assert invalid_flag.value.status == 400

    with pytest.raises(ControlPlaneError) as arbitrary_route:
        client.post(
            "/v1/schedules/schedule-a/amend",
            headers=headers,
            json={
                "expected_revision_id": "revision-a",
                "spec": {"kind": "interval", "interval_seconds": 120},
                "execution_route": "prefect:" + "b" * 64,
            },
        )
    assert arbitrary_route.value.status == 400


def test_external_trigger_runs_sync_service_calls_in_worker_threads() -> None:
    request_thread = get_ident()
    service_threads: list[int] = []

    class ScheduleService:
        def authorize(self, *_args: object) -> None:
            service_threads.append(get_ident())

        def trigger_external(self, *_args: object) -> Any:
            service_threads.append(get_ident())
            return SimpleNamespace(
                status="pending",
                to_dict=lambda: {"status": "pending"},
            )

    router = APIRouter()
    service = ScheduleService()
    register_schedule_routes(
        router,
        SimpleNamespace(get_schedule_service=lambda: service),
        lambda: None,
    )
    external_route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.operation_id == "cp_external_schedule_trigger"
    )
    endpoint = external_route.endpoint
    schedule_id = "schedule-thread-check"
    revision_id = "revision-thread-check"
    scheduled_at = "2026-10-13T12:00:00Z"
    envelope = TriggerEnvelope(
        schedule_id=schedule_id,
        schedule_revision_id=revision_id,
        timer_owner_generation=1,
        occurrence_id=external_occurrence_id(schedule_id, revision_id, scheduled_at),
        scheduled_at=scheduled_at,
        delivery_attempt_id="delivery-thread-check",
        correlation_id="thread-check",
    )
    body = json.dumps(envelope.to_dict()).encode("utf-8")

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    async def invoke() -> None:
        request = Request({"type": "http", "headers": []}, receive)
        response = Response()
        result = await endpoint(schedule_id, request, response, _ctx())
        assert result["status"] == "pending"
        assert response.status_code == 202

    asyncio.run(invoke())
    assert len(service_threads) == 2
    assert all(thread_id != request_thread for thread_id in service_threads)
