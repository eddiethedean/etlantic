"""SQLModel parity regressions from the post-release 0.40 deep dive."""

# ruff: noqa: I001

from __future__ import annotations

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRecord,
    EnvironmentRef,
    LifecycleState,
    Principal,
    RegistryRevision,
    SecurityDomain,
    TenantRecord,
    TenantRef,
    WorkspaceRecord,
    WorkspaceRef,
    content_fingerprint,
)
from etlantic_sqlmodel.control_plane import (
    SQLModelSubmissionStore,
    SqlModelEventStore,
    SqlModelRegistryProvider,
    create_control_plane_tables,
    create_registry_tables,
    create_sqlite_engine,
    dump_registry_sqlite,
    load_registry_sqlite,
)

pytestmark = pytest.mark.sqlmodel


def _ctx(workspace: str = "ws-a") -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="domain-a"),
    )


def _provider(tmp_path, name: str = "registry.db") -> SqlModelRegistryProvider:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / name}")
    create_registry_tables(engine)
    return SqlModelRegistryProvider(engine)


def _seed(provider: SqlModelRegistryProvider, *contexts: ControlPlaneContext) -> None:
    provider.tenants.put(
        contexts[0],
        TenantRecord(tenant_id="tenant-a", security_domain_id="domain-a"),
    )
    for ctx in contexts:
        provider.workspaces.put(
            ctx,
            WorkspaceRecord(
                tenant_id="tenant-a", workspace_id=ctx.workspace.workspace_id
            ),
        )


def test_sqlmodel_environment_scope_and_lifecycle_match_memory(tmp_path) -> None:
    provider = _provider(tmp_path)
    ctx_a, ctx_b = _ctx("ws-a"), _ctx("ws-b")
    _seed(provider, ctx_a, ctx_b)
    provider.put_environment(
        ctx_a,
        EnvironmentRecord(
            tenant_id="tenant-a",
            workspace_id="ws-a",
            environment_id="prod",
            name="production",
        ),
    )
    with pytest.raises(ControlPlaneError) as cross_scope:
        provider.get_environment(ctx_b, "prod")
    assert cross_scope.value.status == 404

    provider.put_environment(
        ctx_a,
        EnvironmentRecord(
            tenant_id="tenant-a",
            workspace_id="ws-a",
            environment_id="prod",
            name="production",
            lifecycle=LifecycleState.SUSPENDED,
        ),
    )
    with pytest.raises(ControlPlaneError) as suspended:
        provider.get_environment(ctx_a, "prod")
    assert suspended.value.status == 403


def test_sqlmodel_revision_and_promotion_payloads_are_secret_free(tmp_path) -> None:
    provider = _provider(tmp_path)
    ctx = _ctx()
    _seed(provider, ctx)
    content = {"name": "orders", "password": "super-secret-token"}
    provider.revisions.put_revision(
        ctx,
        RegistryRevision(
            logical_id="pipe-orders",
            revision_id="rev-1",
            tenant_id="tenant-a",
            workspace_id="ws-a",
            content_fingerprint=content_fingerprint(content),
            content=content,
            kind="pipeline",
            signature_placeholder="token=super-secret-token",
            provenance_placeholder={"password": "super-secret-token"},
        ),
    )
    stored = provider.revisions.get_revision(ctx, "rev-1")
    assert "super-secret-token" not in str(stored.to_dict())
    assert stored.content_fingerprint == content_fingerprint(stored.content)

    promotion = provider.revisions.promote(
        ctx,
        logical_id="pipe-orders",
        from_revision_id="rev-1",
        from_environment="dev",
        to_environment="prod",
        metadata={"token": "super-secret-token"},
    )
    assert "super-secret-token" not in str(promotion.to_dict())


def test_sqlmodel_submission_and_event_payloads_are_redacted(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'cp.db'}")
    create_control_plane_tables(engine)
    ctx = _ctx()

    submissions = SQLModelSubmissionStore(engine)
    first = submissions.accept(
        ctx,
        idempotency_key="idem-1",
        payload={"definition_id": "orders", "token": "first"},
    )
    replay = submissions.accept(
        ctx,
        idempotency_key="idem-1",
        payload={"definition_id": "orders", "token": "second"},
    )
    assert first.created is True
    assert replay.created is False

    events = SqlModelEventStore(engine)
    event = events.append(
        ctx,
        kind="run.accepted",
        payload={"password": "super-secret-token"},
    )
    assert event.payload == {"password": "***"}
    assert events.list_after_cursor(ctx, None)[0].payload == {"password": "***"}


def test_backup_round_trip_handles_suspended_scopes_and_redacts(tmp_path) -> None:
    source = _provider(tmp_path, "source.db")
    ctx = _ctx()
    _seed(source, ctx)
    content = {"name": "orders", "password": "super-secret-token"}
    source.revisions.put_revision(
        ctx,
        RegistryRevision(
            logical_id="pipe-orders",
            revision_id="rev-1",
            tenant_id="tenant-a",
            workspace_id="ws-a",
            content_fingerprint=content_fingerprint(content),
            content=content,
            kind="pipeline",
        ),
    )
    source.workspaces.set_lifecycle(ctx, "ws-a", LifecycleState.SUSPENDED)
    source.tenants.set_lifecycle(ctx, "tenant-a", LifecycleState.SUSPENDED)
    transcript = dump_registry_sqlite(source.engine)
    assert "super-secret-token" not in str(transcript.to_dict())

    destination_engine = create_sqlite_engine(
        f"sqlite:///{tmp_path / 'destination.db'}"
    )
    restored = load_registry_sqlite(destination_engine, transcript)
    assert restored.tenants.peek("tenant-a").lifecycle == LifecycleState.SUSPENDED
    assert (
        restored.workspaces.peek("tenant-a", "ws-a").lifecycle
        == LifecycleState.SUSPENDED
    )
