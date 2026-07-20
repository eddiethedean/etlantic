"""Workspace and durable report CLI tests."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from etlantic.cli import app
from etlantic.workspace import resolve_workspace

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})


def test_resolve_workspace_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    paths = resolve_workspace()
    assert paths.reports == tmp_path / ".etlantic" / "reports"
    assert paths.artifacts == tmp_path / ".etlantic" / "artifacts"


def test_run_persists_report_across_invocations(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init = runner.invoke(app, ["init", "--directory", str(tmp_path), "--force"])
    assert init.exit_code == 0, init.stdout + init.stderr

    run = runner.invoke(
        app,
        [
            "run",
            "pipeline.py:SamplePipeline",
            "--profile",
            "development",
            "--format",
            "json",
            "--no-write",
        ],
    )
    assert run.exit_code == 0, run.stdout + run.stderr
    payload = json.loads(run.stdout)
    run_id = payload["run_id"]

    show = runner.invoke(
        app,
        ["report", "show", run_id, "--format", "json"],
    )
    assert show.exit_code == 0, show.stdout + show.stderr
    shown = json.loads(show.stdout)
    assert shown["run_id"] == run_id

    listed = runner.invoke(app, ["report", "list", "--format", "json"])
    assert listed.exit_code == 0
    reports = json.loads(listed.stdout)["reports"]
    assert any(item["run_id"] == run_id for item in reports)
