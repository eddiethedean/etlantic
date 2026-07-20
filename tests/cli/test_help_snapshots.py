"""CLI help snapshot tests."""

from __future__ import annotations

from typer.testing import CliRunner

from etlantic.cli import app

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})

_EXPECTED_COMMANDS = [
    "init",
    "doctor",
    "validate",
    "inspect",
    "plan",
    "run",
    "compile",
    "generate",
    "diff",
    "profile",
    "plugin",
    "schema",
    "reliability",
    "viz",
    "report",
]


def test_root_help_lists_core_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    text = result.stdout.lower()
    for command in _EXPECTED_COMMANDS:
        assert command in text


def test_init_help() -> None:
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "minimal import-safe pipeline" in result.stdout.lower()


def test_doctor_help() -> None:
    result = runner.invoke(app, ["doctor", "--help"])
    assert result.exit_code == 0
    assert "read-only" in result.stdout.lower()
