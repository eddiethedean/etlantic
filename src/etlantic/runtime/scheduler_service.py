"""Timer-leadership scheduler loop (not etlantic.scheduler/1)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Any

from etlantic.control_plane.authz import validate_control_plane_context
from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.schedule_clock import (
    FakeScheduleClock,
    ScheduleClock,
    SystemClock,
    catch_up_nominals,
    next_fire_after,
)
from etlantic.control_plane.schedule_models import (
    FiringRecord,
    FiringStatus,
    ScheduleRecord,
)
from etlantic.control_plane.schedule_protocols import (
    PollingWakeTransport,
    ScheduledOccurrenceService,
    ScheduleStore,
    WakeTransport,
)
from etlantic.profile import Profile
from etlantic.runtime.role import RuntimeRoleLifecycle, RuntimeRoleStatus

_LOG = logging.getLogger(__name__)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _is_nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


class SchedulerService:
    """Leader-elected due-timer scanner. Production must split from FastAPI."""

    def __init__(
        self,
        schedule_store: ScheduleStore,
        *,
        durable: DurableWorkStore | None = None,
        clock: ScheduleClock | None = None,
        owner_id: str = "scheduler-1",
        ttl_seconds: int = 30,
        wake: WakeTransport | None = None,
        plan_fingerprint: str = "plan",
        run_submitter: (
            Callable[[ControlPlaneContext, ScheduleRecord, str], tuple[str, str]] | None
        ) = None,
        occurrence_preparer: (
            Callable[
                [ControlPlaneContext, ScheduleRecord, str, FiringRecord | None],
                ScheduleRecord,
            ]
            | None
        ) = None,
        occurrence_recoverer: (
            Callable[[ControlPlaneContext, ScheduleRecord, str], tuple[str, str] | None]
            | None
        ) = None,
        occurrence_service: ScheduledOccurrenceService | None = None,
        allow_callback_only: bool = False,
        profile: Profile | str | None = None,
    ) -> None:
        if type(ttl_seconds) is not int or ttl_seconds < 1:
            raise ValueError("ttl_seconds must be a positive integer")
        if not _is_nonempty_text(owner_id):
            raise ValueError("owner_id must be a non-empty scheduler identity")
        if profile is not None:
            from etlantic.control_plane.schedule_trust import validate_schedule_runtime

            validate_schedule_runtime(profile, schedule_store)
        self.schedule_store = schedule_store
        self.durable = durable
        self.clock = clock or SystemClock()
        self.owner_id = owner_id
        self.ttl_seconds = ttl_seconds
        self.wake = wake or PollingWakeTransport()
        self.plan_fingerprint = plan_fingerprint
        if occurrence_service is not None:
            if not all(
                callable(getattr(occurrence_service, name, None))
                for name in (
                    "prepare_scheduled_occurrence",
                    "submit_scheduled_run",
                    "recover_scheduled_occurrence",
                )
            ):
                raise TypeError(
                    "occurrence_service must provide preparation, submission, and recovery"
                )
            run_submitter = occurrence_service.submit_scheduled_run
            occurrence_preparer = occurrence_service.prepare_scheduled_occurrence
            occurrence_recoverer = occurrence_service.recover_scheduled_occurrence
        if (
            run_submitter is not None
            and not all(
                callback is not None
                for callback in (
                    occurrence_preparer,
                    occurrence_recoverer,
                )
            )
            and not allow_callback_only
        ):
            raise ValueError(
                "managed scheduling requires explicit preparation and recovery; "
                "set allow_callback_only=True only for a documented low-level path"
            )
        if run_submitter is not None and durable is None:
            raise ValueError(
                "scheduled submission requires a durable work store for linking"
            )
        self.run_submitter = run_submitter
        self.occurrence_recoverer: (
            Callable[[ControlPlaneContext, ScheduleRecord, str], tuple[str, str] | None]
            | None
        ) = occurrence_recoverer
        self.occurrence_preparer = occurrence_preparer
        self._lease_token: int | None = None
        self._role = RuntimeRoleLifecycle(
            "scheduler",
            capabilities=(
                "read_status",
                "cooperative_drain",
                "leader_standby",
                "managed_occurrence_recovery"
                if self.durable is not None
                and self.run_submitter is not None
                and self.occurrence_preparer is not None
                and self.occurrence_recoverer is not None
                else "callback_occurrence_only",
            ),
        )

    def drain(self) -> None:
        self._role.request_drain()

    def request_drain(self) -> RuntimeRoleStatus:
        return self._role.request_drain()

    @property
    def draining(self) -> bool:
        return self._role.draining

    @draining.setter
    def draining(self, value: bool) -> None:
        if value:
            self._role.request_drain()

    def status(self) -> RuntimeRoleStatus:
        return self._role.status()

    def ready(self) -> bool:
        return self._role.status().ready

    def tick(self, ctx: ControlPlaneContext) -> int:
        """Scan due timers once. Duplicate ticks are idempotent via firing keys."""
        validate_control_plane_context(ctx)
        if not self._role.begin_tick():
            return 0
        try:
            return self._tick(ctx)
        except Exception:
            self._role.observe_prerequisites(
                "unusable", reason_code="scheduler_tick_failed"
            )
            raise
        finally:
            self._role.end_tick()

    def _tick(self, ctx: ControlPlaneContext) -> int:
        try:
            lease = self.schedule_store.acquire_leader_lease(
                ctx, owner_id=self.owner_id, ttl_seconds=self.ttl_seconds
            )
        except ControlPlaneError as exc:
            if str(exc) == "scheduler leader lease held":
                self._role.observe_standby()
            else:
                self._role.observe_prerequisites(
                    "unusable", reason_code="schedule_store_unavailable"
                )
            return 0
        except Exception:
            self._role.observe_prerequisites(
                "unusable", reason_code="schedule_store_unavailable"
            )
            return 0
        self._role.observe_prerequisites("usable")
        self._lease_token = lease.fencing_token
        now = self.clock.now()
        self._reconcile_unlinked_firings(ctx)
        due = self.schedule_store.due_schedules(ctx, now=_iso(now))
        claimed = 0
        for rec in due:
            if self.draining:
                break
            try:
                claimed += self._fire_due(ctx, rec, now, lease.fencing_token)
            except Exception as exc:
                # A bad occurrence must not starve unrelated due schedules.
                # Keep the schedule cursor unchanged so a later tick can retry.
                self._role.observe_prerequisites(
                    "unusable", reason_code="schedule_dispatch_failed"
                )
                _LOG.warning(
                    "Scheduled occurrence failed (schedule_id=%s error=%s)",
                    rec.schedule_id,
                    type(exc).__name__,
                )
        self.wake.notify()
        return claimed

    def _reconcile_unlinked_firings(self, ctx: ControlPlaneContext) -> None:
        """Retry managed submissions for durable occurrences not yet linked."""
        if self.run_submitter is None or self.durable is None:
            return
        for schedule in self.schedule_store.list_schedules(ctx):
            if self.draining:
                return
            for firing in self.schedule_store.list_firings(ctx, schedule.schedule_id):
                if self.draining:
                    return
                if firing.status != "accepted" or firing.submission_id is not None:
                    continue
                if not self._role.begin_dispatch():
                    return
                try:
                    # The firing revision is immutable even if the schedule
                    # was amended after a lost link acknowledgement.
                    occurrence = replace(
                        schedule,
                        revision_id=firing.revision_id,
                        occurrence_snapshot=dict(firing.metadata),
                        occurrence_inputs=None,
                    )
                    try:
                        recovered = (
                            self.occurrence_recoverer(
                                ctx, occurrence, firing.nominal_fire_time
                            )
                            if self.occurrence_recoverer is not None
                            else None
                        )
                        if recovered is None:
                            prepared = (
                                self.occurrence_preparer(
                                    ctx,
                                    occurrence,
                                    firing.nominal_fire_time,
                                    firing,
                                )
                                if self.occurrence_preparer is not None
                                else occurrence
                            )
                            recovered = self.run_submitter(
                                ctx, prepared, firing.nominal_fire_time
                            )
                        submission_id, fingerprint = recovered
                        self.schedule_store.link_firing_submission(
                            ctx,
                            firing.firing_id,
                            submission_id=submission_id,
                            plan_fingerprint=fingerprint,
                            durable=self.durable,
                        )
                    except Exception as exc:
                        # One unavailable parameter source must not prevent
                        # other schedules from reconciling or firing.
                        _LOG.warning(
                            "Scheduled firing reconciliation failed "
                            "(schedule=%s firing=%s error=%s)",
                            schedule.schedule_id,
                            firing.firing_id,
                            type(exc).__name__,
                        )
                        self._role.observe_prerequisites(
                            "unusable", reason_code="occurrence_recovery_failed"
                        )
                finally:
                    self._role.end_dispatch()

    def _fire_due(
        self,
        ctx: ControlPlaneContext,
        rec: ScheduleRecord,
        now: datetime,
        fencing_token: int,
    ) -> int:
        if rec.next_fire_at is None:
            return 0
        due = datetime.fromisoformat(rec.next_fire_at.replace("Z", "+00:00"))
        if due > now:
            return 0
        if rec.spec.misfire == "skip" and due < now:
            nxt = next_fire_after(rec.spec, after=now, last_nominal=due)
            created = self._claim_scheduled_firing(
                ctx,
                rec,
                _iso(due),
                fencing_token,
                next_fire_at=_iso(nxt) if nxt is not None else None,
                skip_status="skipped_misfire",
            )
            return int(created)
        if rec.spec.misfire == "catch_up":
            from datetime import timedelta

            if rec.spec.kind == "interval" and rec.spec.interval_seconds:
                last = due - timedelta(seconds=int(rec.spec.interval_seconds))
            else:
                last = due - timedelta(minutes=1)
            if rec.spec.catch_up_max == 0:
                nxt = next_fire_after(rec.spec, after=now, last_nominal=due)
                created = self._claim_scheduled_firing(
                    ctx,
                    rec,
                    _iso(due),
                    fencing_token,
                    next_fire_at=_iso(nxt) if nxt is not None else None,
                    skip_status="skipped_misfire",
                )
                return int(created)
            nominals = catch_up_nominals(rec.spec, last_nominal=last, now=now)
        else:
            nominals = [due]
        claimed = 0
        for nominal in nominals:
            if self.draining:
                break
            nxt = next_fire_after(rec.spec, after=nominal, last_nominal=nominal)
            created = self._claim_scheduled_firing(
                ctx,
                rec,
                _iso(nominal),
                fencing_token,
                next_fire_at=_iso(nxt) if nxt is not None else None,
            )
            claimed += int(created)
        return claimed

    def _claim_scheduled_firing(
        self,
        ctx: ControlPlaneContext,
        rec: ScheduleRecord,
        nominal_fire_time: str,
        fencing_token: int,
        *,
        next_fire_at: str | None,
        skip_status: FiringStatus | None = None,
    ) -> bool:
        if not self._role.begin_dispatch():
            return False
        try:
            return self._claim_scheduled_firing_reserved(
                ctx,
                rec,
                nominal_fire_time,
                fencing_token,
                next_fire_at=next_fire_at,
                skip_status=skip_status,
            )
        finally:
            self._role.end_dispatch()

    def _claim_scheduled_firing_reserved(
        self,
        ctx: ControlPlaneContext,
        rec: ScheduleRecord,
        nominal_fire_time: str,
        fencing_token: int,
        *,
        next_fire_at: str | None,
        skip_status: FiringStatus | None = None,
    ) -> bool:
        prepared = (
            self.occurrence_preparer(ctx, rec, nominal_fire_time, None)
            if self.occurrence_preparer is not None
            else rec
        )
        claim_options: dict[str, Any] = {}
        if prepared.occurrence_snapshot is not None:
            claim_options["metadata"] = dict(prepared.occurrence_snapshot)
        try:
            firing, created = self.schedule_store.claim_firing(
                ctx,
                schedule_id=rec.schedule_id,
                revision_id=rec.revision_id,
                nominal_fire_time=nominal_fire_time,
                owner_id=self.owner_id,
                fencing_token=fencing_token,
                plan_fingerprint=(
                    "managed-admission-pending"
                    if self.run_submitter is not None
                    else self.plan_fingerprint
                ),
                durable=self.durable,
                next_fire_at=next_fire_at,
                admit_submission=self.run_submitter is None,
                skip_status=skip_status,
                **claim_options,
            )
        except ControlPlaneError as exc:
            # The schedule changed after this scan. A subsequent tick will
            # reload current state; lease and provider conflicts still surface.
            if exc.code == "PMFIRE409":
                return False
            raise
        if (
            created
            and firing.status == "accepted"
            and self.run_submitter is not None
            and self.durable is not None
        ):
            prepared = (
                self.occurrence_preparer(ctx, rec, nominal_fire_time, firing)
                if self.occurrence_preparer is not None
                else prepared
            )
            submission_id, fingerprint = self.run_submitter(
                ctx, prepared, nominal_fire_time
            )
            self.schedule_store.link_firing_submission(
                ctx,
                firing.firing_id,
                submission_id=submission_id,
                plan_fingerprint=fingerprint,
                durable=self.durable,
            )
        return created


__all__ = ["FakeScheduleClock", "SchedulerService"]
