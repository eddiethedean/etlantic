"""OpenAPI 3.1 snapshot and generated-client smoke for CP1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from etlantic.control_plane import (
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryEventStore,
    MemorySubmissionStore,
)
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)

pytestmark = pytest.mark.fastapi

REQUIRED_OPERATION_IDS = {
    "cp_health",
    "cp_ready",
    "cp_list_definitions",
    "cp_get_definition",
    "cp_validate_definition",
    "cp_plan_definition",
    "cp_submit_run",
    "cp_get_run",
    "cp_cancel_run",
    "cp_stream_run_events",
    "cp_get_run_report",
    "cp_list_run_artifacts",
    "cp_get_run_lineage",
    "cp_list_schema_observations",
    "cp_ack_schema_observation",
    "cp_list_reliability",
}

SNAPSHOT = Path(__file__).parent / "openapi_cp1_snapshot.json"


def _build_api() -> ETLanticAPI:
    authz = MemoryAuthorizer()
    defs = MemoryDefinitionRepository()
    subs = MemorySubmissionStore()
    events = MemoryEventStore()
    return ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        submissions=subs,
        events=events,
        context_factory=membership_context_factory(
            {
                "alice": ("tenant-a", "ws-1", "development", "default"),
            }
        ),
        principal_dependency=principal_from_header,
    )


def test_openapi_31_and_stable_operation_ids() -> None:
    app = create_app(_build_api())
    schema = app.openapi()
    assert schema.get("openapi", "").startswith("3.")
    op_ids: set[str] = set()
    for path_item in schema["paths"].values():
        for method, op in path_item.items():
            if method.startswith("x-") or not isinstance(op, dict):
                continue
            op_id = op.get("operationId")
            assert op_id, f"missing operationId on {method}"
            op_ids.add(op_id)
    assert op_ids >= REQUIRED_OPERATION_IDS

    # Snapshot: fail if missing (do not auto-write silently).
    dump = {
        "openapi": schema["openapi"],
        "paths": sorted(schema["paths"]),
        "operationIds": sorted(op_ids),
    }
    assert SNAPSHOT.exists(), (
        f"OpenAPI snapshot missing at {SNAPSHOT}; regenerate intentionally "
        "and commit the updated snapshot."
    )
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert dump["operationIds"] == expected["operationIds"]
    assert dump["paths"] == expected["paths"]


def test_generated_client_smoke_dump_and_happy_path(tmp_path: Path) -> None:
    api = _build_api()
    ctx_defs = api.definitions
    from etlantic.control_plane import (
        ControlPlaneContext,
        EnvironmentRef,
        Principal,
        SecurityDomain,
        TenantRef,
        WorkspaceRef,
    )

    ctx = ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )
    ctx_defs.put(ctx, "pipe-1", {"name": "demo", "fingerprint": "fp1"})
    for action in (
        "definition.list",
        "definition.read",
        "definition.validate",
        "definition.plan",
        "run.submit",
        "run.read",
    ):
        api.authorizer.grant(ctx, action)

    app = create_app(api)
    openapi_path = tmp_path / "openapi.json"
    openapi_path.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    dumped = json.loads(openapi_path.read_text(encoding="utf-8"))
    op_ids = {
        op["operationId"]
        for path in dumped["paths"].values()
        for method, op in path.items()
        if isinstance(op, dict) and "operationId" in op
    }
    assert op_ids >= REQUIRED_OPERATION_IDS

    client = TestClient(app)
    headers = {"X-Principal": "alice", "Idempotency-Key": "idem-smoke-1"}
    listed = client.get("/v1/definitions", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["definition_id"] == "pipe-1"

    submit = client.post(
        "/v1/definitions/pipe-1/runs",
        headers=headers,
        json={},
    )
    assert submit.status_code == 202
    body = submit.json()
    assert body["status"] == "accepted"
    assert body["submission_id"]
    run_id = body["resource_id"] or body["submission_id"]
    status = client.get(f"/v1/runs/{run_id}", headers={"X-Principal": "alice"})
    assert status.status_code == 200
    assert status.json()["status"] == "accepted"
