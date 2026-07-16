"""CLI smoke tests."""

from __future__ import annotations

import re

import pytest
import typer
from typer.testing import CliRunner

from pipelantic.cli import _build_selection, app

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _plain_output(result: object) -> str:
    stderr = getattr(result, "stderr", "") or ""
    stdout = getattr(result, "stdout", "") or ""
    return _ANSI_ESCAPE.sub("", stderr + stdout).lower()


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.5.0" in result.stdout


def test_cli_validate_and_plan() -> None:
    target = "tests.fixtures.sample_pipeline:SamplePipeline"
    result = runner.invoke(app, ["validate", target, "--profile", "local"])
    assert result.exit_code == 0
    result = runner.invoke(
        app, ["plan", target, "--profile", "local", "--format", "json"]
    )
    assert result.exit_code == 0, result.stderr
    assert "pipelantic.plan/1" in result.stdout


def test_cli_plan_explain() -> None:
    target = "tests.fixtures.sample_pipeline:SamplePipeline"
    result = runner.invoke(
        app, ["plan", "explain", target, "--profile", "local", "--format", "json"]
    )
    assert result.exit_code == 0, result.stderr
    assert "fingerprint" in result.stdout
    assert "steps" in result.stdout


def test_build_selection_rejects_conflicting_flags() -> None:
    with pytest.raises(typer.BadParameter, match="only one"):
        _build_selection(run_one="step", run_until="step", nodes=None)


def test_cli_conflicting_selection_flags() -> None:
    target = "tests.fixtures.sample_pipeline:SamplePipeline"
    result = runner.invoke(
        app,
        [
            "plan",
            target,
            "--run-one=step",
            "--run-until=step",
        ],
    )
    assert result.exit_code != 0
    output = _plain_output(result)
    assert "only one" in output or "run-until" in output
