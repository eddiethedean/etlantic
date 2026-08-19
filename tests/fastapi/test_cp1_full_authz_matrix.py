"""Full CP1 authz matrix: every operationId x two tenants + two workspaces."""

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

# Resource-addressed ops: cross-tenant/workspace id → opaque 404.
CROSS_TENANT_404_CASES: list[tuple[str, str, str, dict | None]] = [
    ("cp_get_definition", "GET", "/v1/definitions/{definition_id}", None),
    (
        "cp_validate_definition",
        "POST",
        "/v1/definitions/{definition_id}/validate",
        None,
    ),
    ("cp_plan_definition", "POST", "/v1/definitions/{definition_id}/plan", None),
    (
        "cp_definition_context",
        "POST",
        "/v1/definitions/{definition_id}/context",
        None,
    ),
    ("cp_submit_run", "POST", "/v1/definitions/{definition_id}/runs", {}),
    ("cp_get_run", "GET", "/v1/runs/{run_id}", None),
    ("cp_cancel_run", "POST", "/v1/runs/{run_id}/cancel", None),
    ("cp_stream_run_events", "GET", "/v1/runs/{run_id}/events", None),
    ("cp_get_run_report", "GET", "/v1/runs/{run_id}/report", None),
    ("cp_list_run_artifacts", "GET", "/v1/runs/{run_id}/artifacts", None),
    ("cp_get_run_lineage", "GET", "/v1/runs/{run_id}/lineage", None),
]

# Caller-scoped list/ack ops: allow in-tenant; never leak foreign ids.
SCOPED_LIST_CASES: list[tuple[str, str, str, dict | None]] = [
    ("cp_list_definitions", "GET", "/v1/definitions", None),
    ("cp_list_schema_observations", "GET", "/v1/schema/observations", None),
    (
        "cp_ack_schema_observation",
        "POST",
        "/v1/schema/observations/{observation_id}/ack",
        None,
    ),
    ("cp_list_reliability", "GET", "/v1/reliability", None),
]

PUBLIC_OPERATION_IDS = {"cp_health", "cp_ready"}

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


def _build() -> tuple[TestClient, str, ETLanticAPI]:
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
                "alice-ws2": ("tenant-a", "ws-2", "development", "default"),
                "bob": ("tenant-b", "ws-1", "development", "default"),
            }
        ),
        principal_dependency=principal_from_header,
        known_observation_ids={"obs-1"},
    )
    a = _ctx("tenant-a", "ws-1", "alice")
    a2 = _ctx("tenant-a", "ws-2", "alice-ws2")
    b = _ctx("tenant-b", "ws-1", "bob")
    defs.put(a, "pipe-a", {"owner": "a"})
    defs.put(a2, "pipe-a2", {"owner": "a2"})
    defs.put(b, "pipe-b", {"owner": "b"})
    for action in ACTIONS:
        authz.grant(a, action)
        authz.grant(a2, action)
        authz.grant(b, action)
    client = TestClient(create_app(api))
    submit = client.post(
        "/v1/definitions/pipe-a/runs",
        headers={"X-Principal": "alice", "Idempotency-Key": "matrix-seed"},
        json={},
    )
    assert submit.status_code == 202
    run_id = submit.json()["resource_id"] or submit.json()["submission_id"]
    return client, run_id, api


def _path(template: str, *, definition_id: str, run_id: str) -> str:
    return (
        template.replace("{definition_id}", definition_id)
        .replace("{run_id}", run_id)
        .replace("{observation_id}", "obs-1")
    )


