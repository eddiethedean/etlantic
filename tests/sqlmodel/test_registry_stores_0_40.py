"""SQLModel CP2 registry stores, migrations, and memory conformance (0.40 / 040-P)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from etlantic.control_plane import (
    AliasRecord,
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    LifecycleState,
    MemoryRegistryProvider,
    Principal,
    RegistryDefinitionRepository,
    RegistryRevision,
    SecurityDomain,
    TenantRecord,
    TenantRef,
    WorkspaceRecord,
    WorkspaceRef,
    content_fingerprint,
)
from etlantic_sqlmodel.control_plane import (
    SqlModelRegistryProvider,
    create_sqlite_engine,
)
from etlantic_sqlmodel.migrations import (
    apply_migrations,
    current_version,
    downgrade,
    upgrade,
)

pytestmark = pytest.mark.sqlmodel


def _ctx(
    *,
    tenant: str = "tenant-a",
    workspace: str = "ws-1",
    domain: str = "domain-a",
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice", kind="human"),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id=domain),
    )


def _seed(provider, ctx: ControlPlaneContext) -> None:
    provider.tenants.put(
        ctx,
        TenantRecord(
            tenant_id=ctx.tenant.tenant_id,
            security_domain_id=ctx.security_domain.domain_id,
            display_name=ctx.tenant.tenant_id,
        ),
    )
    provider.workspaces.put(
        ctx,
        WorkspaceRecord(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            display_name=ctx.workspace.workspace_id,
        ),
    )


def test_migration_apply_on_empty_db_and_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "registry.db"
    engine = create_sqlite_engine(f"sqlite:///{db}")
    assert current_version(engine) is None
    applied = apply_migrations(engine)
    assert applied == "003_cp4_governance"
    assert current_version(engine) == "003_cp4_governance"

    provider = SqlModelRegistryProvider(engine)
    ctx = _ctx()
    _seed(provider, ctx)

    content = {"name": "orders"}
    rev = RegistryRevision(
        logical_id="pipe-orders",
        revision_id="rev-1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
        kind="pipeline",
    )
    provider.revisions.put_revision(ctx, rev)

    # Restart against same file.
    engine2 = create_sqlite_engine(f"sqlite:///{db}")
    provider2 = SqlModelRegistryProvider(engine2)
    tenant = provider2.tenants.get(ctx, "tenant-a")
    assert tenant.tenant_id == "tenant-a"
    workspace = provider2.workspaces.get(ctx, "ws-1")
    assert workspace.workspace_id == "ws-1"
    got = provider2.revisions.get_revision(ctx, "rev-1")
    assert got.content == content
    assert got.content_fingerprint == content_fingerprint(content)


def test_migration_upgrade_downgrade(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    upgrade(engine)
    assert current_version(engine) == "003_cp4_governance"
    downgrade(engine, target="001_registry_cp2")
    assert current_version(engine) == "001_registry_cp2"
    downgrade(engine, target=None)
    assert current_version(engine) is None


def test_sqlmodel_promote_and_suspend() -> None:
    engine = create_sqlite_engine("sqlite://")
    apply_migrations(engine)
    provider = SqlModelRegistryProvider(engine)
    ctx = _ctx()
    _seed(provider, ctx)

    content = {"stage": "dev"}
    provider.revisions.put_revision(
        ctx,
        RegistryRevision(
            logical_id="pipe-1",
            revision_id="rev-dev-1",
            tenant_id="tenant-a",
            workspace_id="ws-1",
            content_fingerprint=content_fingerprint(content),
            content=content,
            kind="pipeline",
        ),
    )
    before = provider.revisions.get_revision(ctx, "rev-dev-1")
    promo = provider.revisions.promote(
        ctx,
        logical_id="pipe-1",
        from_revision_id="rev-dev-1",
        from_environment="development",
        to_environment="production",
    )
    assert promo.logical_id == "pipe-1"
    assert provider.revisions.get_revision(ctx, "rev-dev-1") == before

    provider.workspaces.set_lifecycle(ctx, "ws-1", LifecycleState.SUSPENDED)
    with pytest.raises(ControlPlaneError) as exc:
        provider.revisions.get_revision(ctx, "rev-dev-1")
    assert exc.value.status == 403


def test_memory_vs_sqlmodel_promote_suspend_conformance() -> None:
    engine = create_sqlite_engine("sqlite://")
    apply_migrations(engine)
    backends = {
        "memory": MemoryRegistryProvider(),
        "sqlmodel": SqlModelRegistryProvider(engine),
    }
    for label, provider in backends.items():
        ctx = _ctx()
        _seed(provider, ctx)
        content = {"backend": label}
        provider.revisions.put_revision(
            ctx,
            RegistryRevision(
                logical_id="logic-x",
                revision_id="rev-x1",
                tenant_id="tenant-a",
                workspace_id="ws-1",
                content_fingerprint=content_fingerprint(content),
                content=content,
            ),
        )
        before = provider.revisions.get_revision(ctx, "rev-x1")
        promo = provider.revisions.promote(
            ctx,
            logical_id="logic-x",
            from_revision_id="rev-x1",
            from_environment="dev",
            to_environment="prod",
        )
        assert promo.logical_id == "logic-x", label
        assert provider.revisions.get_revision(ctx, "rev-x1") == before, label
        provider.tenants.set_lifecycle(ctx, "tenant-a", LifecycleState.SUSPENDED)
        with pytest.raises(ControlPlaneError) as exc:
            provider.workspaces.list(ctx)
        assert exc.value.status == 403, label


def test_registry_definition_repository_round_trip() -> None:
    engine = create_sqlite_engine("sqlite://")
    apply_migrations(engine)
    provider = SqlModelRegistryProvider(engine)
    ctx = _ctx()
    _seed(provider, ctx)
    defs = RegistryDefinitionRepository(provider)
    doc = {"schema": "etlantic.pipeline/1", "name": "demo", "nodes": []}
    defs.put(ctx, "def-1", doc)
    assert defs.get(ctx, "def-1") == doc
    assert defs.list(ctx) == ["def-1"]
    defs.put(ctx, "def-1", {**doc, "name": "demo-v2"})
    assert defs.get(ctx, "def-1")["name"] == "demo-v2"
    assert len(provider.revisions.list_revisions(ctx, "def-1")) == 2


def test_sqlmodel_alias_and_immutability() -> None:
    engine = create_sqlite_engine("sqlite://")
    apply_migrations(engine)
    provider = SqlModelRegistryProvider(engine)
    ctx = _ctx()
    _seed(provider, ctx)
    content = {"x": 1}
    rev = RegistryRevision(
        logical_id="l1",
        revision_id="r1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
    )
    provider.revisions.put_revision(ctx, rev)
    provider.revisions.put_alias(
        ctx,
        AliasRecord(
            tenant_id="tenant-a",
            workspace_id="ws-1",
            alias="latest",
            logical_id="l1",
            revision_id="r1",
        ),
    )
    assert provider.revisions.resolve_alias(ctx, "latest").revision_id == "r1"
    with pytest.raises(ControlPlaneError) as exc:
        provider.revisions.put_revision(ctx, rev)
    assert exc.value.status == 409


def test_sqlmodel_rejects_tenant_takeover_and_alias_logical_mismatch() -> None:
    engine = create_sqlite_engine("sqlite://")
    apply_migrations(engine)
    provider = SqlModelRegistryProvider(engine)
    owner = _ctx(tenant="tenant-a", workspace="ws-1", domain="domain-a")
    attacker = _ctx(tenant="tenant-b", workspace="ws-1", domain="domain-b")
    _seed(provider, owner)

    with pytest.raises(ControlPlaneError) as tenant_exc:
        provider.tenants.put(
            attacker,
            TenantRecord(tenant_id="tenant-a", security_domain_id="domain-b"),
        )
    assert tenant_exc.value.status == 404

    content = {"v": 1}
    provider.revisions.put_revision(
        owner,
        RegistryRevision(
            logical_id="logic-a",
            revision_id="rev-a",
            tenant_id="tenant-a",
            workspace_id="ws-1",
            content_fingerprint=content_fingerprint(content),
            content=content,
            kind="pipeline",
        ),
    )
    with pytest.raises(ControlPlaneError) as alias_exc:
        provider.revisions.put_alias(
            owner,
            AliasRecord(
                tenant_id="tenant-a",
                workspace_id="ws-1",
                alias="bad",
                logical_id="logic-b",
                revision_id="rev-a",
            ),
        )
    assert alias_exc.value.status == 409
