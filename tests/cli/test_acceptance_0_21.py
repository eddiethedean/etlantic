"""End-to-end CLI acceptance scenario for 0.21."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_acceptance_chain(tmp_path: Path) -> None:
    """init → doctor → validate → plan → run → report show in separate processes."""
    root = tmp_path / "project"
    root.mkdir()
    env = {
        "NO_COLOR": "1",
        "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
    }

    def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "etlantic.cli", *args],
            cwd=root,
            env={**env, **dict(__import__("os").environ)},
            capture_output=True,
            text=True,
            check=False,
        )

    assert run_cli("init", "--force").returncode == 0
    assert (
        run_cli("doctor", "--profile", "development", "--format", "json").returncode
        == 0
    )
    target = "pipeline.py:SamplePipeline"
    assert run_cli("validate", target, "--profile", "development").returncode == 0
    assert (
        run_cli(
            "plan", target, "--profile", "development", "--format", "json"
        ).returncode
        == 0
    )
    run = run_cli(
        "run", target, "--profile", "development", "--format", "json", "--no-write"
    )
    assert run.returncode == 0, run.stdout + run.stderr
    run_id = json.loads(run.stdout)["run_id"]
    show = run_cli("report", "show", run_id, "--format", "json")
    assert show.returncode == 0, show.stdout + show.stderr
    assert json.loads(show.stdout)["run_id"] == run_id