def test_public_health_ready_unauthenticated() -> None:
    client, _, _ = _build()
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_ready_503_when_stores_missing() -> None:
    client, _, api = _build()
    api.events = None  # type: ignore[assignment]
    ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["status"] == "not_ready"
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    "operation_id,method,template,body",
    CROSS_TENANT_404_CASES,
    ids=[c[0] for c in CROSS_TENANT_404_CASES],
)
def test_cross_tenant_resource_is_404(
    operation_id: str,
    method: str,
    template: str,
    body: dict | None,
) -> None:
    del operation_id
    client, run_id, _ = _build()
    path = _path(template, definition_id="pipe-a", run_id=run_id)
    headers = {"X-Principal": "bob"}
    if template.endswith("/runs") and method == "POST":
        headers["Idempotency-Key"] = "bob-cross"
    resp = client.request(method, path, headers=headers, json=body)
    assert resp.status_code == 404, (method, path, resp.status_code, resp.text)


@pytest.mark.parametrize(
    "operation_id,method,template,body",
    CROSS_TENANT_404_CASES,
    ids=[f"ws-{c[0]}" for c in CROSS_TENANT_404_CASES],
)
def test_cross_workspace_same_tenant_is_404(
    operation_id: str,
    method: str,
    template: str,
    body: dict | None,
) -> None:
    del operation_id
    client, run_id, _ = _build()
    path = _path(template, definition_id="pipe-a", run_id=run_id)
    headers = {"X-Principal": "alice-ws2"}
    if template.endswith("/runs") and method == "POST":
        headers["Idempotency-Key"] = "alice-ws2-cross"
    resp = client.request(method, path, headers=headers, json=body)
    assert resp.status_code == 404, (method, path, resp.status_code, resp.text)


@pytest.mark.parametrize(
    "operation_id,method,template,body",
    CROSS_TENANT_404_CASES + SCOPED_LIST_CASES,
    ids=[c[0] for c in CROSS_TENANT_404_CASES + SCOPED_LIST_CASES],
)
def test_in_tenant_allow(
    operation_id: str,
    method: str,
    template: str,
    body: dict | None,
) -> None:
    client, run_id, _ = _build()
    path = _path(template, definition_id="pipe-a", run_id=run_id)
    headers = {"X-Principal": "alice"}
    if operation_id == "cp_submit_run":
        headers["Idempotency-Key"] = "alice-allow"
    resp = client.request(method, path, headers=headers, json=body)
    assert resp.status_code in {200, 202}, (
        operation_id,
        method,
        path,
        resp.status_code,
        resp.text,
    )


def test_list_definitions_never_leaks_cross_tenant_or_workspace_ids() -> None:
    client, _, _ = _build()
    alice = client.get("/v1/definitions", headers={"X-Principal": "alice"})
    alice_ws2 = client.get("/v1/definitions", headers={"X-Principal": "alice-ws2"})
    bob = client.get("/v1/definitions", headers={"X-Principal": "bob"})
    assert alice.status_code == 200 and bob.status_code == 200
    alice_ids = {i["definition_id"] for i in alice.json()["items"]}
    alice_ws2_ids = {i["definition_id"] for i in alice_ws2.json()["items"]}
    bob_ids = {i["definition_id"] for i in bob.json()["items"]}
    assert alice_ids == {"pipe-a"}
    assert alice_ws2_ids == {"pipe-a2"}
    assert bob_ids == {"pipe-b"}
    assert "pipe-a" not in bob_ids
    assert "pipe-a" not in alice_ws2_ids
    assert "pipe-b" not in alice_ids


def test_unauthenticated_protected_is_401() -> None:
    client, run_id, _ = _build()
    path = _path(
        "/v1/definitions/{definition_id}", definition_id="pipe-a", run_id=run_id
    )
    assert client.get(path).status_code == 401


def test_matrix_covers_all_protected_operation_ids() -> None:
    from tests.fastapi.test_cp1_openapi import REQUIRED_OPERATION_IDS

    covered = (
        {c[0] for c in CROSS_TENANT_404_CASES}
        | {c[0] for c in SCOPED_LIST_CASES}
        | PUBLIC_OPERATION_IDS
    )
    missing = REQUIRED_OPERATION_IDS - covered
    assert not missing, f"authz matrix missing operationIds: {sorted(missing)}"
