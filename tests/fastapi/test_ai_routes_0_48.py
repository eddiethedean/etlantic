"""FastAPI 0.48 context and proposal-validate routes."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from tests.fixtures.sample_pipeline import SamplePipeline

from etlantic.authoring.normalize import definition_from_pipeline
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
    for action in ("definition.read",):
        authz.grant(ctx, action)
    defs = MemoryDefinitionRepository()
    defn = definition_from_pipeline(SamplePipeline)
    defs.put(ctx, "pipe-1", defn.to_dict())
    api = ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    return TestClient(create_app(api))


def test_context_and_proposal_validate_routes() -> None:
    client = _client()
    headers = {"X-Principal": "alice"}
    context = client.post("/v1/definitions/pipe-1/context", headers=headers)
    assert context.status_code == 200
    body = context.json()
    assert body["schema"] == "etlantic.context_bundle/1"
    assert body["redacted"] is True

    missing = client.post("/v1/definitions/other/context", headers=headers)
    assert missing.status_code == 404

    denied = client.post("/v1/definitions/pipe-1/context")
    assert denied.status_code in (401, 403, 404)

    apply_route = client.post(
        "/v1/proposals/apply",
        headers=headers,
        json={"proposal": {"schema": "etlantic.proposal/1"}},
    )
    assert apply_route.status_code == 404

    validated = client.post(
        "/v1/proposals/validate",
        headers=headers,
        json={
            "definition_id": "pipe-1",
            "proposal": {
                "schema": "etlantic.proposal/1",
                "task_id": "scaffold_model",
                "files": [{"path": "ok.py", "content": "x = 1\n"}],
            },
        },
    )
    assert validated.status_code == 200
    payload = validated.json()
    assert payload["applied"] is False
    assert payload["ok"] is True
