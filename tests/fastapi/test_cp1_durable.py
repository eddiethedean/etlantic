"""Durable submit, observe, and multi-worker idempotency for CP1."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

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

ACTIONS = (
    "definition.read",
    "definition.validate",
    "definition.plan",
    "run.submit",
    "run.read",
    "run.cancel",
    "run.events",
    "run.report",
    "run.artifacts",
    "run.lineage",
    "schema.observations.list",
    "schema.observations.ack",
    "reliability.list",
)


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _wired() -> tuple[TestClient, MemorySubmissionStore, ETLanticAPI]:
    authz = MemoryAuthorizer()
    defs = MemoryDefinitionRepository()
    subs = MemorySubmissionStore()
    api = ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        submissions=subs,
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    ctx = _ctx()
    defs.put(ctx, "pipe", {"name": "pipe"})
    for action in ACTIONS:
        authz.grant(ctx, action)
    return TestClient(create_app(api)), subs, api


def test_submit_returns_202_and_status_cancel_report_artifacts_lineage() -> None:
    client, _, _ = _wired()
    headers = {"X-Principal": "alice", "Idempotency-Key": "idem-1"}
    submit = client.post("/v1/definitions/pipe/runs", headers=headers, json={})
    assert submit.status_code == 202
    receipt = submit.json()
    assert receipt["status"] == "accepted"
    run_id = receipt["resource_id"]

    # Idempotent replay
    again = client.post("/v1/definitions/pipe/runs", headers=headers, json={})
    assert again.status_code == 202
    assert again.json()["acceptance_id"] == receipt["acceptance_id"]

    status = client.get(f"/v1/runs/{run_id}", headers={"X-Principal": "alice"})
    assert status.status_code == 200
    assert status.json()["status"] == "accepted"

    cancel = client.post(f"/v1/runs/{run_id}/cancel", headers={"X-Principal": "alice"})
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancel_requested"

    report = client.get(f"/v1/runs/{run_id}/report", headers={"X-Principal": "alice"})
    assert report.status_code == 200
    assert report.json()["run_id"] == run_id

    arts = client.get(f"/v1/runs/{run_id}/artifacts", headers={"X-Principal": "alice"})
    assert arts.status_code == 200
    assert arts.json()["items"]

    lineage = client.get(f"/v1/runs/{run_id}/lineage", headers={"X-Principal": "alice"})
    assert lineage.status_code == 200
    assert lineage.json()["schema"] == "etlantic.control_plane.lineage_stub/1"


def test_schema_and_reliability_stubs_labeled() -> None:
    client, _, _ = _wired()
    headers = {"X-Principal": "alice"}
    obs = client.get("/v1/schema/observations", headers=headers)
    assert obs.status_code == 200
    body = obs.json()
    assert body["label"] == "observations"
    assert "not contract authority" in body["note"]

    ack = client.post("/v1/schema/observations/obs-1/ack", headers=headers)
    assert ack.status_code == 200
    assert (
        "not promote" in ack.json()["note"].lower()
        or "authority" in ack.json()["note"].lower()
    )

    rel = client.get("/v1/reliability", headers=headers)
    assert rel.status_code == 200
    assert rel.json()["schema"] == "etlantic.control_plane.reliability_stub/1"


def test_multi_worker_shared_memory_idempotent_submit() -> None:
    """Two 'workers' (threads) sharing one MemorySubmissionStore."""
    _, subs, api = _wired()
    app_a = create_app(api)
    app_b = create_app(api)
    client_a = TestClient(app_a)
    client_b = TestClient(app_b)
    headers = {"X-Principal": "alice", "Idempotency-Key": "shared-idem"}

    def submit(client: TestClient) -> dict:
        resp = client.post("/v1/definitions/pipe/runs", headers=headers, json={})
        assert resp.status_code == 202
        return resp.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(submit, client_a)
        f2 = pool.submit(submit, client_b)
        r1, r2 = f1.result(), f2.result()

    assert r1["acceptance_id"] == r2["acceptance_id"]
    assert r1["submission_id"] == r2["submission_id"]
    assert len(subs.poll_accepted(limit=10)) >= 1


def test_include_router_does_not_force_handlers() -> None:
    from etlantic.control_plane import ControlPlaneError
    from etlantic_fastapi import include_router
    from fastapi import FastAPI

    _, _, api = _wired()
    host = FastAPI()
    include_router(host, api)
    assert ControlPlaneError not in host.exception_handlers
