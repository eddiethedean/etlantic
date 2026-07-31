"""Isolation-profile matrix evidence tests (CP2 / 040-O exit).

Profiles (ADR-017):
- isolated-deployment
- dedicated-schema
- shared-service + second control (RLS or tenant credentials)

A shared-service profile that relies only on application ``WHERE tenant_id``
is non-conforming. The stub below proves a second filter is required.
"""

from __future__ import annotations

import json
from pathlib import Path

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

EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "11_DEVELOPMENT"
    / "isolation_profile_matrix_0_40.json"
)


def _ctx(
    tenant: str,
    workspace: str,
    domain: str,
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice", kind="human"),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id=domain),
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


def test_isolation_profile_evidence_json_present() -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert payload["schema"] == "etlantic.isolation_profile_matrix/1"
    profiles = {row["profile"] for row in payload["profiles"]}
    assert profiles == {
        "isolated-deployment",
        "dedicated-schema",
        "shared-service",
    }
    shared = next(r for r in payload["profiles"] if r["profile"] == "shared-service")
    assert shared["second_control_required"] is True
    assert shared["where_only_insufficient"] is True
    assert payload["cp2_production_multi_tenant_claim"] is False


def test_two_tenant_two_workspace_matrix_memory() -> None:
    provider = MemoryRegistryProvider()
    matrix = (
        ("tenant-a", "ws-1", "domain-a"),
        ("tenant-a", "ws-2", "domain-a"),
        ("tenant-b", "ws-1", "domain-b"),
        ("tenant-b", "ws-2", "domain-b"),
    )
    for tenant, workspace, domain in matrix:
        ctx = _ctx(tenant, workspace, domain)
        _seed(provider, ctx)
        content = {"t": tenant, "w": workspace}
        provider.revisions.put_revision(
            ctx,
            RegistryRevision(
                logical_id="pipe-1",
                revision_id=f"rev-{tenant}-{workspace}",
                tenant_id=tenant,
                workspace_id=workspace,
                content_fingerprint=content_fingerprint(content),
                content=content,
                kind="pipeline",
            ),
        )

    for tenant, workspace, domain in matrix:
        ctx = _ctx(tenant, workspace, domain)
        own = provider.revisions.get_revision(ctx, f"rev-{tenant}-{workspace}")
        assert own.tenant_id == tenant
        assert own.workspace_id == workspace
        for other_t, other_w, _ in matrix:
            if (other_t, other_w) == (tenant, workspace):
                continue
            with pytest.raises(ControlPlaneError):
                provider.revisions.get_revision(ctx, f"rev-{other_t}-{other_w}")


def test_shared_service_where_alone_is_insufficient() -> None:
    """Documented RLS stub: a naive WHERE-only filter is not a second control.

    Simulates shared-service rows visible under a stolen/forged tenant filter
    when the independent second control (RLS / credentials) is absent.
    """

    class SharedTable:
        def __init__(self) -> None:
            self.rows = [
                {"tenant_id": "tenant-a", "secret": "a"},
                {"tenant_id": "tenant-b", "secret": "b"},
            ]

        def select_where_only(self, tenant_id: str) -> list[dict[str, str]]:
            # Application-only filter — attacker can pass any tenant_id.
            return [row for row in self.rows if row["tenant_id"] == tenant_id]

        def select_with_second_control(
            self,
            *,
            claimed_tenant_id: str,
            session_tenant_id: str,
        ) -> list[dict[str, str]]:
            # Second control: session credential must match claimed tenant.
            if claimed_tenant_id != session_tenant_id:
                return []
            return self.select_where_only(claimed_tenant_id)

    table = SharedTable()
    # WHERE alone: forged claim discloses another tenant.
    leaked = table.select_where_only("tenant-b")
    assert leaked and leaked[0]["secret"] == "b"

    # With second control (session credential), forged claim fails closed.
    blocked = table.select_with_second_control(
        claimed_tenant_id="tenant-b",
        session_tenant_id="tenant-a",
    )
    assert blocked == []
    allowed = table.select_with_second_control(
        claimed_tenant_id="tenant-a",
        session_tenant_id="tenant-a",
    )
    assert allowed and allowed[0]["secret"] == "a"


@pytest.mark.sqlmodel
def test_two_tenant_matrix_sqlmodel_compound_keys() -> None:
    from etlantic_sqlmodel.control_plane import (
        SqlModelRegistryProvider,
        create_sqlite_engine,
    )
    from etlantic_sqlmodel.migrations import apply_migrations

    engine = create_sqlite_engine("sqlite://")
    apply_migrations(engine)
    provider = SqlModelRegistryProvider(engine)
    ctx_a = _ctx("tenant-a", "ws-1", "domain-a")
    ctx_b = _ctx("tenant-b", "ws-1", "domain-b")
    for ctx in (ctx_a, ctx_b):
        _seed(provider, ctx)  # type: ignore[arg-type]
        content = {"t": ctx.tenant.tenant_id}
        provider.revisions.put_revision(
            ctx,
            RegistryRevision(
                logical_id="pipe-1",
                revision_id=f"rev-{ctx.tenant.tenant_id}",
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                content_fingerprint=content_fingerprint(content),
                content=content,
                kind="pipeline",
            ),
        )
    assert (
        provider.revisions.get_revision(ctx_a, "rev-tenant-a").tenant_id == "tenant-a"
    )
    with pytest.raises(ControlPlaneError):
        provider.revisions.get_revision(ctx_a, "rev-tenant-b")
