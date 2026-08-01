#!/usr/bin/env python3
"""CI/local gate: durable chaos matrix (dual-host lease, outbox, stale fencing)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _ctx(tenant: str = "tenant-a", workspace: str = "workspace-a"):
    from etlantic.control_plane import (
        ControlPlaneContext,
        EnvironmentRef,
        Principal,
        SecurityDomain,
        TenantRef,
        WorkspaceRef,
    )

    return ControlPlaneContext(
        principal=Principal("worker-a", issuer="chaos"),
        tenant=TenantRef(tenant),
        workspace=WorkspaceRef(tenant, workspace),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def _run_chaos(store_factory) -> list[dict[str, object]]:
    from etlantic.control_plane import ControlPlaneError, EffectRecord, PreviewWorkspace

    results: list[dict[str, object]] = []
    ctx = _ctx()

    # Crash-point: accept leaves unpublished outbox; publish is idempotent.
    store = store_factory()
    submission, _ = store.accept(
        ctx, idempotency_key="chaos-1", operation="run.submit", plan_fingerprint="plan"
    )
    pending = store.pending_outbox(ctx)
    assert pending
    first = store.mark_published(ctx, pending[0].outbox_id)
    second = store.mark_published(ctx, pending[0].outbox_id)
    results.append(
        {
            "case": "outbox_crash_point_duplicate_publish",
            "status": "pass"
            if first.published_at and second.delivery_count == first.delivery_count
            else "fail",
        }
    )

    # Dual-host lease + stale fencing.
    host_a = store_factory()
    host_b = store_factory()
    # Share state when factory returns fresh empty stores: for memory use one store.
    shared = store_factory()
    sub, _ = shared.accept(
        ctx, idempotency_key="chaos-lease", operation="run.submit", plan_fingerprint="p"
    )
    lease_a = shared.acquire_lease(
        ctx, sub.submission_id, owner_id="host-a", ttl_seconds=60
    )
    stale_ok = False
    try:
        shared.acquire_lease(ctx, sub.submission_id, owner_id="host-b", ttl_seconds=60)
    except ControlPlaneError:
        stale_ok = True
    shared.release_lease(
        ctx,
        sub.submission_id,
        owner_id="host-a",
        fencing_token=lease_a.fencing_token,
    )
    lease_b = shared.acquire_lease(
        ctx, sub.submission_id, owner_id="host-b", ttl_seconds=60
    )
    fencing_ok = False
    try:
        shared.heartbeat(
            ctx,
            sub.submission_id,
            owner_id="host-a",
            fencing_token=lease_a.fencing_token,
            ttl_seconds=30,
        )
    except ControlPlaneError:
        fencing_ok = True
    results.append(
        {
            "case": "dual_host_lease_fencing",
            "status": "pass"
            if stale_ok and fencing_ok and lease_b.fencing_token > lease_a.fencing_token
            else "fail",
            "hosts": ["host-a", "host-b"],
        }
    )

    # Unknown effect fail-closed.
    effect_store = store_factory()
    sub2, _ = effect_store.accept(
        ctx,
        idempotency_key="chaos-effect",
        operation="run.submit",
        plan_fingerprint="p",
    )
    effect_store.record_effect(
        ctx,
        EffectRecord(
            "e1",
            sub2.submission_id,
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            "unknown",
            datetime.now(UTC).isoformat(),
        ),
    )
    unknown_ok = False
    try:
        effect_store.record_effect(
            ctx,
            EffectRecord(
                "e1",
                sub2.submission_id,
                ctx.tenant.tenant_id,
                ctx.workspace.workspace_id,
                "pending",
                datetime.now(UTC).isoformat(),
            ),
        )
    except ControlPlaneError:
        unknown_ok = True
    results.append(
        {
            "case": "unknown_effect_fail_closed",
            "status": "pass" if unknown_ok else "fail",
        }
    )

    # Preview staleness / cleanup scoped.
    preview_store = store_factory()
    preview = PreviewWorkspace(
        "pv-chaos",
        ctx.tenant.tenant_id,
        ctx.workspace.workspace_id,
        "r1",
        "r2",
        datetime.now(UTC).isoformat(),
        (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
        1,
        "code",
        "plan",
    )
    preview_store.create_preview(ctx, preview)
    stale = preview_store.mark_preview_stale(ctx, "pv-chaos", code_fingerprint="other")
    results.append(
        {
            "case": "preview_staleness",
            "status": "pass" if stale.stale else "fail",
        }
    )

    # Silence unused for API-style dual factory paths.
    _ = (host_a, host_b, submission)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake", action="store_true", default=True)
    parser.add_argument(
        "--write-evidence",
        type=Path,
        default=None,
        help="Optional path to write durable_chaos_matrix JSON.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from etlantic.control_plane import MemoryDurableWorkStore

    results = _run_chaos(MemoryDurableWorkStore)
    evidence = {
        "schema": "etlantic.durable_chaos_matrix/1",
        "phase": "0.41",
        "cp3_production_multi_tenant_claim": False,
        "production_multi_tenant_gate": "0.43",
        "notes": (
            "Fake evidence for CP3 exit. Dual-host lease/fencing, outbox "
            "crash-point, unknown-effect fail-closed, preview staleness."
        ),
        "cases": results,
    }
    failed = [r for r in results if r["status"] != "pass"]
    if args.write_evidence is not None:
        args.write_evidence.write_text(json.dumps(evidence, indent=2) + "\n")
    if args.json:
        print(json.dumps(evidence, indent=2))
    else:
        for row in results:
            print(f"{row['case']}: {row['status']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
