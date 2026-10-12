"""Snapshot round trips for the phase 0.58 in-memory durable store."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import json

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    DispatchReconciliation,
    DispatchRecord,
    EnvironmentRef,
    ExecutionRouteTransition,
    MemoryDurableWorkStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("snapshot-worker", issuer="tests"),
        tenant=TenantRef("tenant-snapshot"),
        workspace=WorkspaceRef("tenant-snapshot", "workspace-snapshot"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("internal"),
    )


def test_memory_durable_snapshot_round_trips_dispatch_reconciliation_history() -> None:
    ctx = _context()
    reconciliation = DispatchReconciliation(
        from_generation=3,
        to_generation=4,
        prefect_flow_run_id="flow-run-snapshot",
        authorized_at="2026-10-12T12:00:00Z",
        principal_subject=ctx.principal.subject,
        principal_issuer=ctx.principal.issuer,
        evidence_sha256="a" * 64,
    )
    dispatch = DispatchRecord(
        submission_id="sub-snapshot",
        tenant_id=ctx.tenant.tenant_id,
        workspace_id=ctx.workspace.workspace_id,
        execution_route="prefect:" + "4" * 64,
        binding_fingerprint="4" * 64,
        plan_fingerprint="b" * 64,
        envelope_sha256="c" * 64,
        generation=4,
        creation_key="etlantic-snapshot",
        created_at="2026-10-12T11:00:00Z",
        updated_at="2026-10-12T12:00:00Z",
        reconciliation_history=(reconciliation,),
    )
    store = MemoryDurableWorkStore()
    store._dispatches[(*ctx.scope_key, dispatch.submission_id)] = dispatch

    snapshot = json.loads(json.dumps(store.dump()))
    restored = MemoryDurableWorkStore()
    restored.load(snapshot)

    restored_dispatch = restored.get_dispatch(ctx, dispatch.submission_id)
    assert restored_dispatch == dispatch
    assert restored_dispatch.reconciliation_history[0].to_dict() == (
        reconciliation.to_dict()
    )


def test_memory_durable_snapshot_round_trips_route_lifecycle_and_reservations() -> None:
    ctx = _context()
    store = MemoryDurableWorkStore()
    reserved_route = "prefect:" + "1" * 64
    retired_route = "prefect:" + "2" * 64

    store.reserve_execution_route_reference(
        ctx, reserved_route, "schedule:scheduled-job"
    )
    draining = store.transition_execution_route_state(
        ctx, reserved_route, expected_revision=0, status="draining"
    )
    retired = store.transition_execution_route_state(
        ctx, retired_route, expected_revision=0, status="draining"
    )
    retired = store.transition_execution_route_state(
        ctx,
        retired_route,
        expected_revision=retired.revision,
        status="retired",
    )

    snapshot = json.loads(json.dumps(store.dump()))
    restored = MemoryDurableWorkStore()
    restored.load(snapshot)

    assert restored.get_execution_route_state(ctx, reserved_route) == draining
    assert restored.execution_route_reference_counts(ctx, reserved_route) == {
        "canonical_submissions": 0,
        "schedule_reservations": 1,
    }
    restored_history = restored.get_execution_route_state(ctx, reserved_route).history
    assert len(restored_history) == 1
    assert isinstance(restored_history[0], ExecutionRouteTransition)

    with pytest.raises(ControlPlaneError) as referenced:
        restored.transition_execution_route_state(
            ctx,
            reserved_route,
            expected_revision=draining.revision,
            status="retired",
        )
    assert referenced.value.extensions["reason"] == "execution_route_referenced"

    assert restored.get_execution_route_state(ctx, retired_route) == retired
    with pytest.raises(ControlPlaneError) as retired_denial:
        restored.reserve_execution_route_reference(
            ctx, retired_route, "schedule:must-stay-fenced"
        )
    assert retired_denial.value.extensions["reason"] == "execution_route_retired"


def test_memory_durable_snapshot_loads_legacy_payload_without_route_state() -> None:
    restored = MemoryDurableWorkStore()

    # Snapshots written before route lifecycle was introduced remain readable.
    restored.load({"submissions": {}, "idempotency": {}, "dispatches": {}})

    route = "prefect:" + "3" * 64
    state = restored.get_execution_route_state(_context(), route)
    assert state.status == "active"
    assert state.revision == 0
    assert state.history == ()
