#!/usr/bin/env python3
"""CI/local gate: registry provider promote/suspend conformance (memory + optional SQLModel).

Prefer this stub over extending the public CLI surface until ``etlantic registry``
is promoted. See packages/etlantic-sqlmodel/README.md and
packages/etlantic-fastapi/README.md for registry admin HTTP (``/v1/registry``).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


def _ctx(tenant: str = "tenant-a", workspace: str = "ws-1", domain: str = "domain-a"):
    from etlantic.control_plane import (
        ControlPlaneContext,
        EnvironmentRef,
        Principal,
        SecurityDomain,
        TenantRef,
        WorkspaceRef,
    )

    return ControlPlaneContext(
        principal=Principal(subject="alice", kind="human"),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id=domain),
    )


def _seed(provider: Any, ctx: Any) -> None:
    from etlantic.control_plane import TenantRecord, WorkspaceRecord

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


def _run_suite(label: str, provider: Any) -> list[dict[str, Any]]:
    from etlantic.control_plane import (
        ControlPlaneError,
        LifecycleState,
        RegistryRevision,
        content_fingerprint,
    )

    results: list[dict[str, Any]] = []
    ctx = _ctx()
    _seed(provider, ctx)

    content = {"stage": "dev", "v": 1}
    rev = RegistryRevision(
        logical_id="pipe-1",
        revision_id="rev-dev-1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
        kind="pipeline",
    )
    provider.revisions.put_revision(ctx, rev)
    before = provider.revisions.get_revision(ctx, "rev-dev-1")
    promotion = provider.revisions.promote(
        ctx,
        logical_id="pipe-1",
        from_revision_id="rev-dev-1",
        from_environment="development",
        to_environment="production",
    )
    after = provider.revisions.get_revision(ctx, "rev-dev-1")
    promote_ok = (
        promotion.logical_id == "pipe-1"
        and promotion.to_revision_id != "rev-dev-1"
        and after == before
    )
    results.append({"case": f"{label}:promote_immutable", "ok": promote_ok})

    tenants = provider.tenants.list(ctx)
    results.append(
        {
            "case": f"{label}:list_tenants",
            "ok": any(t.tenant_id == "tenant-a" for t in tenants),
        }
    )

    provider.workspaces.set_lifecycle(ctx, "ws-1", LifecycleState.SUSPENDED)
    suspend_ok = False
    try:
        provider.revisions.get_revision(ctx, "rev-dev-1")
    except ControlPlaneError as exc:
        suspend_ok = exc.status == 403
    results.append({"case": f"{label}:suspend_fail_closed", "ok": suspend_ok})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Run memory (+ SQLModel when installed) conformance",
    )
    args = parser.parse_args(argv)
    if not args.fake:
        parser.error("specify --fake")

    from etlantic.control_plane import MemoryRegistryProvider

    exit_code = 0
    all_results = _run_suite("memory", MemoryRegistryProvider())
    try:
        from etlantic_sqlmodel.control_plane import (
            SqlModelRegistryProvider,
            create_sqlite_engine,
        )
        from etlantic_sqlmodel.migrations import apply_migrations

        engine = create_sqlite_engine("sqlite://")
        apply_migrations(engine)
        all_results.extend(_run_suite("sqlmodel", SqlModelRegistryProvider(engine)))
    except ImportError:
        print("  skip: etlantic-sqlmodel not importable")

    ok = sum(1 for r in all_results if r.get("ok"))
    failed = [r for r in all_results if not r.get("ok")]
    print(f"Registry conformance: {ok}/{len(all_results)} cases")
    for row in all_results:
        print(f"  - {row.get('case')}: ok={row.get('ok')}")
    if failed:
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
