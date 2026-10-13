"""Live PostgreSQL scheduler leadership and accepted-firing recovery."""

from __future__ import annotations

import hashlib
import os
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from multiprocessing import get_context
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

import sqlalchemy
from sqlalchemy import text

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    DurableWorkStore,
    EnvironmentRef,
    FakeScheduleClock,
    FiringRecord,
    Principal,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    firing_key,
)
from etlantic.runtime.scheduler_service import SchedulerService
from etlantic_sqlmodel.control_plane import (
    SQLModelDurableWorkStore,
    SQLModelScheduleStore,
)
from etlantic_sqlmodel.migrations import upgrade

pytestmark = pytest.mark.sqlmodel


class _FailOnceLinkStore(SQLModelScheduleStore):
    fail_next_link = True

    def link_firing_submission(
        self,
        ctx: ControlPlaneContext,
        firing_id: str,
        *,
        submission_id: str,
        plan_fingerprint: str,
        durable: DurableWorkStore,
        preparation_owner_id: str | None = None,
        preparation_fencing_token: int | None = None,
        recovered: bool = False,
    ) -> FiringRecord:
        if self.fail_next_link:
            self.fail_next_link = False
            raise OSError("simulated scheduler loss before durable firing link")
        return super().link_firing_submission(
            ctx,
            firing_id,
            submission_id=submission_id,
            plan_fingerprint=plan_fingerprint,
            durable=durable,
            preparation_owner_id=preparation_owner_id,
            preparation_fencing_token=preparation_fencing_token,
            recovered=recovered,
        )


def _scheduler_process_tick(
    url: str,
    store_id: str,
    owner_id: str,
    fail_link: bool,
    clock_at: str = "2026-10-01T12:00:00Z",
) -> tuple[int, str]:
    """Run one scheduler tick in a short-lived, independent process."""
    engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
    try:
        ctx = ControlPlaneContext(
            principal=Principal("phase057-scheduler-test"),
            tenant=TenantRef(store_id),
            workspace=WorkspaceRef(store_id, "workspace"),
            environment=EnvironmentRef("test"),
            security_domain=SecurityDomain("phase057-scheduler-test"),
        )
        store_type = _FailOnceLinkStore if fail_link else SQLModelScheduleStore
        schedules = store_type(engine, store_id=store_id)
        durable = SQLModelDurableWorkStore(engine, store_id=store_id)

        def key_for(occurrence: Any, nominal: str) -> str:
            logical_key = firing_key(
                occurrence.schedule_id, occurrence.revision_id, nominal
            )
            return "schedule-" + hashlib.sha256(logical_key.encode()).hexdigest()

        def prepare(_ctx: Any, occurrence: Any, _nominal: str, _firing: Any) -> Any:
            return occurrence

        def submit(_ctx: Any, occurrence: Any, nominal: str) -> tuple[str, str]:
            accepted, _created = durable.accept(
                ctx,
                idempotency_key=key_for(occurrence, nominal),
                operation="run.submit",
                plan_fingerprint="phase057-plan",
                revision_id="phase057-definition-rev",
                input_snapshot='{"schema":"etlantic.execution_envelope/1"}',
                execution_route=occurrence.execution_route,
            )
            return accepted.submission_id, "phase057-plan"

        def recover(_ctx: Any, occurrence: Any, nominal: str) -> tuple[str, str] | None:
            accepted = durable.get_submission_by_idempotency(
                ctx,
                idempotency_key=key_for(occurrence, nominal),
                operation="run.submit",
            )
            if accepted is None:
                return None
            return accepted.submission_id, accepted.plan_fingerprint

        scheduler = SchedulerService(
            schedules,
            durable=durable,
            clock=FakeScheduleClock(
                datetime.fromisoformat(clock_at.replace("Z", "+00:00"))
            ),
            owner_id=owner_id,
            # Keep the lease alive while each independent process starts. The
            # test explicitly releases it once standby behavior is verified.
            ttl_seconds=300,
            run_submitter=submit,
            occurrence_preparer=prepare,
            occurrence_recoverer=recover,
        )
        return scheduler.tick(ctx), scheduler.status().activity
    finally:
        engine.dispose()


