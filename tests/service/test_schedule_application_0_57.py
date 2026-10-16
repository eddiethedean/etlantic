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
    next_fire_after,
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


def test_interval_skip_preserves_the_external_rate_grid() -> None:
    spec = ScheduleSpec(kind="interval", interval_seconds=60, misfire="skip")
    next_cursor = next_fire_after(
        spec,
        after=datetime(2026, 10, 8, 12, 2, 5, tzinfo=UTC),
        last_nominal=datetime(2026, 10, 8, 12, 0, tzinfo=UTC),
    )

    assert next_cursor == datetime(2026, 10, 8, 12, 3, tzinfo=UTC)


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


def test_external_resume_reanchors_and_fences_old_scheduler_events() -> None:
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "schedule.write")
    store = MemoryScheduleStore()
    workload = Principal(subject="timer", issuer="tests", kind="workload")
    anchor = "2026-10-08T10:00:00Z"
    record = store.create(
        ctx,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        workload_identity=workload,
        timer_owner="external",
        next_fire_at="2026-10-08T10:01:00Z",
        timer_schedule_start_at=anchor,
    )
    store.pause(ctx, record.schedule_id)
    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=store,
        clock=lambda: datetime(2026, 10, 8, 12, 0, 0, 900000, tzinfo=UTC),
    )

    resumed = service.resume(ctx, record.schedule_id)

    assert resumed.status == "active"
    assert resumed.timer_owner_generation == record.timer_owner_generation + 1
    assert resumed.timer_schedule_start_at == "2026-10-08T12:00:00Z"
    assert resumed.next_fire_at == "2026-10-08T12:01:00Z"


def test_external_resume_waits_for_unlinked_occurrence_preparation() -> None:
    owner_ctx = _context()
    workload = Principal(subject="timer", issuer="tests", kind="workload")
    trigger_ctx = replace(owner_ctx, principal=workload)
    authorizer = MemoryAuthorizer()
    authorizer.grant(owner_ctx, "schedule.write")
    for action in ("schedule.trigger", "run.submit"):
        authorizer.grant(trigger_ctx, action)
    store = MemoryScheduleStore()
    nominal = "2026-10-08T12:00:00Z"
    record = store.create(
        owner_ctx,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        workload_identity=workload,
        timer_owner="external",
        next_fire_at=nominal,
    )

    class IntermittentManagedService:
        preparation_calls = 0

        def recover_scheduled_occurrence(
            self, *_args: object, **_kwargs: object
        ) -> None:
            return None

        def prepare_scheduled_occurrence(
            self, *_args: object, **_kwargs: object
        ) -> Any:
            self.preparation_calls += 1
            if self.preparation_calls == 1:
                raise ControlPlaneError(
                    "temporary preparation outage", code="PMCP503", status=503
                )
            raise ControlPlaneError(
                "invalid scheduled parameters", code="PMCP422", status=422
            )

        def submit_scheduled_run(self, *_args: object, **_kwargs: object) -> Any:
            raise AssertionError("failed preparation must not submit a run")

    managed = IntermittentManagedService()
    now = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=store,
        managed_service=managed,
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
        delivery_attempt_id="attempt-resume-pending",
        correlation_id="corr-resume-pending",
    )

    with pytest.raises(ControlPlaneError) as outage:
        service.trigger_external(trigger_ctx, envelope)
    assert outage.value.status == 503
    store.pause(owner_ctx, record.schedule_id)

    with pytest.raises(ControlPlaneError) as blocked_resume:
        service.resume(owner_ctx, record.schedule_id)
    assert blocked_resume.value.status == 409
    assert blocked_resume.value.extensions["reason"] == (
        "occurrence_preparation_pending"
    )

    with pytest.raises(ControlPlaneError) as retry:
        service.trigger_external(trigger_ctx, envelope)
    assert retry.value.status == 422
    firing = store.list_firings(owner_ctx, record.schedule_id)[0]
    assert firing.status == "failed_preparation"
    assert firing.submission_id is None
    assert managed.preparation_calls == 2

    resumed = service.resume(owner_ctx, record.schedule_id)
    assert resumed.status == "active"
    assert resumed.timer_owner_generation == record.timer_owner_generation + 1


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


@pytest.mark.parametrize(
    ("misfire", "catch_up_max"),
    [("skip", 10), ("catch_up", 0)],
)
def test_external_trigger_skips_late_occurrence_and_advances_past_backlog(
    misfire: Any, catch_up_max: int
) -> None:
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
            kind="interval",
            interval_seconds=60,
            misfire=misfire,
            catch_up_max=catch_up_max,
            overlap="queue",
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


