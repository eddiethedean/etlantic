"""Plan diff CLI tests."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from etlantic.cli import app

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})
_TARGET = "tests.fixtures.sample_pipeline:SamplePipeline"


def test_plan_diff_equal_targets() -> None:
    result = runner.invoke(
        app,
        ["plan", "diff", _TARGET, _TARGET, "--profile", "local", "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["equal"] is True


def test_plan_explain_human() -> None:
    result = runner.invoke(
        app,
        ["plan", "explain", _TARGET, "--profile", "local", "--format", "human"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "fingerprint:" in result.stdout
    assert "Steps:" in result.stdout
