#!/usr/bin/env python3
"""CI/local gate: CP4 outage / fail-closed chaos matrix (fake)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

MATRIX_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "11_DEVELOPMENT"
    / "cp4_outage_matrix_0_42.json"
)


def _run_matrix() -> dict[str, object]:
    from etlantic.control_plane import (
        ControlPlaneContext,
        ControlPlaneError,
        EnvironmentRef,
        MemoryApprovalStore,
        MemoryAuditEvidenceStore,
        MemoryPolicyProvider,
        MemoryQuotaProvider,
        Principal,
        SecurityDomain,
        TenantRef,
        WorkspaceRef,
        gate_pre_submit,
    )

    ctx = ControlPlaneContext(
        principal=Principal("chaos", issuer="tests"),
        tenant=TenantRef("t1"),
        workspace=WorkspaceRef("t1", "w1"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )
    cases: list[dict[str, object]] = []

    policy = MemoryPolicyProvider(unavailable=True)
    try:
        gate_pre_submit(
            ctx, policy=policy, plan_fingerprint="p", require_policy=True
        )
        cases.append({"id": "policy_outage", "status": "fail", "detail": "no raise"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "policy_outage",
                "status": "pass" if exc.status == 503 else "fail",
                "http_status": exc.status,
            }
        )

    quotas = MemoryQuotaProvider(unavailable=True)
    try:
        quotas.admit(ctx, resource="concurrency")
        cases.append({"id": "quota_outage", "status": "fail", "detail": "no raise"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "quota_outage",
                "status": "pass" if exc.status == 503 else "fail",
                "http_status": exc.status,
            }
        )

    policy2 = MemoryPolicyProvider()
    policy2.set_rule("pre_submit", "deny")
    try:
        gate_pre_submit(
            ctx, policy=policy2, plan_fingerprint="p", require_policy=True
        )
        cases.append({"id": "policy_deny", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "policy_deny",
                "status": "pass" if exc.status == 403 else "fail",
                "http_status": exc.status,
            }
        )

    approvals = MemoryApprovalStore()
    audit = MemoryAuditEvidenceStore()
    audit.append(ctx, action="chaos", resource="r1")
    ok = audit.verify_chain(ctx)
    cases.append({"id": "audit_integrity", "status": "pass" if ok else "fail"})

    failed = [c for c in cases if c["status"] != "pass"]
    return {
        "matrix_version": "0.42.0",
        "cases": cases,
        "pass": len(failed) == 0,
        "failed": [c["id"] for c in failed],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake", action="store_true", default=True)
    parser.add_argument("--write-matrix", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = _run_matrix()
    if args.write_matrix:
        MATRIX_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.json or args.write_matrix:
        print(json.dumps(result, indent=2))
    else:
        print("pass" if result["pass"] else f"fail: {result['failed']}")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
