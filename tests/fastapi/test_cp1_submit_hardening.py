"""CP1 submit hardening: event gating, definition_id force, scoped poll (0.39)."""

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
    "definition.read",
    "run.submit",
    "run.read",
    "run.cancel",
    "run.events",
)


def _ctx(
    tenant: str = "tenant-a",
    workspace: str = "ws-1",
    subject: str = "alice",
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject=subject),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _wired() -> tuple[TestClient, MemorySubmissionStore, MemoryEventStore, ETLanticAPI]:
    authz = MemoryAuthorizer()
    defs = MemoryDefinitionRepository()
    subs = MemorySubmissionStore()
    events = MemoryEventStore()
    api = ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        submissions=subs,
        events=events,
        context_factory=membership_context_factory(
            {
                "alice": ("tenant-a", "ws-1", "development", "default"),
                "bob": ("tenant-b", "ws-1", "development", "default"),
            }
        ),
        principal_dependency=principal_from_header,
    )
    alice = _ctx()
    bob = _ctx(tenant="tenant-b", subject="bob")
    defs.put(alice, "pipe", {"name": "pipe"})
    defs.put(bob, "pipe", {"name": "pipe"})
    for action in ACTIONS:
        authz.grant(alice, action)
        authz.grant(bob, action)
    return TestClient(create_app(api)), subs, events, api


def test_double_submit_emits_one_accepted_event() -> None:
    client, _, events, _ = _wired()
    headers = {"X-Principal": "alice", "Idempotency-Key": "idem-once"}
    first = client.post("/v1/definitions/pipe/runs", headers=headers, json={})
    second = client.post("/v1/definitions/pipe/runs", headers=headers, json={})
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["acceptance_id"] == second.json()["acceptance_id"]

    listed = events.list_after_cursor(_ctx(), None, limit=100)
    accepted = [e for e in listed if e.kind == "run.accepted"]
    assert len(accepted) == 1


def test_double_cancel_emits_one_cancel_event() -> None:
    client, _, events, _ = _wired()
    headers = {"X-Principal": "alice", "Idempotency-Key": "idem-cancel"}
    submit = client.post("/v1/definitions/pipe/runs", headers=headers, json={})
    run_id = submit.json()["resource_id"]
    c1 = client.post(f"/v1/runs/{run_id}/cancel", headers={"X-Principal": "alice"})
    c2 = client.post(f"/v1/runs/{run_id}/cancel", headers={"X-Principal": "alice"})
    assert c1.status_code == 200
    assert c2.status_code == 200
    listed = events.list_after_cursor(_ctx(), None, limit=100)
    cancels = [e for e in listed if e.kind == "run.cancel_requested"]
    assert len(cancels) == 1


def test_definition_id_mismatch_rejected() -> None:
    client, _, _, _ = _wired()
    headers = {"X-Principal": "alice", "Idempotency-Key": "idem-def"}
    resp = client.post(
        "/v1/definitions/pipe/runs",
        headers=headers,
        json={"payload": {"definition_id": "other-pipe"}},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == 400


def test_definition_id_forced_from_path() -> None:
    client, subs, _, _ = _wired()
    headers = {"X-Principal": "alice", "Idempotency-Key": "idem-force"}
    resp = client.post(
        "/v1/definitions/pipe/runs",
        headers=headers,
        json={"payload": {"extra": 1}},
    )
    assert resp.status_code == 202
    run_id = resp.json()["resource_id"]
    record = subs.get_run(_ctx(), run_id)
    assert record["definition_id"] == "pipe"


def test_poll_accepted_scoped_to_caller_tenant() -> None:
    client, subs, _, _ = _wired()
    alice_headers = {"X-Principal": "alice", "Idempotency-Key": "idem-a"}
    bob_headers = {"X-Principal": "bob", "Idempotency-Key": "idem-b"}
    assert (
        client.post(
            "/v1/definitions/pipe/runs", headers=alice_headers, json={}
        ).status_code
        == 202
    )
    assert (
        client.post(
            "/v1/definitions/pipe/runs", headers=bob_headers, json={}
        ).status_code
        == 202
    )
    alice_poll = subs.poll_accepted(_ctx(), limit=10)
    bob_poll = subs.poll_accepted(_ctx(tenant="tenant-b", subject="bob"), limit=10)
    assert len(alice_poll) == 1
    assert len(bob_poll) == 1
    assert alice_poll[0]["tenant_id"] == "tenant-a"
    assert bob_poll[0]["tenant_id"] == "tenant-b"
    assert all(r["tenant_id"] == "tenant-a" for r in alice_poll)
