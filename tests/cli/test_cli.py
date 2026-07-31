"""CLI smoke and workflow tests."""

from __future__ import annotations

import json
import re
from importlib.metadata import version
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from etlantic.cli import _build_selection, app

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
_TARGET = "tests.fixtures.sample_pipeline:SamplePipeline"


def _plain_output(result: object) -> str:
    stderr = getattr(result, "stderr", "") or ""
    stdout = getattr(result, "stdout", "") or ""
    return _ANSI_ESCAPE.sub("", stderr + stdout).lower()


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert version("etlantic") in result.stdout


def test_cli_validate_sarif() -> None:
    result = runner.invoke(
        app, ["validate", _TARGET, "--profile", "local", "--format", "sarif"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["version"] == "2.1.0"
    assert "$schema" in payload or payload.get("runs")


def test_cli_plugin_list() -> None:
    result = runner.invoke(app, ["plugin", "list", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "plugins" in payload


def test_cli_plugin_list_transform_compiler() -> None:
    result = runner.invoke(
        app, ["plugin", "list", "--kind", "transform_compiler", "--format", "json"]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert "plugins" in payload
    compilers = [p for p in payload["plugins"] if p.get("kind") == "transform_compiler"]
    # Workspace may or may not have optional compilers installed in core CI.
    for item in compilers:
        assert "capabilities" in item
        assert "compiler_protocol" in item


def test_cli_plugin_list_scheduler() -> None:
    result = runner.invoke(
        app, ["plugin", "list", "--kind", "scheduler", "--format", "json"]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    engines = {p.get("engine") for p in payload["plugins"]}
    assert "local" in engines


def test_cli_plugin_info_scheduler_local() -> None:
    result = runner.invoke(
        app,
        ["plugin", "info", "local", "--kind", "scheduler", "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload.get("engine") == "local" or "local" in str(payload).lower()


def test_cli_freshness_fails_closed_without_observed_age() -> None:
    result = runner.invoke(
        app,
        [
            "reliability",
            "freshness",
            "orders",
            "--max-age",
            "60",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 1, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is False


def test_cli_freshness_ok_with_observed_age() -> None:
    result = runner.invoke(
        app,
        [
            "reliability",
            "freshness",
            "orders",
            "--max-age",
            "3600",
            "--observed-age",
            "10",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_cli_partition_check_flags() -> None:
    result = runner.invoke(
        app,
        [
            "reliability",
            "partition-check",
            "orders",
            "--keys",
            "dt,region",
            "--observed",
            "2024-01-01/us,2024-01-01/eu",
            "--minimum-count",
            "2",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["expectation"]["partition_keys"] == ["dt", "region"]
    assert payload["observed_partitions"] == [
        "2024-01-01/eu",
        "2024-01-01/us",
    ]


def test_cli_partition_check_requires_observed() -> None:
    result = runner.invoke(
        app,
        [
            "reliability",
            "partition-check",
            "orders",
            "--keys",
            "dt",
            "--observed",
            "",
            "--format",
            "json",
        ],
    )
    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False


def test_cli_diff_load_failure_is_explicit() -> None:
    from etlantic.cli import exit_codes as ec

    result = runner.invoke(
        app,
        [
            "diff",
            "tests.fixtures.sample_pipeline:MissingPipeline",
            _TARGET,
            "--kind",
            "pipeline",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == ec.INVALID_MODEL
    payload = json.loads(result.stdout)
    assert payload.get("ok") is False
    assert "previous" in str(payload.get("error", "")).lower()


def test_cli_generate(tmp_path: Path) -> None:
    out = tmp_path / "contracts"
    result = runner.invoke(
        app,
        ["generate", _TARGET, "--output", str(out), "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload.get("ok") is True
    assert out.exists()


@pytest.mark.sqlmodel
def test_cli_generate_sqlmodel_writes_source(tmp_path: Path) -> None:
    pytest.importorskip("sqlmodel")
    pytest.importorskip("etlantic_sqlmodel")
    out = tmp_path / "contracts"
    result = runner.invoke(
        app,
        [
            "generate",
            _TARGET,
            "--output",
            str(out),
            "--sqlmodel",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload.get("ok") is True
    sqlmodel_paths = payload.get("sqlmodel") or {}
    assert sqlmodel_paths
    for path_str in sqlmodel_paths.values():
        text = Path(path_str).read_text(encoding="utf-8")
        assert "class " in text
        assert "SQLModel" in text
        assert not text.strip().startswith("# Generated SQLModel")


def test_cli_viz_lineage() -> None:
    result = runner.invoke(app, ["viz", "lineage", _TARGET, "--format", "json"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "etlantic.lineage/1" in result.stdout


def test_cli_validate_and_plan() -> None:
    result = runner.invoke(app, ["validate", _TARGET, "--profile", "local"])
    assert result.exit_code == 0
    result = runner.invoke(
        app, ["plan", _TARGET, "--profile", "local", "--format", "json"]
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "fingerprint" in payload
    assert "plan_id" in payload
    assert "logical_graph" in payload


def test_cli_plan_explain() -> None:
    result = runner.invoke(
        app, ["plan", "explain", _TARGET, "--profile", "local", "--format", "json"]
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "fingerprint" in payload
    assert "steps" in payload


def test_cli_run_json() -> None:
    result = runner.invoke(
        app,
        [
            "run",
            _TARGET,
            "--profile",
            "development",
            "--format",
            "json",
            "--no-write",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "succeeded"


def test_cli_diff_emits_structured_report() -> None:
    result = runner.invoke(
        app,
        ["diff", _TARGET, _TARGET, "--kind", "pipeline", "--format", "json"],
    )
    # Same pipeline may still emit compatibility diagnostics depending on DPCS
    # normalization; the CLI must always return a structured report payload.
    assert result.stdout.strip(), result.stderr
    payload = json.loads(result.stdout)
    assert "valid" in payload
    assert "diagnostics" in payload
    assert isinstance(payload["diagnostics"], list)


def test_cli_inspect() -> None:
    result = runner.invoke(app, ["inspect", _TARGET, "--format", "json"])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert "nodes" in payload or "pipeline" in str(payload).lower()


def test_build_selection_rejects_conflicting_flags() -> None:
    with pytest.raises(typer.BadParameter, match="only one"):
        _build_selection(run_one="step", run_until="step", nodes=None)


def test_cli_conflicting_selection_flags() -> None:
    result = runner.invoke(
        app,
        [
            "plan",
            _TARGET,
            "--run-one=step",
            "--run-until=step",
        ],
    )
    assert result.exit_code != 0
    output = _plain_output(result)
    assert "only one" in output
