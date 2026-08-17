"""Memory ScheduleStore conformance."""

from __future__ import annotations

from etlantic.control_plane import MemoryScheduleStore
from etlantic.testing import run_schedule_store_conformance_suite


def test_memory_schedule_store_conformance() -> None:
    run_schedule_store_conformance_suite(MemoryScheduleStore())
