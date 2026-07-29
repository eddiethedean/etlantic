"""Run history provider conformance helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from etlantic.observability.history import RunHistoryProvider, RunHistoryQuery
from etlantic.reports.model import PipelineRunReport, RunSummary
from etlantic.runtime.events import LifecycleEvent
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus


def assert_run_history_provider_info(provider: RunHistoryProvider) -> None:
    descriptor = provider.descriptor
    assert descriptor.name
    assert descriptor.engine
    assert descriptor.capabilities is not None


def run_run_history_conformance_suite(provider: RunHistoryProvider) -> None:
    """Validate create/append/read/list semantics."""
    assert_run_history_provider_info(provider)
    run_id = "history-conformance"
    provider.create_run(
        run_id=run_id,
        pipeline_id="pipe",
        plan_id="plan-1",
    )
    provider.append_event(
        LifecycleEvent(
            kind="run_started",
            run_id=run_id,
            pipeline_id="pipe",
            plan_id="plan-1",
        )
    )
    started = datetime.now(UTC)
    report = PipelineRunReport(
        pipeline_id="pipe",
        plan_id="plan-1",
        run_id=run_id,
        intent=RunIntent.STANDARD,
        profile="test",
        status=RunStatus.SUCCEEDED,
        started_at=started,
        ended_at=started,
        summary=RunSummary(total_steps=1, succeeded=1),
    )
    provider.append_report(report)
    payload = provider.read_run(run_id)
    assert payload is not None
    assert payload["report"]["run_id"] == run_id
    entries = provider.list_runs(RunHistoryQuery(pipeline_id="pipe"))
    assert any(e.run_id == run_id for e in entries)
