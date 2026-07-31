"""CP2 registry directory, revision, alias, and promotion tests (0.40)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from etlantic.control_plane import (
    AliasRecord,
    ControlPlaneContext,
    ControlPlaneError,
    CorrelationKey,
    EnvironmentRef,
    LifecycleState,
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


def _ctx(
    *,
    tenant: str = "tenant-a",
    workspace: str = "ws-1",
    subject: str = "user-a",
    domain: str = "domain-a",
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(
            subject=subject, issuer="https://issuer.example", kind="human"
        ),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id=domain),
        correlation_key=CorrelationKey(value="corr-1"),
        request_id="req-1",
    )


def _seed_workspace(provider: MemoryRegistryProvider, ctx: ControlPlaneContext) -> None:
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


def test_two_tenant_isolation_directory_and_revisions() -> None:
    provider = MemoryRegistryProvider()
    ctx_a = _ctx(tenant="tenant-a", workspace="ws-1", domain="domain-a")
    ctx_b = _ctx(tenant="tenant-b", workspace="ws-1", domain="domain-b")
    _seed_workspace(provider, ctx_a)
    _seed_workspace(provider, ctx_b)

    content = {"kind": "pipeline", "name": "orders"}
    rev_a = RegistryRevision(
        logical_id="pipe-orders",
        revision_id="rev-a1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
        kind="pipeline",
    )
    provider.revisions.put_revision(ctx_a, rev_a)

    content_b = {"kind": "pipeline", "name": "secret-b"}
    rev_b = RegistryRevision(
        logical_id="pipe-orders",
        revision_id="rev-b1",
        tenant_id="tenant-b",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content_b),
        content=content_b,
        kind="pipeline",
    )
    provider.revisions.put_revision(ctx_b, rev_b)

    # Directory isolation: A cannot read B's tenant/workspace records.
    with pytest.raises(ControlPlaneError) as exc_tenant:
        provider.tenants.get(ctx_a, "tenant-b")
    assert exc_tenant.value.status == 404

    listed = provider.workspaces.list(ctx_a)
    assert [w.workspace_id for w in listed] == ["ws-1"]
    assert all(w.tenant_id == "tenant-a" for w in listed)

    # Revision isolation: same revision_id under B is invisible to A.
    got_a = provider.revisions.get_revision(ctx_a, "rev-a1")
    assert got_a.content["name"] == "orders"
    with pytest.raises(ControlPlaneError) as exc_rev:
        provider.revisions.get_revision(ctx_a, "rev-b1")
    assert exc_rev.value.status == 404

    # A cannot overwrite B by forging tenant fields on the revision.
    forged = RegistryRevision(
        logical_id="pipe-orders",
        revision_id="rev-b2",
        tenant_id="tenant-b",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint({"x": 1}),
        content={"x": 1},
    )
    with pytest.raises(ControlPlaneError):
        provider.revisions.put_revision(ctx_a, forged)


def test_suspended_workspace_rejects_put_get() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed_workspace(provider, ctx)

    content = {"v": 1}
    rev = RegistryRevision(
        logical_id="logic-1",
        revision_id="rev-1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
    )
    provider.revisions.put_revision(ctx, rev)

    provider.workspaces.set_lifecycle(ctx, "ws-1", LifecycleState.SUSPENDED)

    with pytest.raises(ControlPlaneError) as exc_get_ws:
        provider.workspaces.get(ctx, "ws-1")
    assert exc_get_ws.value.status == 403

    with pytest.raises(ControlPlaneError) as exc_put_ws:
        provider.workspaces.put(
            ctx,
            WorkspaceRecord(tenant_id="tenant-a", workspace_id="ws-1"),
        )
    assert exc_put_ws.value.status == 403

    with pytest.raises(ControlPlaneError) as exc_get_rev:
        provider.revisions.get_revision(ctx, "rev-1")
    assert exc_get_rev.value.status == 403

    with pytest.raises(ControlPlaneError) as exc_put_rev:
        provider.revisions.put_revision(
            ctx,
            RegistryRevision(
                logical_id="logic-1",
                revision_id="rev-2",
                tenant_id="tenant-a",
                workspace_id="ws-1",
                content_fingerprint=content_fingerprint({"v": 2}),
                content={"v": 2},
            ),
        )
    assert exc_put_rev.value.status == 403


def test_promotion_preserves_logical_id_and_immutability() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed_workspace(provider, ctx)

    content = {"stage": "dev", "hash": "abc"}
    source = RegistryRevision(
        logical_id="pipe-1",
        revision_id="rev-dev-1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
        kind="pipeline",
        signature_placeholder="sig-placeholder",
    )
    provider.revisions.put_revision(ctx, source)
    before = provider.revisions.get_revision(ctx, "rev-dev-1")

    promotion = provider.revisions.promote(
        ctx,
        logical_id="pipe-1",
        from_revision_id="rev-dev-1",
        from_environment="development",
        to_environment="production",
    )
    assert promotion.logical_id == "pipe-1"
    assert promotion.from_revision_id == "rev-dev-1"
    assert promotion.to_revision_id != "rev-dev-1"
    assert promotion.to_environment == "production"

    after = provider.revisions.get_revision(ctx, "rev-dev-1")
    assert after == before
    assert after.content_fingerprint == before.content_fingerprint

    promoted = provider.revisions.get_revision(ctx, promotion.to_revision_id)
    assert promoted.logical_id == "pipe-1"
    assert promoted.content == content

    # Overwrite of an existing revision_id fails closed (immutability).
    with pytest.raises(ControlPlaneError) as exc:
        provider.revisions.put_revision(ctx, source)
    assert exc.value.status == 409


def test_tamper_detection_on_content_fingerprint() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed_workspace(provider, ctx)

    content = {"safe": True}
    rev = RegistryRevision(
        logical_id="logic-t",
        revision_id="rev-t1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
    )
    provider.revisions.put_revision(ctx, rev)

    # Simulate storage tampering of content without updating fingerprint.
    key = (*ctx.scope_key, "rev-t1")
    stored = provider.revisions._revisions[key]
    provider.revisions._revisions[key] = replace(
        stored, content={"safe": False, "injected": "row"}
    )

    with pytest.raises(ControlPlaneError) as exc:
        provider.revisions.get_revision(ctx, "rev-t1")
    assert exc.value.status == 409
    assert "fingerprint" in exc.value.detail.lower()


def test_alias_resolution() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed_workspace(provider, ctx)

    content = {"alias_target": True}
    rev = RegistryRevision(
        logical_id="logic-a",
        revision_id="rev-alias-1",
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
            alias="prod",
            logical_id="logic-a",
            revision_id="rev-alias-1",
        ),
    )

    resolved = provider.revisions.resolve_alias(ctx, "prod")
    assert resolved.revision_id == "rev-alias-1"
    assert resolved.logical_id == "logic-a"
    assert resolved.content == content

    ctx_other = _ctx(tenant="tenant-b", workspace="ws-1", domain="domain-b")
    _seed_workspace(provider, ctx_other)
    with pytest.raises(ControlPlaneError) as exc:
        provider.revisions.resolve_alias(ctx_other, "prod")
    assert exc.value.status == 404


def test_existing_tenant_cannot_be_taken_over_by_incoming_domain() -> None:
    provider = MemoryRegistryProvider()
    owner = _ctx(tenant="tenant-a", domain="domain-a")
    attacker = _ctx(tenant="tenant-b", domain="domain-b")
    _seed_workspace(provider, owner)

    with pytest.raises(ControlPlaneError) as exc:
        provider.tenants.put(
            attacker,
            TenantRecord(
                tenant_id="tenant-a",
                security_domain_id="domain-b",
                display_name="taken-over",
            ),
        )
    assert exc.value.status == 404
    assert provider.tenants.get(owner, "tenant-a").display_name == "tenant-a"


def test_revision_storage_is_deeply_immutable_and_redacts_metadata() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed_workspace(provider, ctx)
    content = {"nested": {"items": [1]}}
    revision = RegistryRevision(
        logical_id="logic-deep",
        revision_id="rev-deep",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
        kind="pipeline",
        provenance_placeholder={"api_token": "super-secret-token"},
    )
    provider.revisions.put_revision(ctx, revision)
    content["nested"]["items"].append(2)

    stored = provider.revisions.get_revision(ctx, "rev-deep")
    assert stored.content == {"nested": {"items": [1]}}
    assert stored.provenance_placeholder == {"api_token": "***"}

    provider.tenants.put(
        ctx,
        TenantRecord(
            tenant_id="tenant-a",
            security_domain_id="domain-a",
            metadata={"password": "super-secret-token"},
        ),
    )
    assert provider.tenants.get(ctx, "tenant-a").metadata == {"password": "***"}


def test_alias_and_revision_kind_must_match_logical_identity() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed_workspace(provider, ctx)
    content = {"v": 1}
    provider.revisions.put_revision(
        ctx,
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
            ctx,
            AliasRecord(
                tenant_id="tenant-a",
                workspace_id="ws-1",
                alias="wrong",
                logical_id="logic-b",
                revision_id="rev-a",
            ),
        )
    assert alias_exc.value.status == 409

    with pytest.raises(ControlPlaneError) as kind_exc:
        provider.revisions.put_revision(
            ctx,
            RegistryRevision(
                logical_id="logic-a",
                revision_id="rev-contract",
                tenant_id="tenant-a",
                workspace_id="ws-1",
                content_fingerprint=content_fingerprint(content),
                content=content,
                kind="contract",
            ),
        )
    assert kind_exc.value.status == 409
