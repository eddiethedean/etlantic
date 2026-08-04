#!/usr/bin/env python3
"""CI/local gate: two-tenant / two-workspace registry isolation + profile matrix.

Extends conformance with an isolation matrix over memory (and SQLModel when
installed). Fake evidence lives at
docs/11_DEVELOPMENT/isolation_profile_matrix_0_40.json.

CP2 alone ≠ GA; Supported profiles graduated in 0.43.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "11_DEVELOPMENT" / "isolation_profile_matrix_0_40.json"


def _ctx(tenant: str, workspace: str, domain: str):
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


def _run_matrix(label: str, provider: Any) -> list[dict[str, Any]]:
    from etlantic.control_plane import (
        ControlPlaneError,
        RegistryRevision,
        content_fingerprint,
    )

    results: list[dict[str, Any]] = []
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

    isolation_ok = True
    for tenant, workspace, domain in matrix:
        ctx = _ctx(tenant, workspace, domain)
        own = provider.revisions.get_revision(ctx, f"rev-{tenant}-{workspace}")
        if own.tenant_id != tenant or own.workspace_id != workspace:
            isolation_ok = False
        for other_t, other_w, _ in matrix:
            if (other_t, other_w) == (tenant, workspace):
                continue
            try:
                provider.revisions.get_revision(ctx, f"rev-{other_t}-{other_w}")
                isolation_ok = False
            except ControlPlaneError:
                pass
            except Exception:
                pass
    results.append({"case": f"{label}:two_by_two_isolation", "ok": isolation_ok})
    return results


def _check_evidence() -> dict[str, Any]:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    profiles = {row["profile"] for row in payload.get("profiles", [])}
    expected = {"isolated-deployment", "dedicated-schema", "shared-service"}
    shared = next(
        (
            r
            for r in payload.get("profiles", [])
            if r.get("profile") == "shared-service"
        ),
        None,
    )
    ok = (
        payload.get("schema") == "etlantic.isolation_profile_matrix/1"
        and profiles == expected
        and payload.get("cp2_production_multi_tenant_claim") is False
        and shared is not None
        and shared.get("where_only_insufficient") is True
        and shared.get("second_control_required") is True
    )
    return {"case": "evidence:isolation_profile_matrix", "ok": ok}


def _shared_service_stub() -> dict[str, Any]:
    """WHERE-only is insufficient without a second control."""

    rows = [
        {"tenant_id": "tenant-a", "secret": "a"},
        {"tenant_id": "tenant-b", "secret": "b"},
    ]

    def where_only(tenant_id: str) -> list[dict[str, str]]:
        return [row for row in rows if row["tenant_id"] == tenant_id]

    def with_session(claimed: str, session: str) -> list[dict[str, str]]:
        if claimed != session:
            return []
        return where_only(claimed)

    leaked = where_only("tenant-b")
    blocked = with_session("tenant-b", "tenant-a")
    allowed = with_session("tenant-a", "tenant-a")
    ok = bool(leaked) and blocked == [] and bool(allowed)
    return {"case": "shared_service:where_insufficient", "ok": ok}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Run memory (+ SQLModel when installed) isolation matrix",
    )
    args = parser.parse_args(argv)
    if not args.fake:
        parser.error("specify --fake")

    from etlantic.control_plane import MemoryRegistryProvider

    all_results: list[dict[str, Any]] = []
    all_results.append(_check_evidence())
    all_results.append(_shared_service_stub())
    all_results.extend(_run_matrix("memory", MemoryRegistryProvider()))
    try:
        from etlantic_sqlmodel.control_plane import (
            SqlModelRegistryProvider,
            create_sqlite_engine,
        )
        from etlantic_sqlmodel.migrations import apply_migrations

        engine = create_sqlite_engine("sqlite://")
        apply_migrations(engine)
        all_results.extend(_run_matrix("sqlmodel", SqlModelRegistryProvider(engine)))
    except ImportError:
        print("  skip: etlantic-sqlmodel not importable")

    ok = sum(1 for r in all_results if r.get("ok"))
    failed = [r for r in all_results if not r.get("ok")]
    print(f"Registry isolation: {ok}/{len(all_results)} cases")
    for row in all_results:
        print(f"  - {row.get('case')}: ok={row.get('ok')}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
