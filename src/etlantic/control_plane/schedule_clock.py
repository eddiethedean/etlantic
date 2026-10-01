"""Injectable clocks and next-fire evaluation (no APScheduler)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from etlantic.control_plane.schedule_diagnostics import fire_diagnostic
from etlantic.control_plane.schedule_models import ScheduleSpec

_CRON_FIELDS = ("minute", "hour", "day", "month", "weekday")


def _as_utc(value: datetime) -> datetime:
    """Normalize clock inputs consistently, treating naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ScheduleClock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """UTC wall clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class FakeScheduleClock:
    """Deterministic clock for DST / misfire / catch-up tests."""

    instant: datetime

    def now(self) -> datetime:
        return _as_utc(self.instant)

    def advance(self, delta: timedelta) -> None:
        self.instant = self.now() + delta

    def set(self, instant: datetime) -> None:
        self.instant = instant


def _parse_cron_field(field: str, minimum: int, maximum: int) -> set[int]:
    text = field.strip()
    if text == "*":
        return set(range(minimum, maximum + 1))
    values: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            base, step_s = part.split("/", 1)
            step = int(step_s)
            part = base if base else "*"
        if part == "*":
            values.update(range(minimum, maximum + 1, step))
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            values.update(range(start, end + 1, step))
            continue
        values.add(int(part))
    if not values:
        raise ValueError(
            fire_diagnostic("invalid_cron", f"empty cron field {field!r}").message
        )
    if any(v < minimum or v > maximum for v in values):
        raise ValueError(
            fire_diagnostic(
                "invalid_cron",
                f"cron field {field!r} outside {minimum}-{maximum}",
            ).message
        )
    return values


def parse_cron(expr: str) -> dict[str, set[int]]:
    """Parse a 5-field cron expression (minute hour day month weekday)."""
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(
            fire_diagnostic(
                "invalid_cron",
                "cron expressions must have 5 fields (minute hour day month weekday)",
            ).code
            + ": cron expressions must have 5 fields (minute hour day month weekday)"
        )
    minute, hour, day, month, weekday = parts
    return {
        "minute": _parse_cron_field(minute, 0, 59),
        "hour": _parse_cron_field(hour, 0, 23),
        "day": _parse_cron_field(day, 1, 31),
        "month": _parse_cron_field(month, 1, 12),
        "weekday": _parse_cron_field(weekday, 0, 6),
    }


def _in_window(spec: ScheduleSpec, instant: datetime) -> bool:
    if spec.window_start:
        start = datetime.fromisoformat(spec.window_start.replace("Z", "+00:00"))
        if instant < start:
            return False
    if spec.window_end:
        end = datetime.fromisoformat(spec.window_end.replace("Z", "+00:00"))
        if instant >= end:
            return False
    return True


def _cron_match(parsed: dict[str, set[int]], local: datetime) -> bool:
    weekday = local.weekday()  # Monday=0 … Sunday=6; cron Sunday=0
    cron_weekday = (local.weekday() + 1) % 7  # convert to Sunday=0
    del weekday
    return (
        local.minute in parsed["minute"]
        and local.hour in parsed["hour"]
        and local.day in parsed["day"]
        and local.month in parsed["month"]
        and cron_weekday in parsed["weekday"]
    )


def next_fire_after(
    spec: ScheduleSpec,
    *,
    after: datetime,
    last_nominal: datetime | None = None,
) -> datetime | None:
    """Return the next UTC fire instant strictly after ``after``.

    Naive ``after`` and ``last_nominal`` values are interpreted as UTC, matching
    :class:`FakeScheduleClock` and avoiding host-timezone-dependent occurrences.
    DST gaps (spring-forward) skip the missing local hour. ``misfire=skip``
    drops that slot; ``fire_once`` / ``catch_up`` fire at the first valid
    local instant after the gap while preserving the intended nominal minute.
    """
    tz = ZoneInfo(spec.timezone)
    cursor = _as_utc(after)
    if not _in_window(spec, cursor + timedelta(seconds=1)):
        if spec.window_end:
            end = datetime.fromisoformat(spec.window_end.replace("Z", "+00:00"))
            if cursor >= end:
                return None
        if spec.window_start:
            start = datetime.fromisoformat(spec.window_start.replace("Z", "+00:00"))
            if cursor < start:
                cursor = start - timedelta(seconds=1)

    if spec.kind == "interval":
        step = timedelta(seconds=int(spec.interval_seconds or 0))
        base = _as_utc(last_nominal) if last_nominal is not None else cursor
        candidate = base + step
        if candidate <= cursor:
            candidate = cursor + step
        if spec.jitter_seconds:
            candidate = candidate + timedelta(seconds=spec.jitter_seconds)
        if not _in_window(spec, candidate):
            return None
        return candidate

    parsed = parse_cron(spec.cron or "")
    # Walk UTC minutes so spring-forward gaps never produce a local match.
    probe = cursor.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = 366 * 24 * 60
    for _ in range(limit):
        local = probe.astimezone(tz)
        if _cron_match(parsed, local):
            utc_fire = local.astimezone(UTC)
            if spec.jitter_seconds:
                utc_fire = utc_fire + timedelta(seconds=spec.jitter_seconds)
            if not _in_window(spec, utc_fire):
                probe += timedelta(minutes=1)
                continue
            return utc_fire
        probe += timedelta(minutes=1)
    raise ValueError(
        fire_diagnostic(
            "invalid_cron",
            "could not find a next fire time within one year",
            path=("spec", "cron"),
        ).message
    )


def catch_up_nominals(
    spec: ScheduleSpec,
    *,
    last_nominal: datetime,
    now: datetime,
) -> list[datetime]:
    """Bounded list of missed nominal fire times between last and now."""
    last_nominal_utc = _as_utc(last_nominal)
    now_utc = _as_utc(now)
    if spec.misfire != "catch_up":
        nxt = next_fire_after(
            spec, after=last_nominal_utc, last_nominal=last_nominal_utc
        )
        return [nxt] if nxt and nxt <= now_utc else []
    found: list[datetime] = []
    cursor = last_nominal_utc
    while len(found) < spec.catch_up_max:
        nxt = next_fire_after(spec, after=cursor, last_nominal=cursor)
        if nxt is None or nxt > now_utc:
            break
        found.append(nxt)
        cursor = nxt
    if spec.catch_up_max == 0:
        return []
    return found
