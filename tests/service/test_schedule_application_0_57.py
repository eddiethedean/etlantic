"""Transport-independent schedule command acceptance tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryScheduleStore,
    Principal,
    ScheduleSpec,
    ScheduleStore,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.service import ScheduleApplicationService


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice", issuer="tests"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="workspace-a"),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def test_headless_schedule_service_authorizes_and_operates_on_canonical_models() -> (
    None
):
    ctx = _context()
    authorizer = MemoryAuthorizer()
    store = MemoryScheduleStore()
    authorizer.grant(ctx, "schedule.write")
    authorizer.grant(ctx, "schedule.read")
    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=store,
        clock=lambda: datetime(2026, 10, 8, 12, 0, tzinfo=UTC),
    )

    created = service.create(
        ctx,
        "pipeline-a",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
    )
    assert created.definition_id == "pipeline-a"
    assert service.get(ctx, created.schedule_id) == created
    assert service.list_definition(ctx, "pipeline-a") == (created,)


def test_schedule_service_denies_before_reading_or_mutating_store() -> None:
    class UntouchableStore:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"store accessed before authorization: {name}")

    service = ScheduleApplicationService(
        authorizer=MemoryAuthorizer(),
        schedule_store=cast(ScheduleStore, UntouchableStore()),
    )
    with pytest.raises(ControlPlaneError):
        service.create(
            _context(),
            "pipeline-a",
            spec=ScheduleSpec(kind="interval", interval_seconds=60),
        )
