# pyright: reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownParameterType=false
"""CLI regression tests for 0.21 wiring (workspace, preview, exit codes)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from etlantic.cli import app
from etlantic.cli import exit_codes as ec

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})


def _init_project(tmp_path: Path) -> Path:
    result = runner.invoke(app, ["init", "--directory", str(tmp_path), "--force"])
    assert result.exit_code == 0, result.stdout + result.stderr
    return tmp_path


def test_run_preview_default_text(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_project(tmp_path)
    result = runner.invoke(
        app,
        [
            "run",
            "pipeline.py:SamplePipeline",
            "--profile",
            "development",
            "--preview",
        ],
    )
    assert result.exit_code == ec.SUCCESS, result.stdout + result.stderr
    assert "command: run" in result.stdout
    assert "write_intent:" in result.stdout


def test_workspace_flag_resolves_profiles_off_cwd(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    _init_project(project)
    result = runner.invoke(
        app,
        [
            "--workspace",
            str(project),
            "validate",
            str(project / "pipeline.py") + ":SamplePipeline",
            "--profile",
            "development",
        ],
    )
    assert result.exit_code == ec.SUCCESS, result.stdout + result.stderr


def test_accept_legacy_bindings_cli_validate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_project(tmp_path)
    profile = tmp_path / "profiles" / "development.json"
    data = json.loads(profile.read_text(encoding="utf-8"))
    data.pop("assets", None)
    data["bindings"] = {"customers": "json://data/customers.json", "curated": "memory"}
    profile.write_text(json.dumps(data), encoding="utf-8")

    blocked = runner.invoke(
        app,
        ["validate", "pipeline.py:SamplePipeline", "--profile", "development"],
    )
    assert blocked.exit_code != 0

    allowed = runner.invoke(
        app,
        [
            "--accept-legacy-bindings",
            "validate",
            "pipeline.py:SamplePipeline",
            "--profile",
            "development",
        ],
    )
    assert allowed.exit_code == ec.SUCCESS, allowed.stdout + allowed.stderr


def test_profile_migrate_empty_assets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "name": "legacy",
                "security_mode": "development",
                "assets": {},
                "bindings": {"rows": "memory"},
            }
        ),
        encoding="utf-8",
    )
    dry = runner.invoke(app, ["profile", "migrate", str(path), "--format", "json"])
    assert dry.exit_code == ec.SUCCESS, dry.stdout + dry.stderr
    payload = json.loads(dry.stdout)
    assert payload["profile"]["assets"]["rows"] == "memory"
    assert "bindings" not in payload["profile"]

    written = runner.invoke(
        app,
        ["--non-interactive", "profile", "migrate", str(path), "--write"],
    )
    assert written.exit_code == ec.SUCCESS, written.stdout + written.stderr
    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert migrated["assets"]["rows"] == "memory"
    assert "bindings" not in migrated


def test_ephemeral_report_list(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_project(tmp_path)
    run = runner.invoke(
        app,
        [
            "--ephemeral",
            "run",
            "pipeline.py:SamplePipeline",
            "--profile",
            "development",
            "--format",
            "json",
            "--no-write",
        ],
    )
    assert run.exit_code == ec.SUCCESS, run.stdout + run.stderr
    run_id = json.loads(run.stdout)["run_id"]
    # Ephemeral list uses in-memory store for the same process via CliRunner
    # recreates app each invoke — list from durable store should not see it.
    listed = runner.invoke(app, ["report", "list", "--format", "json"])
    assert listed.exit_code == ec.SUCCESS
    reports = json.loads(listed.stdout)["reports"]
    assert not any(item["run_id"] == run_id for item in reports)


def test_exit_codes_module_values() -> None:
    assert ec.SUCCESS == 0
    assert ec.USAGE_ERROR == 2
    assert ec.INVALID_MODEL == 10
    assert ec.TRUST_FAILURE == 11
    assert ec.PLANNING_FAILURE == 12
    assert ec.EXECUTION_FAILURE == 13
    assert ec.PARTIAL_RUN == 14
    assert ec.BREAKING_CHANGE == 15
    assert ec.ENVIRONMENT_FAILURE == 16
