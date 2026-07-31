"""SSE resume, disconnect/reconnect, and authz for CP1 run events (039-E)."""

from __future__ import annotations

import json

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
    tenant: str = "tenant-a", workspace: str = "ws-1", subject: str = "alice"
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject=subject),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _wired() -> tuple[TestClient, ETLanticAPI]:
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
    return TestClient(create_app(api)), api


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    current_id: str | None = None
    current_event: str | None = None
    data_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("id:"):
            current_id = line[3:].strip()
        elif line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif line == "" and data_lines:
            payload = json.loads("\n".join(data_lines))
            events.append(
                {
                    "id": current_id,
                    "event": current_event,
                    "data": payload,
                }
            )
            current_id = None
            current_event = None
            data_lines = []
    return events


def test_sse_history_reconnect_duplicate_suppression() -> None:
    client, _ = _wired()
    headers = {"X-Principal": "alice", "Idempotency-Key": "sse-1"}
    submit = client.post("/v1/definitions/pipe/runs", headers=headers, json={})
    assert submit.status_code == 202
    run_id = submit.json()["resource_id"]

    with client.stream(
        "GET",
        f"/v1/runs/{run_id}/events",
        headers={"X-Principal": "alice"},
    ) as stream:
        assert stream.status_code == 200
        assert "text/event-stream" in stream.headers["content-type"]
        first_body = "".join(stream.iter_text())
    first = _parse_sse(first_body)
    assert len(first) == 1
    assert first[0]["event"] == "run.accepted"
    assert first[0]["data"]["schema"] == "etlantic.control_plane.event/1"
    assert first[0]["data"]["payload"]["run_id"] == run_id
    cursor = first[0]["id"]
    assert cursor == first[0]["data"]["cursor"]

    cancel = client.post(f"/v1/runs/{run_id}/cancel", headers={"X-Principal": "alice"})
    assert cancel.status_code == 200

    # Reconnect with cursor: only events after cursor (duplicate suppression).
    with client.stream(
        "GET",
        f"/v1/runs/{run_id}/events",
        params={"cursor": cursor},
        headers={"X-Principal": "alice"},
    ) as stream:
        assert stream.status_code == 200
        resume_body = "".join(stream.iter_text())
    resumed = _parse_sse(resume_body)
    assert len(resumed) == 1
    assert resumed[0]["event"] == "run.cancel_requested"
    assert resumed[0]["data"]["kind"] == "run.cancel_requested"
    assert all(e["event"] != "run.accepted" for e in resumed)

    # Last-Event-ID header resume is equivalent.
    with client.stream(
        "GET",
        f"/v1/runs/{run_id}/events",
        headers={"X-Principal": "alice", "Last-Event-ID": cursor},
    ) as stream:
        assert stream.status_code == 200
        via_header = _parse_sse("".join(stream.iter_text()))
    assert [e["event"] for e in via_header] == ["run.cancel_requested"]


def test_sse_unknown_cursor_is_410() -> None:
    client, _ = _wired()
    headers = {"X-Principal": "alice", "Idempotency-Key": "sse-410"}
    submit = client.post("/v1/definitions/pipe/runs", headers=headers, json={})
    run_id = submit.json()["resource_id"]
    resp = client.get(
        f"/v1/runs/{run_id}/events",
        params={"cursor": "not-a-real-cursor"},
        headers={"X-Principal": "alice"},
    )
    assert resp.status_code == 410
    body = resp.json()
    assert body["code"] == "PMCP410"
    assert body["extensions"]["hint"] == "omit_cursor_or_last_event_id"


def test_sse_authz_deny_and_cross_tenant_404() -> None:
    client, api = _wired()
    headers = {"X-Principal": "alice", "Idempotency-Key": "sse-authz"}
    submit = client.post("/v1/definitions/pipe/runs", headers=headers, json={})
    run_id = submit.json()["resource_id"]

    # In-scope forbid via forbidden_resources → 403 (not opaque 404).
    api.authorizer.forbidden_resources.add(
        ("tenant-a", "ws-1", "run.events", f"run:{run_id}")
    )
    denied = client.get(
        f"/v1/runs/{run_id}/events",
        headers={"X-Principal": "alice"},
    )
    assert denied.status_code == 403

    # Cross-tenant: bob cannot observe alice's run (non-enumeration).
    api.authorizer.forbidden_resources.clear()
    cross = client.get(
        f"/v1/runs/{run_id}/events",
        headers={"X-Principal": "bob"},
    )
    assert cross.status_code == 404


def test_event_matches_run_requires_explicit_run_id() -> None:
    from etlantic.control_plane import ControlPlaneEvent
    from etlantic_fastapi.sse import event_matches_run

    base = dict(
        event_id="e1",
        sequence=1,
        cursor="c1",
        kind="run.accepted",
        created_at="2026-07-31T00:00:00Z",
    )
    assert event_matches_run(
        ControlPlaneEvent(**base, payload={"run_id": "run-1"}), "run-1"
    )
    assert not event_matches_run(
        ControlPlaneEvent(**base, payload={"acceptance_id": "run-1"}), "run-1"
    )
    assert not event_matches_run(
        ControlPlaneEvent(**base, payload={"submission_id": "run-1"}), "run-1"
    )


def test_memory_event_store_unknown_cursor_raises_gone() -> None:
    events = MemoryEventStore()
    ctx = _ctx()
    events.append(ctx, kind="run.accepted", payload={"run_id": "r1"})
    with pytest.raises(ControlPlaneError) as caught:
        events.list_after_cursor(ctx, "missing-cursor")
    assert caught.value.status == 410
