"""CLI tests for etlantic report query (0.34)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from typer.testing import CliRunner

from etlantic.cli import app
from etlantic.observability.history import FileRunHistoryProvider
from etlantic.reports.model import PipelineRunReport, RunSummary
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus


def test_report_query_cli_since_until(tmp_path, monkeypatch) -> None:
    history_root = tmp_path / "history"
    provider = FileRunHistoryProvider(history_root)
    old = datetime(2020, 1, 1, tzinfo=UTC)
    recent = datetime(2026, 6, 1, tzinfo=UTC)
    for run_id, started in (("old-run", old), ("new-run", recent)):
        provider.append_report(
            PipelineRunReport(
                pipeline_id="p1",
                plan_id="plan",
                run_id=run_id,
                intent=RunIntent.STANDARD,
                profile="development",
                status=RunStatus.SUCCEEDED,
                started_at=started,
                ended_at=started,
                summary=RunSummary(total_steps=1, succeeded=1),
            )
        )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    since = "2026-01-01T00:00:00+00:00"
    result = runner.invoke(
        app,
        ["report", "query", "--since", since, "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    run_ids = {entry["run_id"] for entry in payload["runs"]}
    assert "new-run" in run_ids
    assert "old-run" not in run_ids
