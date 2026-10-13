"""Transport-independent schedule command acceptance tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast

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
    TriggerEnvelope,
    WorkspaceRef,
    external_occurrence_id,
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


def test_external_trigger_skips_late_occurrence_and_advances_past_backlog() -> None:
    ctx = replace(
        _context(),
        principal=Principal(subject="timer", issuer="tests", kind="workload"),
    )
    authorizer = MemoryAuthorizer()
    for action in ("schedule.trigger", "run.submit"):
        authorizer.grant(ctx, action)
    schedules = MemoryScheduleStore()
    nominal = "2026-10-01T12:00:00Z"
    record = schedules.create(
        ctx,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(
            kind="interval", interval_seconds=60, misfire="skip", overlap="queue"
        ),
        workload_identity=ctx.principal,
        timer_owner="external",
        next_fire_at=nominal,
    )

    class UnusedManagedService:
        def prepare_scheduled_occurrence(
            self, *_args: object, **_kwargs: object
        ) -> Any:
            raise AssertionError("skipped misfire must not prepare a run")

    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=schedules,
        managed_service=UnusedManagedService(),
        durable_work=object(),
        clock=lambda: now,
    )
    envelope = TriggerEnvelope(
        schedule_id=record.schedule_id,
        schedule_revision_id=record.revision_id,
        timer_owner_generation=record.timer_owner_generation,
        occurrence_id=external_occurrence_id(
            record.schedule_id, record.revision_id, nominal
        ),
        scheduled_at=nominal,
        delivery_attempt_id="attempt-late",
        correlation_id="corr-late",
    )

    receipt = service.trigger_external(ctx, envelope)

    assert receipt.status == "skipped"
    assert receipt.firing_status == "skipped_misfire"
    assert schedules.list_firings(ctx, record.schedule_id)[0].status == (
        "skipped_misfire"
    )
    assert schedules.get(ctx, record.schedule_id).next_fire_at == (
        "2026-10-02T12:01:00Z"
    )
