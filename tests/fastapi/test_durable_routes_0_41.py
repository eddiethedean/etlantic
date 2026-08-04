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


def test_durable_accept_failure_compensates_cp1_create() -> None:
    class _BoomDurable(MemoryDurableWorkStore):
        def accept(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("durable unavailable")

    authz = MemoryAuthorizer()
    defs = MemoryDefinitionRepository()
    submissions = MemorySubmissionStore()
    ctx = _ctx()
    defs.put(ctx, "pipe-1", {"name": "pipe-1"})
    for action in (*DURABLE_ACTIONS, "run.read"):
        authz.grant(ctx, action)
    api = ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        submissions=submissions,
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
        durable_work=_BoomDurable(),
    )
    client = TestClient(create_app(api))
    resp = client.post(
        "/v1/definitions/pipe-1/runs",
        headers={"X-Principal": "alice", "Idempotency-Key": "boom-1"},
        json={"payload": {"plan_fingerprint": "plan"}},
    )
    assert resp.status_code == 503, resp.text
    assert submissions._runs == {} or all(
        row.get("status") == "cancel_requested" for row in submissions._runs.values()
    )


def test_checkpoint_cas_requires_fencing_on_wire() -> None:
    client, durable = _client()
    headers = {"X-Principal": "alice"}
    resp = client.post(
        "/v1/definitions/pipe-1/runs",
        headers={**headers, "Idempotency-Key": "cas-1"},
        json={"payload": {"plan_fingerprint": "plan"}},
    )
    assert resp.status_code == 202
    submission_id = resp.json()["submission_id"]
    lease = client.post(
        f"/v1/durable/submissions/{submission_id}/leases",
        headers=headers,
        json={"owner_id": "host-1", "ttl_seconds": 30},
    )
    token = lease.json()["fencing_token"]
    attempt = client.post(
        f"/v1/durable/submissions/{submission_id}/attempts",
        headers=headers,
        json={"owner_id": "host-1", "fencing_token": token},
    )
    missing = client.post(
        "/v1/durable/checkpoints/cursor:main/cas",
        headers=headers,
        json={"value_fingerprint": "v1", "expected_version": None},
    )
    assert missing.status_code == 422
    ok = client.post(
        "/v1/durable/checkpoints/cursor:main/cas",
        headers=headers,
        json={
            "value_fingerprint": "v1",
            "expected_version": None,
            "attempt_id": attempt.json()["attempt_id"],
            "fencing_token": token,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["version"] == 1
    assert durable  # keep reference live for GC clarity


def test_unknown_profile_fails_closed_on_validate() -> None:
    authz = MemoryAuthorizer()
    defs = MemoryDefinitionRepository()
    ctx = _ctx()
    defs.put(
        ctx,
        "pipe-1",
        {"schema": "etlantic.pipeline/1", "name": "pipe-1", "nodes": []},
    )
    authz.grant(ctx, "definition.read")
    authz.grant(ctx, "definition.validate")
    api = ETLanticAPI(
        authorizer=authz,
        definitions=defs,
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        profile="definitely-not-a-real-profile-name",
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    client = TestClient(create_app(api))
    resp = client.post(
        "/v1/definitions/pipe-1/validate",
        headers={"X-Principal": "alice"},
    )
    assert resp.status_code == 400, resp.text


def test_durable_effects_repair_diagnose_shadow_routes() -> None:
    headers = {"X-Principal": "alice"}
    ctx = _ctx()
    authz = MemoryAuthorizer()
    durable = MemoryDurableWorkStore()
    defs = MemoryDefinitionRepository()
    for action in (
        *DURABLE_ACTIONS,
        "durable.effect.write",
        "durable.repair",
        "durable.checkpoint.write",
        "durable.shadow.write",
    ):
        authz.grant(ctx, action)
    defs.put(ctx, "pipe-1", {"name": "pipe-1"})
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
    resp = client.post(
        "/v1/definitions/pipe-1/runs",
        headers={**headers, "Idempotency-Key": "fx-1"},
        json={"payload": {"plan_fingerprint": "plan-fx"}},
    )
    assert resp.status_code == 202, resp.text
    submission_id = resp.json()["submission_id"]
    pending = durable.pending_outbox(ctx)
    assert pending
    client.post(
        f"/v1/durable/outbox/{pending[0].outbox_id}/published",
        headers=headers,
    )
    lease = client.post(
        f"/v1/durable/submissions/{submission_id}/leases",
        headers=headers,
        json={"owner_id": "host-1", "ttl_seconds": 30},
    )
    token = lease.json()["fencing_token"]
    attempt = client.post(
        f"/v1/durable/submissions/{submission_id}/attempts",
        headers=headers,
        json={"owner_id": "host-1", "fencing_token": token},
    )
    attempt_id = attempt.json()["attempt_id"]
    checkpoint_id = "checkpoint:main"
    cas = client.post(
        f"/v1/durable/checkpoints/{checkpoint_id}/cas",
        headers=headers,
        json={
            "attempt_id": attempt_id,
            "fencing_token": token,
            "expected_version": None,
            "value_fingerprint": "v1",
        },
    )
    assert cas.status_code == 200, cas.text

    effect = client.post(
        "/v1/durable/effects",
        headers=headers,
        json={
            "effect_id": "eff-1",
            "submission_id": submission_id,
            "status": "pending",
        },
    )
    assert effect.status_code == 200, effect.text

    repair = client.post(
        f"/v1/durable/submissions/{submission_id}/repair",
        headers=headers,
        json={},
    )
    assert repair.status_code == 200, repair.text

    diagnose = client.post(
        f"/v1/durable/checkpoints/{checkpoint_id}/diagnose",
        headers=headers,
        json={"kind": "corruption", "detail": "test"},
    )
    assert diagnose.status_code == 200, diagnose.text
    assert diagnose.json()["checkpoint_id"] == checkpoint_id

    get_diag = client.get(
        f"/v1/durable/checkpoints/{checkpoint_id}/diagnose",
        headers=headers,
    )
    assert get_diag.status_code == 405

    preview = client.post(
        "/v1/durable/previews",
        headers=headers,
        json={
            "preview_id": "pv-shadow",
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
    shadow = client.post(
        "/v1/durable/shadow",
        headers=headers,
        json={
            "shadow_run_id": "sh-1",
            "preview_id": "pv-shadow",
            "submission_id": submission_id,
        },
    )
    assert shadow.status_code == 200, shadow.text
    assert shadow.json()["shadow_run_id"] == "sh-1"
