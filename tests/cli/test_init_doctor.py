"""Init and doctor CLI tests."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from etlantic.cli import app

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})


def test_init_scaffold(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--directory", str(tmp_path), "--with-toml"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert (tmp_path / "pipeline.py").is_file()
    assert (tmp_path / "profiles" / "development.json").is_file()
    assert (tmp_path / "data" / "sample.json").is_file()
    assert (tmp_path / "etlantic.toml").is_file()
    assert (tmp_path / ".etlantic" / "reports").is_dir()


def test_doctor_after_init(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init = runner.invoke(app, ["init", "--directory", ".", "--force"])
    assert init.exit_code == 0
    doctor = runner.invoke(
        app,
        [
            "doctor",
            "pipeline.py:SamplePipeline",
            "--profile",
            "development",
            "--format",
            "json",
        ],
    )
    assert doctor.exit_code == 0, doctor.stdout + doctor.stderr
    payload = json.loads(doctor.stdout)
    assert payload["ok"] is True
    assert any(c["name"] == "python_version" for c in payload["checks"])
