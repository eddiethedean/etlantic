from __future__ import annotations

import pytest

from etlantic.control_plane import (
    DispatchReconciliation,
    DispatchRecord,
    execution_route_backend,
    execution_route_binding,
    validate_execution_route,
)


def _ecs_route() -> str:
    return "ecs:" + "a" * 64


def test_ecs_dispatch_codec_uses_generic_remote_identity() -> None:
    route = _ecs_route()
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/etlantic/task-id"
    record = DispatchRecord(
        submission_id="submission-1",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        execution_route=route,
        binding_fingerprint="a" * 64,
        plan_fingerprint="b" * 64,
        envelope_sha256="c" * 64,
        generation=1,
        creation_key="etlantic-idempotency-key",
        created_at="2026-10-14T12:00:00Z",
        updated_at="2026-10-14T12:00:00Z",
        status="dispatched",
        backend_kind="ecs",
        remote_run_id=task_arn,
    )

    restored = DispatchRecord.from_dict(record.to_dict())

    assert restored == record
    assert restored.remote_run_id == task_arn
    assert restored.prefect_flow_run_id is None
    assert execution_route_backend(route) == "ecs"
    assert execution_route_binding(route) == "a" * 64


def test_ecs_reconciliation_never_populates_prefect_alias() -> None:
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/etlantic/task-id"
    item = DispatchReconciliation(
        from_generation=1,
        to_generation=2,
        prefect_flow_run_id=None,
        authorized_at="2026-10-14T12:00:00Z",
        principal_subject="operator",
        principal_issuer="tests",
        evidence_sha256="d" * 64,
        backend_kind="ecs",
        remote_run_id=task_arn,
    )

    restored = DispatchReconciliation.from_dict(item.to_dict())

    assert restored.remote_run_id == task_arn
    assert restored.prefect_flow_run_id is None


def test_unknown_execution_backend_stays_fail_closed() -> None:
    with pytest.raises(ValueError, match="execution_route"):
        validate_execution_route("batch:" + "a" * 64)
