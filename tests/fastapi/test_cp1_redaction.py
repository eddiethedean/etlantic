"""Operability: CP1 errors, SSE frames, and reports stay secret-free."""

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
    ControlPlaneEvent,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryEventStore,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    assert_no_secrets,
    redact_control_plane_payload,
)
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)
from etlantic_fastapi.sse import format_sse_message

SECRET = "super-secret-token"
ACTIONS = (
    "definition.read",
    "run.submit",
    "run.read",
    "run.report",
    "run.events",
    "run.artifacts",
)


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _client() -> tuple[TestClient, MemoryEventStore]:
    authz = MemoryAuthorizer()
    defs = MemoryDefinitionRepository()
    events = MemoryEventStore()
    api = ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        submissions=MemorySubmissionStore(),
        events=events,
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    ctx = _ctx()
    defs.put(ctx, "pipe", {"name": "pipe"})
    for action in ACTIONS:
        authz.grant(ctx, action)
    return TestClient(create_app(api)), events


def test_problem_details_redact_secret_extensions() -> None:
    err = ControlPlaneError.conflict(
        f"reuse with password={SECRET}",
        extensions={"api_key": SECRET, "token": SECRET, "safe": "ok"},
    )
    blob = json.dumps(err.to_dict())
    assert_no_secrets(blob, sentinel=SECRET)
    payload = err.to_dict()
    assert payload["extensions"]["api_key"] == "***"
    assert payload["extensions"]["token"] == "***"
    assert payload["extensions"]["safe"] == "ok"
    assert SECRET not in payload["detail"]


def test_event_envelope_redacts_payload_secrets() -> None:
    event = ControlPlaneEvent(
        event_id="evt-1",
        sequence=1,
        cursor="cur-1",
        kind="run.accepted",
        created_at="2026-07-31T00:00:00Z",
        payload={"password": SECRET, "run_id": "sub-1", "note": "ok"},
    )
    blob = json.dumps(event.to_dict())
    assert_no_secrets(blob, sentinel=SECRET)
    assert event.to_dict()["payload"]["password"] == "***"
    assert event.to_dict()["payload"]["run_id"] == "sub-1"


def test_sse_frame_and_report_have_no_secrets() -> None:
    client, events = _client()
    ctx = _ctx()
    events.append(
        ctx,
        kind="run.secret_probe",
        payload={"api_key": SECRET, "authorization": f"Bearer {SECRET}"},
    )
    # Direct SSE encoding path
    stored = events.list_after_cursor(ctx, None, limit=10)[0]
    frame = format_sse_message(stored)
    assert_no_secrets(frame, sentinel=SECRET)

    headers = {"X-Principal": "alice", "Idempotency-Key": "redact-1"}
    submit = client.post("/v1/definitions/pipe/runs", headers=headers, json={})
    assert submit.status_code == 202
    run_id = submit.json()["resource_id"] or submit.json()["submission_id"]

    # Inject a secret into a follow-up event and stream
    events.append(
        ctx,
        kind="run.probe",
        payload={"run_id": run_id, "secret": SECRET, "password": SECRET},
    )
    stream = client.get(
        f"/v1/runs/{run_id}/events",
        headers={"X-Principal": "alice"},
    )
    assert stream.status_code == 200
    assert_no_secrets(stream.text, sentinel=SECRET)

    report = client.get(
        f"/v1/runs/{run_id}/report",
        headers={"X-Principal": "alice"},
    )
    assert report.status_code == 200
    assert_no_secrets(report.text, sentinel=SECRET)
    # Metadata path still redacts if a secret-like key is present
    redacted = redact_control_plane_payload({"token": SECRET, "run_id": run_id})
    assert redacted["token"] == "***"
    assert redacted["run_id"] == run_id
