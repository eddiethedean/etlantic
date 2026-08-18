"""Timer-leadership scheduler loop (not etlantic.scheduler/1)."""

from __future__ import annotations

from datetime import datetime

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
from etlantic.control_plane.schedule_models import ScheduleRecord
from etlantic.control_plane.schedule_protocols import (
    PollingWakeTransport,
    ScheduleStore,
    WakeTransport,
)


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
    ) -> None:
        self.schedule_store = schedule_store
        self.durable = durable
        self.clock = clock or SystemClock()
        self.owner_id = owner_id
        self.ttl_seconds = ttl_seconds
        self.wake = wake or PollingWakeTransport()
        self.plan_fingerprint = plan_fingerprint
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
        due = self.schedule_store.due_schedules(ctx, now=_iso(now))
        claimed = 0
        for rec in due:
            claimed += self._fire_due(ctx, rec, now, lease.fencing_token)
        self.wake.notify()
        return claimed

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
            _firing, created = self.schedule_store.claim_firing(
                ctx,
                schedule_id=rec.schedule_id,
                revision_id=rec.revision_id,
                nominal_fire_time=_iso(due),
                owner_id=self.owner_id,
                fencing_token=fencing_token,
                plan_fingerprint=self.plan_fingerprint,
                durable=self.durable,
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
            nominals = catch_up_nominals(rec.spec, last_nominal=last, now=now) or [due]
        else:
            nominals = [due]
        claimed = 0
        for nominal in nominals:
            nxt = next_fire_after(rec.spec, after=nominal, last_nominal=nominal)
            _firing, created = self.schedule_store.claim_firing(
                ctx,
                schedule_id=rec.schedule_id,
                revision_id=rec.revision_id,
                nominal_fire_time=_iso(nominal),
                owner_id=self.owner_id,
                fencing_token=fencing_token,
                plan_fingerprint=self.plan_fingerprint,
                durable=self.durable,
                next_fire_at=_iso(nxt) if nxt is not None else None,
            )
            claimed += int(created)
        return claimed


__all__ = ["FakeScheduleClock", "SchedulerService"]
