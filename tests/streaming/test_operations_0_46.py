"""Handoff, continuous reports, migration, and backpressure (0.46 wave 5)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from etlantic.reports.model import PipelineRunReport
from etlantic.reports.streaming import (
    STREAM_OPS_KEY,
    StreamOperationsSnapshot,
    attach_stream_operations,
)
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus
from etlantic.spark.streaming import project_core_semantics, project_core_watermark
from etlantic.streaming.envelope import ChangeOp, assert_no_payload
from etlantic.streaming.fixtures import InMemoryTriggerQueue
from etlantic.streaming.handoff import (
    SnapshotCut,
    evaluate_handoff,
    handoff_failure_diagnostic,
)
from etlantic.streaming.migration import migrate_envelope_dict, migrate_state_dict
from etlantic.streaming.semantics import StreamSemantics, WatermarkSpec


def _report(**metadata: object) -> PipelineRunReport:
    return PipelineRunReport(
        pipeline_id="p",
        plan_id="plan",
        run_id="run",
        intent=RunIntent.INCREMENTAL,
        profile="development",
        status=RunStatus.RUNNING,
        started_at=datetime.now(tz=UTC),
        metadata=dict(metadata),
    )


def test_handoff_accepts_exact_cut() -> None:
    cut = SnapshotCut(
        snapshot_identity="snap-1",
        stream_position="000010",
        schema_identity="sch-1",
    )
    result = evaluate_handoff(
        snapshot=cut,
        first_stream_position="000010",
        last_snapshot_position="000010",
    )
    assert result.accepted is True
    assert result.gap_detected is False
    assert result.overlap_detected is False


def test_handoff_gap_and_overlap_fail_closed() -> None:
    cut = SnapshotCut(
        snapshot_identity="snap-1",
        stream_position="000010",
        schema_identity="sch-1",
    )
    gap = evaluate_handoff(
        snapshot=cut,
        first_stream_position="000020",
        last_snapshot_position="000010",
    )
    assert gap.accepted is False
    assert gap.gap_detected is True
    assert handoff_failure_diagnostic(gap).code == "PMSTR200"
    overlap = evaluate_handoff(
        snapshot=cut,
        first_stream_position="000001",
        last_snapshot_position="000010",
    )
    assert overlap.accepted is False
    assert overlap.overlap_detected is True
    assert handoff_failure_diagnostic(overlap).code == "PMSTR201"


def test_continuous_report_has_lag_watermark_and_rejected_ids() -> None:
    snapshot = StreamOperationsSnapshot(
        status="running",
        watermark="2026-08-17T12:00:00Z",
        lateness="10s",
        lag=12,
        backpressure="ok",
        replay_window="1h",
        dedupe_horizon="15m",
        state_version="etlantic.stream-state/1",
        provider_guarantee="at_least_once",
        rejected_record_count=2,
        rejected_record_ids=("rec-a", "rec-b"),
        snapshot_identity="snap-1",
    )
    report = _report(**attach_stream_operations({}, snapshot))
    loaded = report.stream_operations()
    assert loaded is not None
    assert loaded.lag == 12
    assert loaded.watermark == "2026-08-17T12:00:00Z"
    assert loaded.rejected_record_ids == ("rec-a", "rec-b")
    encoded = report.to_json()
    assert "payload" not in encoded.lower()
    assert STREAM_OPS_KEY in report.metadata
    assert "secret-row" not in encoded


def test_quality_window_threshold_transition() -> None:
    below = StreamOperationsSnapshot(status="running", lag=4)
    above = StreamOperationsSnapshot(status="running", lag=50, backpressure="shed")
    assert below.lag is not None and below.lag < 10
    assert above.lag is not None and above.lag >= 10
    assert above.backpressure == "shed"


def test_envelope_and_state_migration_mixed_versions() -> None:
    legacy = migrate_envelope_dict(
        {"o": "u", "pos": "000003", "ord": "3", "schema_id": "sch-2", "txn": "t1"}
    )
    assert legacy.op is ChangeOp.UPDATE
    assert legacy.source_position == "000003"
    assert_no_payload(legacy.to_dict())
    state = migrate_state_dict(
        {
            "schema": "etlantic.stream-state/0",
            "id": "src-1",
            "watermark": "w1",
            "cursor": "cursor:src-1",
        }
    )
    assert state.schema == "etlantic.stream-state/1"
    assert state.identity == "src-1"
    assert state.cursor_identity == "cursor:src-1"


def test_trigger_queue_backpressure() -> None:
    queue = InMemoryTriggerQueue(identity="events", bound=2)
    queue.submit()
    queue.submit()
    with pytest.raises(OverflowError, match="exhausted bound"):
        queue.submit()
    fields = queue.report_fields()
    assert fields["etlantic.streaming.backpressure"] is True
    assert fields["etlantic.streaming.outstanding"] == 2


def test_spark_projects_core_stream_names() -> None:
    core = StreamSemantics(
        watermark=WatermarkSpec(event_time_field="ts", delay="10 minutes"),
    )
    spark_water = project_core_watermark(core.watermark)
    assert spark_water.event_time_column == "ts"
    spec = project_core_semantics(core)
    assert spec.watermark is not None
    assert spec.watermark.event_time_column == "ts"
