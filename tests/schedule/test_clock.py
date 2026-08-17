"""Clock, DST, cron, and catch-up tests for etlantic.schedule/1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from etlantic.control_plane import (
    FakeScheduleClock,
    ScheduleSpec,
    catch_up_nominals,
    next_fire_after,
    parse_cron,
)


def test_interval_next_fire_and_window() -> None:
    spec = ScheduleSpec(kind="interval", interval_seconds=60, timezone="UTC")
    after = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    nxt = next_fire_after(spec, after=after)
    assert nxt == datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    closed = ScheduleSpec(
        kind="interval",
        interval_seconds=60,
        window_end="2026-01-01T00:00:30Z",
    )
    assert next_fire_after(closed, after=after) is None


def test_cron_utc_noon() -> None:
    spec = ScheduleSpec(kind="cron", cron="0 12 * * *", timezone="UTC")
    after = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    nxt = next_fire_after(spec, after=after)
    assert nxt == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_invalid_cron_rejected() -> None:
    with pytest.raises(ValueError, match="PMFIRE120"):
        parse_cron("0 12 *")


def test_catch_up_bounded() -> None:
    spec = ScheduleSpec(
        kind="interval",
        interval_seconds=60,
        misfire="catch_up",
        catch_up_max=3,
    )
    last = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    now = datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    found = catch_up_nominals(spec, last_nominal=last, now=now)
    assert len(found) == 3


def test_america_new_york_spring_forward_skips_missing_hour() -> None:
    """2026-03-08 02:00 local does not exist in America/New_York."""
    spec = ScheduleSpec(kind="cron", cron="30 2 * * *", timezone="America/New_York")
    tz = ZoneInfo("America/New_York")
    before = datetime(2026, 3, 8, 1, 0, tzinfo=tz).astimezone(UTC)
    nxt = next_fire_after(spec, after=before)
    assert nxt is not None
    local = nxt.astimezone(tz)
    assert not (local.month == 3 and local.day == 8 and local.hour == 2)


def test_fake_clock_advance() -> None:
    clock = FakeScheduleClock(datetime(2026, 1, 1, tzinfo=UTC))
    clock.advance(timedelta(seconds=30))
    assert clock.now() == datetime(2026, 1, 1, 0, 0, 30, tzinfo=UTC)
