"""Durable route-reference and cleanup-fence persistence for phase 0.58."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel.control_plane import (
    SQLModelDurableWorkStore,
    create_durable_tables,
)

pytestmark = pytest.mark.sqlmodel


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="route-cleanup-operator", issuer="phase058"),
        tenant=TenantRef(tenant_id="route-cleanup-tenant"),
        workspace=WorkspaceRef(
            tenant_id="route-cleanup-tenant",
            workspace_id="route-cleanup-workspace",
        ),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def test_sqlmodel_persists_schedule_fences_and_cleanup_state() -> None:
    engine = create_engine("sqlite://")
    create_durable_tables(engine)
    store = SQLModelDurableWorkStore(engine, store_id="phase058-route-cleanup")
    ctx = _context()
    route = "prefect:" + "a" * 64
    reference_id = "schedule:" + "b" * 64
    try:
        active = store.get_execution_route_state(ctx, route)
        store.reserve_execution_route_reference(ctx, route, reference_id)
        assert store.execution_route_reference_counts(ctx, route) == {
            "canonical_submissions": 0,
            "schedule_reservations": 1,
        }

        draining = store.transition_execution_route_state(
            ctx,
            route,
            expected_revision=active.revision,
            status="draining",
        )
        with pytest.raises(ControlPlaneError) as retirement_blocked:
            store.transition_execution_route_state(
                ctx,
                route,
                expected_revision=draining.revision,
                status="retired",
            )
        assert retirement_blocked.value.extensions["reason"] == (
            "execution_route_referenced"
        )

        store.release_execution_route_reference(ctx, route, reference_id)
        retired = store.transition_execution_route_state(
            ctx,
            route,
            expected_revision=draining.revision,
            status="retired",
        )
        cleanup_pending = store.transition_execution_route_state(
            ctx,
            route,
            expected_revision=retired.revision,
            status="cleanup_pending",
        )
        reopened = SQLModelDurableWorkStore(engine, store_id="phase058-route-cleanup")
        assert reopened.get_execution_route_state(ctx, route) == cleanup_pending
        assert reopened.execution_route_reference_counts(ctx, route) == {
            "canonical_submissions": 0,
            "schedule_reservations": 0,
        }
        cleaned = reopened.transition_execution_route_state(
            ctx,
            route,
            expected_revision=cleanup_pending.revision,
            status="cleaned",
        )
        assert cleaned.status == "cleaned"
        assert [item.to_status for item in cleaned.history] == [
            "draining",
            "retired",
            "cleanup_pending",
            "cleaned",
        ]
        assert cleaned.to_dict()["schema"] == "etlantic.control_plane.execution_route/2"
    finally:
        engine.dispose()