def test_external_trigger_terminalizes_permanent_preparation_failure() -> None:
    ctx = replace(
        _context(),
        principal=Principal(subject="timer", issuer="tests", kind="workload"),
    )
    authorizer = MemoryAuthorizer()
    for action in ("schedule.trigger", "run.submit"):
        authorizer.grant(ctx, action)
    schedules = MemoryScheduleStore()
    nominal = "2026-10-08T12:00:00Z"
    record = schedules.create(
        ctx,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60, overlap="queue"),
        workload_identity=ctx.principal,
        timer_owner="external",
        next_fire_at=nominal,
    )
    preparations: list[str] = []

    class InvalidManagedService:
        def recover_scheduled_occurrence(
            self, *_args: object, **_kwargs: object
        ) -> None:
            return None

        def prepare_scheduled_occurrence(
            self, *_args: object, **_kwargs: object
        ) -> Any:
            preparations.append("prepare")
            raise ControlPlaneError(
                "scheduled parameters are invalid", code="PMCP422", status=422
            )

        def submit_scheduled_run(self, *_args: object, **_kwargs: object) -> Any:
            raise AssertionError("invalid preparation must not submit a run")

    now = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=schedules,
        managed_service=InvalidManagedService(),
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
        delivery_attempt_id="attempt-invalid-preparation",
        correlation_id="corr-invalid-preparation",
    )

    with pytest.raises(ControlPlaneError) as failure:
        service.trigger_external(ctx, envelope)
    assert failure.value.status == 422
    firing = schedules.list_firings(ctx, record.schedule_id)[0]
    assert firing.status == "failed_preparation"
    assert firing.preparation_owner_id is None

    duplicate = service.trigger_external(ctx, envelope)
    assert duplicate.status == "skipped"
    assert duplicate.firing_status == "failed_preparation"
    assert duplicate.duplicate
    assert preparations == ["prepare"]

    amended = schedules.amend(
        ctx,
        record.schedule_id,
        expected_revision_id=record.revision_id,
        spec=ScheduleSpec(kind="interval", interval_seconds=120, overlap="queue"),
        next_fire_at="2026-10-08T12:02:00Z",
    )
    transferred = schedules.transfer_timer_owner(
        ctx,
        record.schedule_id,
        expected_revision_id=amended.revision_id,
        expected_generation=amended.timer_owner_generation,
        timer_owner="local",
        workload_identity=None,
        policy_fingerprint="policy",
    )
    deleted = schedules.delete(ctx, record.schedule_id)
    assert transferred.timer_owner == "local"
    assert deleted.status == "deleted"


def test_external_trigger_accepts_utc_delivery_for_legacy_offset_cursor() -> None:
    ctx = replace(
        _context(),
        principal=Principal(subject="timer", issuer="tests", kind="workload"),
    )
    authorizer = MemoryAuthorizer()
    for action in ("schedule.write", "schedule.trigger", "run.submit"):
        authorizer.grant(ctx, action)
    schedules = MemoryScheduleStore()
    spec = ScheduleSpec(
        kind="interval",
        interval_seconds=60,
        window_start="2026-10-08T08:00:00-04:00",
        overlap="queue",
    )
    legacy_cursor = next_fire_after(
        spec,
        after=datetime(2026, 10, 8, 11, 0, tzinfo=UTC),
    )
    assert legacy_cursor is not None
    stored_cursor = legacy_cursor.isoformat()
    nominal = legacy_cursor.astimezone(UTC).isoformat().replace("+00:00", "Z")
    record = schedules.create(
        ctx,
        definition_id="pipeline-a",
        profile_name="test",
        spec=spec,
        workload_identity=ctx.principal,
        timer_owner="external",
        next_fire_at=stored_cursor,
    )
    normalized = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=MemoryScheduleStore(),
        clock=lambda: datetime(2026, 10, 8, 11, 0, tzinfo=UTC),
    ).create(ctx, "pipeline-a", spec=spec)
    assert normalized.next_fire_at == "2026-10-08T12:00:59Z"

    class InvalidManagedService:
        def recover_scheduled_occurrence(
            self, *_args: object, **_kwargs: object
        ) -> None:
            return None

        def prepare_scheduled_occurrence(
            self, *_args: object, **_kwargs: object
        ) -> Any:
            raise ControlPlaneError(
                "test reached occurrence preparation", code="PMCP422", status=422
            )

    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=schedules,
        managed_service=InvalidManagedService(),
        durable_work=object(),
        clock=lambda: legacy_cursor.astimezone(UTC),
    )
    envelope = TriggerEnvelope(
        schedule_id=record.schedule_id,
        schedule_revision_id=record.revision_id,
        timer_owner_generation=record.timer_owner_generation,
        occurrence_id=external_occurrence_id(
            record.schedule_id, record.revision_id, nominal
        ),
        scheduled_at=nominal,
        delivery_attempt_id="attempt-offset-cursor",
        correlation_id="corr-offset-cursor",
    )

    with pytest.raises(ControlPlaneError) as failure:
        service.trigger_external(ctx, envelope)
    assert failure.value.status == 422
    assert schedules.list_firings(ctx, record.schedule_id)[0].nominal_fire_time == (
        nominal
    )
