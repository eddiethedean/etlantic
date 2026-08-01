"""CP2 workspace resource store and safe-root helpers (040-W)."""

from __future__ import annotations

from pathlib import Path

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    CorrelationKey,
    EnvironmentRef,
    MemoryWorkspaceResourceStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    WorkspaceResourceRecord,
    is_absolute_root_ref,
    reject_absolute_root_ref,
    reject_symlink_or_traversal,
    resolve_safe_root,
)


def _ctx(
    *,
    tenant: str = "tenant-a",
    workspace: str = "ws-1",
    domain: str = "domain-a",
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(
            subject="user-a", issuer="https://issuer.example", kind="human"
        ),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id=domain),
        correlation_key=CorrelationKey(value="corr-1"),
        request_id="req-1",
    )


def test_two_by_two_tenant_workspace_matrix() -> None:
    store = MemoryWorkspaceResourceStore()
    scopes = [
        ("tenant-a", "ws-1"),
        ("tenant-a", "ws-2"),
        ("tenant-b", "ws-1"),
        ("tenant-b", "ws-2"),
    ]
    for tenant, workspace in scopes:
        ctx = _ctx(tenant=tenant, workspace=workspace, domain=f"d-{tenant}")
        store.put(
            ctx,
            WorkspaceResourceRecord(
                tenant_id=tenant,
                workspace_id=workspace,
                safe_root_refs=(f"landing/{tenant}/{workspace}",),
                artifact_namespace=f"artifacts/{tenant}/{workspace}",
                checkpoint_store_ref=f"checkpoints/{tenant}/{workspace}",
                preview_namespace=f"preview/{tenant}/{workspace}",
            ),
        )

    assert store.list_keys() == scopes

    for tenant, workspace in scopes:
        ctx = _ctx(tenant=tenant, workspace=workspace, domain=f"d-{tenant}")
        got = store.get(ctx)
        assert got.tenant_id == tenant
        assert got.workspace_id == workspace
        assert got.safe_root_refs == (f"landing/{tenant}/{workspace}",)
        assert got.artifact_namespace == f"artifacts/{tenant}/{workspace}"


def test_cross_scope_get_is_404() -> None:
    store = MemoryWorkspaceResourceStore()
    ctx_a = _ctx(tenant="tenant-a", workspace="ws-1")
    ctx_b = _ctx(tenant="tenant-b", workspace="ws-1", domain="domain-b")
    store.put(
        ctx_a,
        WorkspaceResourceRecord(
            tenant_id="tenant-a",
            workspace_id="ws-1",
            safe_root_refs=("landing/a",),
        ),
    )

    with pytest.raises(ControlPlaneError) as exc:
        store.get(ctx_b)
    assert exc.value.status == 404

    # Same tenant, different workspace.
    ctx_a2 = _ctx(tenant="tenant-a", workspace="ws-2")
    with pytest.raises(ControlPlaneError) as exc2:
        store.get(ctx_a2)
    assert exc2.value.status == 404


def test_reject_absolute_path_roots_in_stored_records() -> None:
    store = MemoryWorkspaceResourceStore()
    ctx = _ctx()

    assert is_absolute_root_ref("/var/data")
    assert is_absolute_root_ref("C:\\data")
    assert not is_absolute_root_ref("landing/zone")

    with pytest.raises(ControlPlaneError) as exc:
        reject_absolute_root_ref("/etc/passwd")
    assert exc.value.status == 409

    with pytest.raises(ControlPlaneError) as exc_put:
        store.put(
            ctx,
            WorkspaceResourceRecord(
                tenant_id="tenant-a",
                workspace_id="ws-1",
                safe_root_refs=("/absolute/secret",),
            ),
        )
    assert exc_put.value.status == 409

    with pytest.raises(ControlPlaneError):
        store.put(
            ctx,
            WorkspaceResourceRecord(
                tenant_id="tenant-a",
                workspace_id="ws-1",
                safe_root_refs=("ok/ref",),
                checkpoint_store_ref="/tmp/checkpoints",
            ),
        )

    with pytest.raises(ControlPlaneError):
        store.put(
            ctx,
            WorkspaceResourceRecord(
                tenant_id="tenant-a",
                workspace_id="ws-1",
                safe_root_refs=("../escape",),
            ),
        )


def test_symlink_and_traversal_reject_helpers(tmp_path: Path) -> None:
    base = tmp_path / "workspace"
    base.mkdir()
    allowed = base / "landing"
    allowed.mkdir()
    (allowed / "file.txt").write_text("ok", encoding="utf-8")

    resolved = resolve_safe_root("landing", base=base)
    assert resolved == allowed.resolve()
    assert (
        reject_symlink_or_traversal(Path("landing/file.txt"), approved_root=base)
        == (allowed / "file.txt").resolve()
    )

    with pytest.raises(ControlPlaneError) as exc_trav:
        resolve_safe_root("../outside", base=base)
    assert exc_trav.value.status == 409

    # Symlink pointing outside approved root.
    outside = tmp_path / "outside"
    outside.mkdir()
    link = base / "escape-link"
    link.symlink_to(outside)

    with pytest.raises(ControlPlaneError) as exc_link:
        reject_symlink_or_traversal(link, approved_root=base)
    assert exc_link.value.status == 409

    with pytest.raises(ControlPlaneError):
        resolve_safe_root("escape-link", base=base)

    inside = base / "inside"
    inside.mkdir()
    nested_link = base / "nested-link"
    nested_link.symlink_to(inside, target_is_directory=True)
    with pytest.raises(ControlPlaneError):
        resolve_safe_root("nested-link/child", base=base)

    with pytest.raises(ControlPlaneError):
        reject_symlink_or_traversal(
            base / "landing" / ".." / "inside", approved_root=base
        )
