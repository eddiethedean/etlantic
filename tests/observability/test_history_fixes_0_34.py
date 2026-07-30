"""Regression tests for 0.34 run history and observability fixes."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from etlantic.io_policy import SafeIoPolicy, append_line_safe
from etlantic.observability.history import (
    FileRunHistoryProvider,
    InMemoryRunHistoryProvider,
    RunHistoryQuery,
    coerce_utc,
)
from etlantic.profile import Profile
from etlantic.reports.model import PipelineRunReport, RunSummary
from etlantic.reports.query import query_reports
from etlantic.reports.store import ReportStore
from etlantic.runtime.events import EventBus, LifecycleEvent
from etlantic.runtime.observability_bridge import ObservabilityBridge
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus


def _sample_report(
    *,
    run_id: str = "run-1",
    pipeline_id: str = "pipe-1",
    started_at: datetime | None = None,
) -> PipelineRunReport:
    started = started_at or datetime.now(UTC)
    return PipelineRunReport(
        pipeline_id=pipeline_id,
        plan_id="plan-1",
        run_id=run_id,
        intent=RunIntent.STANDARD,
        profile="development",
        status=RunStatus.SUCCEEDED,
        started_at=started,
        ended_at=started,
        summary=RunSummary(total_steps=1, succeeded=1),
    )


def test_durable_audit_event_append_fails_closed() -> None:
    profile = Profile(
        name="prod",
        security_mode="production",
        plugin_allowlist={"etlantic-polars": "==0.35.0"},
        run_history_provider="file",
        observability_delivery="durable_audit",
    )
    history = MagicMock()
    bridge = ObservabilityBridge(
        events=EventBus(),
        profile=profile,
        run_history_providers={"file": history},
    )
    bridge.configure_for_profile(profile)
    history.append_event.side_effect = RuntimeError("disk full")
    event = LifecycleEvent(kind="step_started", run_id="r1", pipeline_id="p1")
    with pytest.raises(RuntimeError, match="durable_audit"):
        bridge._on_event(event)


def test_append_line_safe_appends_without_reading_full_file(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    policy = SafeIoPolicy.for_root(tmp_path)
    append_line_safe(path, json.dumps({"n": 1}), policy)
    append_line_safe(path, json.dumps({"n": 2}), policy)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["n"] == 1
    assert json.loads(lines[1])["n"] == 2


def test_file_history_append_cross_process(tmp_path) -> None:
    root = tmp_path / "history"
    script = f"""
from datetime import UTC, datetime
from etlantic.observability.history import FileRunHistoryProvider
from etlantic.runtime.events import LifecycleEvent

provider = FileRunHistoryProvider({str(root)!r})
provider.create_run(run_id="shared", pipeline_id="p", plan_id="plan")
provider.append_event(
    LifecycleEvent(
        kind="step_started",
        run_id="shared",
        pipeline_id="p",
        at=datetime.now(UTC),
    )
)
"""
    subprocess.run([sys.executable, "-c", script], check=True, cwd=tmp_path)
    provider = FileRunHistoryProvider(root)
    provider.append_event(
        LifecycleEvent(
            kind="step_finished",
            run_id="shared",
            pipeline_id="p",
            at=datetime.now(UTC),
        )
    )
    payload = provider.read_run("shared")
    assert payload is not None
    assert len(payload["events"]) == 2


def test_list_runs_includes_orphan_report() -> None:
    provider = InMemoryRunHistoryProvider()
    report = _sample_report(run_id="orphan-run")
    provider.append_report(report)
    entries = provider.list_runs()
    assert any(e.run_id == "orphan-run" for e in entries)


def test_create_run_idempotent_for_terminal_status() -> None:
    provider = InMemoryRunHistoryProvider()
    provider.create_run(run_id="r1", pipeline_id="p1")
    provider.append_report(_sample_report(run_id="r1"))
    provider.create_run(run_id="r1", pipeline_id="p1", metadata={"retry": True})
    meta = provider.read_run("r1")
    assert meta is not None
    assert meta["run"]["status"] == "succeeded"
    assert meta["run"]["metadata"].get("retry") is True


def test_list_runs_accepts_naive_since_filter() -> None:
    provider = InMemoryRunHistoryProvider()
    started = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    provider.create_run(run_id="r1", pipeline_id="p1")
    provider._runs["r1"]["started_at"] = started.isoformat()
    naive_since = datetime(2026, 1, 1, 0, 0, 0)
    entries = provider.list_runs(RunHistoryQuery(since=naive_since))
    assert len(entries) == 1


def test_coerce_utc_normalizes_naive() -> None:
    naive = datetime(2026, 1, 1)
    coerced = coerce_utc(naive)
    assert coerced.tzinfo is UTC


def test_query_reports_sorted_by_started_at() -> None:
    store = ReportStore()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    store.put(_sample_report(run_id="r0", started_at=base + timedelta(days=3)))
    store.put(_sample_report(run_id="r1", started_at=base + timedelta(days=1)))
    store.put(_sample_report(run_id="r2", started_at=base + timedelta(days=2)))
    ordered = query_reports(store)
    assert [r.run_id for r in ordered] == ["r0", "r2", "r1"]
