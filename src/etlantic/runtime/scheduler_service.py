"""Timer-leadership scheduler loop (not etlantic.scheduler/1)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Any, cast

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
    ScheduleStore,
    WakeTransport,
)
from etlantic.profile import Profile

_LOG = logging.getLogger(__name__)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


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
        profile: Profile | str | None = None,
    ) -> None:
        if type(ttl_seconds) is not int or ttl_seconds < 1:
            raise ValueError("ttl_seconds must be a positive integer")
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
        self.run_submitter = run_submitter
        self.occurrence_recoverer: (
            Callable[[ControlPlaneContext, ScheduleRecord, str], tuple[str, str] | None]
            | None
        ) = None
        if run_submitter is not None:
            candidate_recoverer = getattr(
                getattr(run_submitter, "__self__", None),
                "recover_scheduled_occurrence",
                None,
            )
            if callable(candidate_recoverer):
                self.occurrence_recoverer = cast(
                    Callable[
                        [ControlPlaneContext, ScheduleRecord, str],
                        tuple[str, str] | None,
                    ],
                    candidate_recoverer,
                )
        inferred_preparer: (
            Callable[
                [ControlPlaneContext, ScheduleRecord, str, FiringRecord | None],
                ScheduleRecord,
            ]
            | None
        ) = occurrence_preparer
        if inferred_preparer is None and run_submitter is not None:
            submitter_owner = getattr(run_submitter, "__self__", None)
            candidate = getattr(submitter_owner, "prepare_scheduled_occurrence", None)
            if callable(candidate):
                inferred_preparer = cast(
                    Callable[
                        [ControlPlaneContext, ScheduleRecord, str, FiringRecord | None],
                        ScheduleRecord,
                    ],
                    candidate,
                )
        self.occurrence_preparer = inferred_preparer
        self._lease_token: int | None = None
        self.draining = False

    def drain(self) -> None:
        self.draining = True

    def ready(self) -> bool:
        return not self.draining

    def tick(self, ctx: ControlPlaneContext) -> int:
        """Scan due timers once. Duplicate ticks are idempotent via firing keys."""
        if self.draining:
            return 0
        try:
            lease = self.schedule_store.acquire_leader_lease(
                ctx, owner_id=self.owner_id, ttl_seconds=self.ttl_seconds
            )
        except ControlPlaneError:
            return 0
        self._lease_token = lease.fencing_token
        now = self.clock.now()
        self._reconcile_unlinked_firings(ctx)
        due = self.schedule_store.due_schedules(ctx, now=_iso(now))
        claimed = 0
        for rec in due:
            try:
                claimed += self._fire_due(ctx, rec, now, lease.fencing_token)
            except Exception as exc:
                # A bad occurrence must not starve unrelated due schedules.
                # Keep the schedule cursor unchanged so a later tick can retry.
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
            for firing in self.schedule_store.list_firings(ctx, schedule.schedule_id):
                if firing.status != "accepted" or firing.submission_id is not None:
                    continue
                # The firing revision is immutable even if the schedule was
                # amended after a lost link acknowledgement.
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
                                ctx, occurrence, firing.nominal_fire_time, firing
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
                    # One unavailable parameter source must not prevent other
                    # schedules from reconciling or firing in this tick.
                    _LOG.warning(
                        "Scheduled firing reconciliation failed "
                        "(schedule=%s firing=%s error=%s)",
                        schedule.schedule_id,
                        firing.firing_id,
                        type(exc).__name__,
                    )
                    continue

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
