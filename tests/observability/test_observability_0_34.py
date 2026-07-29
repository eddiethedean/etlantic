"""Tests for 0.34 observability and run history."""

from __future__ import annotations

from datetime import UTC, datetime

from etlantic.observability import (
    FileRunHistoryProvider,
    InMemoryRunHistoryProvider,
    InMemoryTrendConsumer,
    JsonConsoleObservabilityProvider,
)
from etlantic.runtime.events import LifecycleEvent
from etlantic.testing.event_consumer_conformance import run_event_consumer_conformance_suite
from etlantic.testing.observability_conformance import run_observability_conformance_suite
from etlantic.testing.run_history_conformance import run_run_history_conformance_suite


def test_json_console_observability_conformance() -> None:
    run_observability_conformance_suite(JsonConsoleObservabilityProvider())


def test_in_memory_run_history_conformance() -> None:
    run_run_history_conformance_suite(InMemoryRunHistoryProvider())


def test_file_run_history_roundtrip(tmp_path) -> None:
    provider = FileRunHistoryProvider(tmp_path / "history")
    run_run_history_conformance_suite(provider)


def test_trend_consumer_conformance() -> None:
    consumer = InMemoryTrendConsumer(subject_id="customers")
    run_event_consumer_conformance_suite(consumer)
    summary = consumer.trend_summary("customers")
    assert summary["n"] >= 1


def test_lifecycle_event_correlation_fields() -> None:
    event = LifecycleEvent(
        kind="step_started",
        run_id="run-1",
        pipeline_id="pipe-1",
        plan_id="plan-1",
        region_id="region-a",
        backend="local",
        correlation_id="run-1",
        annotations={"layer": "silver"},
    )
    data = event.to_dict()
    assert data["schema"] == "etlantic.lifecycle_event/1"
    assert data["plan_id"] == "plan-1"
    assert data["annotations"]["layer"] == "silver"
    roundtrip = LifecycleEvent.from_dict(data)
    assert roundtrip.plan_id == "plan-1"
