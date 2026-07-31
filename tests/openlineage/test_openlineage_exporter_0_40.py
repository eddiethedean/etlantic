"""OpenLineage outbound export tests (CP2 / 040-L) — fake transport only."""

from __future__ import annotations

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    MemoryRegistryProvider,
    Principal,
    RegistryRevision,
    SecurityDomain,
    TenantRecord,
    TenantRef,
    WorkspaceRecord,
    WorkspaceRef,
    content_fingerprint,
)
from etlantic_openlineage import FakeTransport, OpenLineageExporter, build_run_event


def _ctx(tenant: str = "tenant-a", workspace: str = "ws-1") -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice", kind="human"),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="domain-a"),
    )


def _seed(provider: MemoryRegistryProvider, ctx: ControlPlaneContext) -> None:
    provider.tenants.put(
        ctx,
        TenantRecord(
            tenant_id=ctx.tenant.tenant_id,
            security_domain_id=ctx.security_domain.domain_id,
        ),
    )
    provider.workspaces.put(
        ctx,
        WorkspaceRecord(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
        ),
    )


def test_build_run_event_maps_plan_and_run_identity() -> None:
    event = build_run_event(
        plan_identity={
            "logical_id": "pipe-orders",
            "revision_id": "rev-1",
            "tenant_id": "tenant-a",
            "workspace_id": "ws-1",
            "content_fingerprint": "abc",
        },
        run_event={"run_id": "run-1", "status": "SUCCEEDED"},
    )
    assert event["eventType"] == "COMPLETE"
    assert event["job"]["name"] == "pipe-orders"
    assert event["run"]["runId"] == "run-1"
    assert event["job"]["facets"]["etlantic"]["revision_id"] == "rev-1"

    running = build_run_event(
        plan_identity={"logical_id": "pipe-orders"},
        run_event={"run_id": "run-2", "status": "RUNNING"},
    )
    assert running["eventType"] == "RUNNING"

    unknown = build_run_event(
        plan_identity={"logical_id": "pipe-orders"},
        run_event={"run_id": "run-3", "status": "QUEUED"},
    )
    assert unknown["eventType"] == "OTHER"


def test_exporter_success_emits_without_mutating_registry() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed(provider, ctx)
    content = {"v": 1}
    rev = RegistryRevision(
        logical_id="pipe-1",
        revision_id="rev-1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
        kind="pipeline",
    )
    provider.revisions.put_revision(ctx, rev)
    before = provider.revisions.get_revision(ctx, "rev-1")

    transport = FakeTransport()
    mutator_calls: list[str] = []

    def on_success(_event: object) -> None:
        mutator_calls.append("success")

    exporter = OpenLineageExporter(transport, on_success=on_success)
    event = exporter.export_run(
        plan_identity={
            "logical_id": "pipe-1",
            "revision_id": "rev-1",
            "tenant_id": "tenant-a",
            "workspace_id": "ws-1",
        },
        run_event={"run_id": "run-ok", "status": "START"},
    )
    assert event["eventType"] == "START"
    assert len(transport.events) == 1
    assert mutator_calls == ["success"]
    assert provider.revisions.get_revision(ctx, "rev-1") == before


def test_failing_transport_does_not_call_registry_mutators() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed(provider, ctx)
    content = {"v": 1}
    rev = RegistryRevision(
        logical_id="pipe-1",
        revision_id="rev-1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
        kind="pipeline",
    )
    provider.revisions.put_revision(ctx, rev)
    before = provider.revisions.get_revision(ctx, "rev-1")
    revision_count = len(provider.revisions._revisions)

    transport = FakeTransport(fail_with=RuntimeError("transport down"))
    mutator_calls: list[str] = []

    def on_success(_event: object) -> None:
        # Would mutate registry if incorrectly wired on failure path.
        mutator_calls.append("success")
        provider.revisions.put_revision(
            ctx,
            RegistryRevision(
                logical_id="pipe-1",
                revision_id="rev-should-not-exist",
                tenant_id="tenant-a",
                workspace_id="ws-1",
                content_fingerprint=content_fingerprint({"bad": True}),
                content={"bad": True},
                kind="pipeline",
            ),
        )

    exporter = OpenLineageExporter(transport, on_success=on_success)
    with pytest.raises(RuntimeError, match="transport down"):
        exporter.export_run(
            plan_identity={
                "logical_id": "pipe-1",
                "revision_id": "rev-1",
                "tenant_id": "tenant-a",
                "workspace_id": "ws-1",
            },
            run_event={"run_id": "run-fail", "status": "START"},
        )

    assert mutator_calls == []
    assert provider.revisions.get_revision(ctx, "rev-1") == before
    assert len(provider.revisions._revisions) == revision_count
    with pytest.raises(ControlPlaneError):
        provider.revisions.get_revision(ctx, "rev-should-not-exist")
