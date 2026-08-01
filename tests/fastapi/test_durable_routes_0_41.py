"""CP3 durable FastAPI routes + dual-write submit (0.41)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
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

DURABLE_ACTIONS = (
    "run.submit",
    "definition.read",
    "durable.outbox.read",
    "durable.outbox.write",
    "durable.cancel",
    "durable.lease.write",
    "durable.attempt.write",
    "durable.checkpoint.write",
    "durable.replay",
    "durable.preview.write",
)


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice", issuer="tests"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _client() -> tuple[TestClient, MemoryDurableWorkStore]:
    authz = MemoryAuthorizer()
    durable = MemoryDurableWorkStore()
    defs = MemoryDefinitionRepository()
    ctx = _ctx()
    defs.put(ctx, "pipe-1", {"name": "pipe-1"})
    for action in DURABLE_ACTIONS:
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
    )
    return TestClient(create_app(api)), durable


def test_submit_dual_writes_durable_accept_and_lease_routes() -> None:
    client, durable = _client()
    headers = {"X-Principal": "alice"}
    resp = client.post(
        "/v1/definitions/pipe-1/runs",
        headers={**headers, "Idempotency-Key": "run-1"},
        json={"payload": {"plan_fingerprint": "plan-abc"}},
    )
    assert resp.status_code == 202, resp.text
    pending = durable.pending_outbox(_ctx())
    assert pending and pending[0].payload_fingerprint

    out = client.get("/v1/durable/outbox", headers=headers)
    assert out.status_code == 200
    assert out.json()[0]["submission_id"] == pending[0].submission_id
    published = client.post(
        f"/v1/durable/outbox/{pending[0].outbox_id}/published",
        headers=headers,
    )
    assert published.status_code == 200
    lease = client.post(
        f"/v1/durable/submissions/{pending[0].submission_id}/leases",
        headers=headers,
        json={"owner_id": "host-1", "ttl_seconds": 30},
    )
    assert lease.status_code == 200
    token = lease.json()["fencing_token"]
    attempt = client.post(
        f"/v1/durable/submissions/{pending[0].submission_id}/attempts",
        headers=headers,
        json={"owner_id": "host-1", "fencing_token": token},
    )
    assert attempt.status_code == 200
    preview = client.post(
        "/v1/durable/previews",
        headers=headers,
        json={
            "preview_id": "pv1",
            "base_revision_id": "r1",
            "candidate_revision_id": "r2",
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(seconds=60)).isoformat(),
            "quota": 2,
            "code_fingerprint": "code",
            "plan_fingerprint": "plan",
            "commit_ref": "abc",
        },
    )
    assert preview.status_code == 200
    assert preview.json()["preview_id"] == "pv1"


def test_dual_write_reuses_cp1_submission_id_and_cancel_propagates() -> None:
    authz = MemoryAuthorizer()
    durable = MemoryDurableWorkStore()
    defs = MemoryDefinitionRepository()
    ctx = _ctx()
    defs.put(ctx, "pipe-1", {"name": "pipe-1"})
    for action in (*DURABLE_ACTIONS, "run.cancel", "run.read"):
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
    )
    client = TestClient(create_app(api))
    headers = {"X-Principal": "alice"}
    resp = client.post(
        "/v1/definitions/pipe-1/runs",
        headers={**headers, "Idempotency-Key": "corr-1"},
        json={"payload": {"plan_fingerprint": "plan-corr"}},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    cp1_id = body["submission_id"]
    pending = durable.pending_outbox(_ctx())
    assert pending and pending[0].submission_id == cp1_id
    cancel = client.post(f"/v1/runs/{body['resource_id']}/cancel", headers=headers)
    assert cancel.status_code == 200, cancel.text
    with pytest.raises(ControlPlaneError):
        durable.acquire_lease(_ctx(), cp1_id, owner_id="host-1", ttl_seconds=30)


def test_missing_durable_store_returns_501() -> None:
    authz = MemoryAuthorizer()
    defs = MemoryDefinitionRepository()
    ctx = _ctx()
    defs.put(ctx, "pipe-1", {"name": "pipe-1"})
    authz.grant(ctx, "durable.outbox.read")
    api = ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
        durable_work=None,
    )
    client = TestClient(create_app(api))
    resp = client.get("/v1/durable/outbox", headers={"X-Principal": "alice"})
    assert resp.status_code == 501
