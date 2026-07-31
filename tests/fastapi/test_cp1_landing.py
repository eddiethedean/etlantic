"""Landing-zone watch submitter bridge outside core (039-L)."""

from __future__ import annotations

from pathlib import Path

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
from etlantic_fastapi.landing_sensor import (
    LandingWatchSubmitter,
    assert_no_file_bytes,
    build_submit_payload,
    local_files_binding_ref,
    make_testclient_submit_run,
)


def test_landing_sensor_module_is_outside_core() -> None:
    import etlantic_fastapi.landing_sensor as mod

    path = Path(mod.__file__ or "").resolve().as_posix()
    assert "etlantic_fastapi" in path
    assert "/src/etlantic/" not in path
    assert not path.endswith("/src/etlantic/landing_sensor.py")


def test_landing_watch_submitter_e2e(tmp_path: Path) -> None:
    secret_bytes = "SECRET_LANDING_ROW_SHOULD_NEVER_APPEAR"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    dropped = inbox / "events.csv"
    dropped.write_text(f"id,payload\n1,{secret_bytes}\n", encoding="utf-8")

    binding = local_files_binding_ref(
        root_ref="landing",
        root="inbox",
        glob="*.csv",
        mode="snapshot",
        provider="local-files",
    )
    definition = {
        "schema": "etlantic.pipeline/1",
        "name": "landing_pipe",
        "assets": {
            "landing_csv": dict(binding),
            "curated": "memory://curated",
        },
        # Binding refs only — never embed landing file contents.
        "note": "continuous watch is a submitter, not a third Extract kind",
    }
    assert_no_file_bytes(definition, forbidden=secret_bytes)

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
    ctx = ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )
    defs.put(ctx, "landing_pipe", definition)
    for action in ("definition.read", "run.submit", "run.read"):
        authz.grant(ctx, action)

    client = TestClient(create_app(api))
    submitter = LandingWatchSubmitter(
        watch_dir=inbox,
        definition_id="landing_pipe",
        submit_run=make_testclient_submit_run(client, principal="alice"),
        binding_ref=binding,
        tenant_id="tenant-a",
        workspace_id="ws-1",
        pattern="*.csv",
    )
    receipts = submitter.poll_once()
    assert len(receipts) == 1
    assert receipts[0]["status"] == "accepted"
    assert receipts[0]["schema"] == "etlantic.control_plane.accept_receipt/1"

    # Idempotent: same file does not create a second acceptance.
    assert submitter.poll_once() == []

    stored = dict(defs.get(ctx, "landing_pipe"))
    payload = build_submit_payload(
        definition_id="landing_pipe",
        binding_ref=binding,
        file_ref={"name": "events.csv", "relative": "events.csv"},
    )
    assert_no_file_bytes(stored, forbidden=secret_bytes)
    assert_no_file_bytes(payload, forbidden=secret_bytes)
    assert payload["landing"]["provider"] == "local-files"
    # Accepted payload kept by store must also be content-free.
    run = client.get(
        f"/v1/runs/{receipts[0]['resource_id']}",
        headers={"X-Principal": "alice"},
    )
    assert run.status_code == 200
    assert_no_file_bytes(run.json(), forbidden=secret_bytes)
    stored_payload = subs._payloads[(*ctx.scope_key, receipts[0]["idempotency_key"])]
    assert_no_file_bytes(stored_payload, forbidden=secret_bytes)
