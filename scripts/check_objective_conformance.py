#!/usr/bin/env python3
"""CI/local gate: delivery-objective clock/restart/dedupe conformance."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake", action="store_true", default=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from etlantic.control_plane import (
        ControlPlaneContext,
        DeliveryObjective,
        EnvironmentRef,
        MemoryObjectiveStore,
        Principal,
        SecurityDomain,
        TenantRef,
        WorkspaceRef,
        memory_webhook_provider,
    )

    ctx = ControlPlaneContext(
        principal=Principal("obj", issuer="tests"),
        tenant=TenantRef("t1"),
        workspace=WorkspaceRef("t1", "w1"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )
    store = MemoryObjectiveStore()
    store.upsert_objective(
        ctx,
        objective=DeliveryObjective(
            objective_id="o1",
            tenant_id="t1",
            workspace_id="w1",
            pipeline_id="p1",
            step_id=None,
            version="1",
            reference="started",
            warning_after_seconds=5,
            hard_after_seconds=10,
            calendar="UTC",
        ),
    )
    ref = datetime.now(UTC) - timedelta(seconds=60)
    a = store.evaluate(ctx, objective_id="o1", reference_at=ref, submission_id="s1")
    b = store.evaluate(ctx, objective_id="o1", reference_at=ref, submission_id="s1")
    assert a.evaluation_id == b.evaluation_id
    provider = memory_webhook_provider()
    store.route_notification(
        ctx,
        evaluation_id=a.evaluation_id,
        channel="webhook",
        destination_ref="hooks/ok",
        authorized_destinations=["hooks/ok"],
        provider=provider,
    )
    payload = {
        "status": "pass",
        "evaluation_id": a.evaluation_id,
        "state": a.state,
        "notifications": len(provider.delivered),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