def test_postgresql_two_schedulers_recover_accepted_unlinked_firing() -> None:
    url = os.environ.get("ETLANTIC_SQLMODEL_TEST_URL")
    if not url:
        pytest.skip("set ETLANTIC_SQLMODEL_TEST_URL for live PostgreSQL qualification")

    engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
    store_id = f"phase057-scheduler-{uuid.uuid4().hex}"
    try:
        assert upgrade(engine) == "014_cp1_complete_principal_idempotency_0_56"
        ctx = ControlPlaneContext(
            principal=Principal("phase057-scheduler-test"),
            tenant=TenantRef(store_id),
            workspace=WorkspaceRef(store_id, "workspace"),
            environment=EnvironmentRef("test"),
            security_domain=SecurityDomain("phase057-scheduler-test"),
        )
        schedules = _FailOnceLinkStore(engine, store_id=store_id)
        durable = SQLModelDurableWorkStore(engine, store_id=store_id)
        execution_route = "prefect:" + "5" * 64
        schedule = schedules.create(
            ctx,
            definition_id="phase057-pipeline",
            definition_revision_id="phase057-definition-rev",
            profile_name="test",
            spec=ScheduleSpec(kind="interval", interval_seconds=60, overlap="queue"),
            execution_route=execution_route,
            next_fire_at="2026-10-01T12:00:00Z",
        )
        assert (
            schedules.get(ctx, schedule.schedule_id).execution_route == execution_route
        )

        with ProcessPoolExecutor(
            max_workers=1, mp_context=get_context("spawn")
        ) as process:
            first_result = process.submit(
                _scheduler_process_tick, url, store_id, "scheduler-a", True
            ).result(timeout=30)
        assert first_result == (0, "idle")
        firing = schedules.list_firings(ctx, schedule.schedule_id)[0]
        assert firing.status == "accepted"
        assert firing.submission_id is None
        assert len(durable.pending_outbox(ctx, execution_route=execution_route)) == 1
        with ProcessPoolExecutor(
            max_workers=1, mp_context=get_context("spawn")
        ) as process:
            standby_result = process.submit(
                _scheduler_process_tick, url, store_id, "scheduler-b", False
            ).result(timeout=30)
        assert standby_result == (0, "standby")

        # Expire the held lease through the public store API instead of sleeping
        # past a tiny TTL, which races with process startup on slower CI hosts.
        schedules.release_leader(ctx, owner_id="scheduler-a", fencing_token=1)
        with ProcessPoolExecutor(
            max_workers=1, mp_context=get_context("spawn")
        ) as process:
            recovery_result = process.submit(
                _scheduler_process_tick, url, store_id, "scheduler-b", False
            ).result(timeout=30)
        assert recovery_result == (0, "idle")
        firing = schedules.list_firings(ctx, schedule.schedule_id)[0]
        assert firing.submission_id is not None
        assert len(durable.pending_outbox(ctx, execution_route=execution_route)) == 1
        accepted = durable.get_submission(ctx, firing.submission_id)
        assert accepted.plan_fingerprint == "phase057-plan"
        assert accepted.execution_route == execution_route

        route_b = "prefect:" + "6" * 64
        with pytest.raises(ControlPlaneError) as active_transfer:
            schedules.amend(
                ctx,
                schedule.schedule_id,
                expected_revision_id=schedule.revision_id,
                spec=ScheduleSpec(
                    kind="interval", interval_seconds=60, overlap="queue"
                ),
                next_fire_at="2026-10-01T12:01:00Z",
                execution_route=route_b,
                policy_fingerprint="route-b-policy",
                durable=durable,
            )
        assert active_transfer.value.extensions.get("reason") == "active_firing"

        lease = durable.acquire_lease(
            ctx,
            accepted.submission_id,
            owner_id="schedule-transfer-test",
            ttl_seconds=60,
        )
        attempt = durable.start_attempt(
            ctx,
            accepted.submission_id,
            owner_id=lease.owner_id,
            fencing_token=lease.fencing_token,
        )
        durable.finish_attempt(
            ctx,
            attempt.attempt_id,
            owner_id=lease.owner_id,
            fencing_token=lease.fencing_token,
            status="completed",
        )
        amended = schedules.amend(
            ctx,
            schedule.schedule_id,
            expected_revision_id=schedule.revision_id,
            spec=ScheduleSpec(kind="interval", interval_seconds=60, overlap="queue"),
            next_fire_at="2026-10-01T12:01:00Z",
            execution_route=route_b,
            policy_fingerprint="route-b-policy",
            durable=durable,
        )
        assert amended.revision_id != schedule.revision_id
        assert amended.execution_route == route_b
        assert amended.metadata["execution_route_amended_from"] == execution_route

        # Reopen both adapters to prove the route and revision are persisted.
        engine.dispose()
        engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
        schedules = SQLModelScheduleStore(engine, store_id=store_id)
        durable = SQLModelDurableWorkStore(engine, store_id=store_id)
        restored = schedules.get(ctx, schedule.schedule_id)
        assert restored == amended
        old_firing = schedules.list_firings(ctx, schedule.schedule_id)[0]
        old_submission = durable.get_submission(ctx, accepted.submission_id)
        assert old_firing.revision_id == schedule.revision_id
        assert old_firing.submission_id == accepted.submission_id
        assert old_submission.execution_route == execution_route
        assert old_submission.status == "completed"

        with ProcessPoolExecutor(
            max_workers=1, mp_context=get_context("spawn")
        ) as process:
            next_result = process.submit(
                _scheduler_process_tick,
                url,
                store_id,
                "scheduler-b",
                False,
                "2026-10-01T12:01:00Z",
            ).result(timeout=30)
        assert next_result == (1, "idle")
        firings = schedules.list_firings(ctx, schedule.schedule_id)
        assert len(firings) == 2
        new_firing = next(
            item for item in firings if item.revision_id == amended.revision_id
        )
        assert new_firing.submission_id is not None
        new_submission = durable.get_submission(ctx, new_firing.submission_id)
        assert new_submission.execution_route == route_b
    finally:
        with engine.begin() as connection:
            for table in (
                "cp_durable_outbox_entity",
                "cp_durable_submission_entity",
                "cp_durable_snapshot",
                "cp_schedule_snapshot",
            ):
                connection.execute(
                    text(f"DELETE FROM {table} WHERE store_id = :store_id"),
                    {"store_id": store_id},
                )
        engine.dispose()
