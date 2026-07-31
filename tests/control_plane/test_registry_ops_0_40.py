"""CP2 ops: search/pagination, retention, backup/restore (040-O)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from etlantic.control_plane import (
    AliasRecord,
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRecord,
    EnvironmentRef,
    MemoryHistoryStore,
    MemoryRegistryProvider,
    MemoryRetentionHook,
    Principal,
    RegistryRevision,
    SchemaObservationRecord,
    SecurityDomain,
    SecurityDomainRecord,
    TenantRecord,
    TenantRef,
    WorkspaceRecord,
    WorkspaceRef,
    content_fingerprint,
    search_revisions,
)


def _ctx(
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


def test_search_revisions_metadata_only_and_pagination() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed(provider, ctx)
    for i in range(5):
        content = {"n": i}
        provider.revisions.put_revision(
            ctx,
            RegistryRevision(
                logical_id="pipe-1",
                revision_id=f"rev-{i}",
                tenant_id="tenant-a",
                workspace_id="ws-1",
                content_fingerprint=content_fingerprint(content),
                content=content,
                kind="pipeline",
            ),
        )
    page1 = search_revisions(provider, ctx, limit=2)
    assert page1.total == 5
    assert len(page1.items) == 2
    assert page1.next_cursor is not None
    # Metadata only — hits must not expose content bodies.
    assert not hasattr(page1.items[0], "content")
    assert "content" not in page1.items[0].to_dict()

    page2 = search_revisions(provider, ctx, limit=2, cursor=page1.next_cursor)
    assert len(page2.items) == 2
    assert {h.revision_id for h in page1.items}.isdisjoint(
        {h.revision_id for h in page2.items}
    )


def test_search_revisions_scoped_isolation() -> None:
    provider = MemoryRegistryProvider()
    ctx_a = _ctx(tenant="tenant-a", workspace="ws-1", domain="domain-a")
    ctx_b = _ctx(tenant="tenant-b", workspace="ws-1", domain="domain-b")
    _seed(provider, ctx_a)
    _seed(provider, ctx_b)
    content = {"secret": "b"}
    provider.revisions.put_revision(
        ctx_b,
        RegistryRevision(
            logical_id="pipe-b",
            revision_id="rev-b",
            tenant_id="tenant-b",
            workspace_id="ws-1",
            content_fingerprint=content_fingerprint(content),
            content=content,
            kind="pipeline",
        ),
    )
    page = search_revisions(provider, ctx_a)
    assert page.total == 0
    assert page.items == ()


def test_search_revisions_rejects_malformed_cursors() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed(provider, ctx)

    for cursor in ("not-base64", "a", "\N{SNOWMAN}"):
        with pytest.raises(ControlPlaneError) as exc:
            search_revisions(provider, ctx, cursor=cursor)
        assert exc.value.status == 400


def test_retention_purges_expired_observations_only() -> None:
    history = MemoryHistoryStore()
    hook = MemoryRetentionHook(history)
    ctx = _ctx()
    old = SchemaObservationRecord(
        observation_id="obs-old",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        subject_id="subj",
        schema_fingerprint="fp-old",
        observed_at="2020-01-01T00:00:00Z",
    )
    new = SchemaObservationRecord(
        observation_id="obs-new",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        subject_id="subj",
        schema_fingerprint="fp-new",
        observed_at="2030-01-01T00:00:00Z",
    )
    history.append_schema_observation(ctx, old)
    history.append_schema_observation(ctx, new)
    cutoff = datetime(2025, 1, 1, tzinfo=UTC)
    deleted = hook.purge_expired_observations(ctx, older_than=cutoff)
    assert deleted == 1
    remaining = history.list_schema_observations(ctx)
    assert len(remaining) == 1
    assert remaining[0].observation_id == "obs-new"


def test_retention_does_not_cross_tenant() -> None:
    history = MemoryHistoryStore()
    hook = MemoryRetentionHook(history)
    ctx_a = _ctx(tenant="tenant-a", workspace="ws-1")
    ctx_b = _ctx(tenant="tenant-b", workspace="ws-1", domain="domain-b")
    history.append_schema_observation(
        ctx_b,
        SchemaObservationRecord(
            observation_id="obs-b",
            tenant_id="tenant-b",
            workspace_id="ws-1",
            subject_id="subj",
            schema_fingerprint="fp-b",
            observed_at="2020-01-01T00:00:00Z",
        ),
    )
    deleted = hook.purge_expired_observations(
        ctx_a,
        older_than=datetime.now(UTC) + timedelta(days=1),
    )
    assert deleted == 0
    assert len(history.list_schema_observations(ctx_b)) == 1


@pytest.mark.sqlmodel
def test_backup_restore_round_trip_preserves_scope() -> None:
    from etlantic_sqlmodel.control_plane import (
        SqlModelRegistryProvider,
        backup_round_trip,
        create_sqlite_engine,
        dump_registry_sqlite,
    )
    from etlantic_sqlmodel.migrations import apply_migrations

    source = create_sqlite_engine("sqlite://")
    apply_migrations(source)
    provider = SqlModelRegistryProvider(source)
    ctx_a = _ctx(tenant="tenant-a", workspace="ws-1", domain="domain-a")
    ctx_b = _ctx(tenant="tenant-b", workspace="ws-2", domain="domain-b")
    for ctx in (ctx_a, ctx_b):
        _seed(provider, ctx)
        provider.put_security_domain(
            ctx,
            SecurityDomainRecord(domain_id=ctx.security_domain.domain_id),
        )
        provider.put_environment(
            ctx,
            EnvironmentRecord(
                tenant_id=ctx.tenant.tenant_id,
                environment_id="development",
                name="development",
                workspace_id=ctx.workspace.workspace_id,
            ),
        )
        content = {"tenant": ctx.tenant.tenant_id}
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
        provider.revisions.put_alias(
            ctx,
            AliasRecord(
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                alias="current",
                logical_id="pipe-1",
                revision_id=f"rev-{ctx.tenant.tenant_id}",
            ),
        )
        provider.revisions.promote(
            ctx,
            logical_id="pipe-1",
            from_revision_id=f"rev-{ctx.tenant.tenant_id}",
            from_environment="development",
            to_environment="production",
        )

    dest = create_sqlite_engine("sqlite://")
    transcript = backup_round_trip(source, dest)
    assert len(transcript.tenants) == 2
    assert len(transcript.workspaces) == 2
    assert len(transcript.revisions) == 4
    assert len(transcript.logicals) == 2
    assert len(transcript.aliases) == 2
    assert len(transcript.promotions) == 2
    assert len(transcript.environments) == 2
    assert len(transcript.security_domains) == 2

    restored = SqlModelRegistryProvider(dest)
    for ctx in (ctx_a, ctx_b):
        rev = restored.revisions.get_revision(ctx, f"rev-{ctx.tenant.tenant_id}")
        assert rev.tenant_id == ctx.tenant.tenant_id
        assert rev.workspace_id == ctx.workspace.workspace_id
        assert restored.revisions.resolve_alias(ctx, "current").revision_id == (
            f"rev-{ctx.tenant.tenant_id}"
        )
        assert restored.get_environment(ctx, "development").workspace_id == (
            ctx.workspace.workspace_id
        )
        assert (
            restored.get_security_domain(ctx, ctx.security_domain.domain_id).domain_id
            == ctx.security_domain.domain_id
        )

    # Cross-scope still fail-closed after restore.
    with pytest.raises(ControlPlaneError):
        restored.revisions.get_revision(ctx_a, "rev-tenant-b")

    # Dump is stable / re-readable.
    again = dump_registry_sqlite(dest)
    assert {t["tenant_id"] for t in again.tenants} == {"tenant-a", "tenant-b"}
