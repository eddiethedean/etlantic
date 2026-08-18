"""MemoryDurableWorkStore persistence for CLI scheduler/worker."""

from __future__ import annotations

import json
from pathlib import Path

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryDurableWorkStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("cli", issuer="tests"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "ws-1"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def test_durable_store_dump_load_roundtrip(tmp_path: Path) -> None:
    ctx = _ctx()
    store = MemoryDurableWorkStore()
    submission, _ = store.accept(
        ctx,
        idempotency_key="idem-1",
        operation="schedule.fire",
        plan_fingerprint="plan",
    )
    path = tmp_path / "durable.json"
    path.write_text(json.dumps(store.dump(), indent=2), encoding="utf-8")
    restored = MemoryDurableWorkStore()
    restored.load(json.loads(path.read_text(encoding="utf-8")))
    assert restored.pending_outbox(ctx)[0].submission_id == submission.submission_id
