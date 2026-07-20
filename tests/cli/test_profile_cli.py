"""Profile CLI tests."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from etlantic.cli import app
from etlantic.profile import development_profile, write_profile

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})


def test_profile_validate_show_diff(tmp_path: Path) -> None:
    left = write_profile(
        development_profile(name="left", assets={"rows": "json://data/a.json"}),
        tmp_path / "left.json",
    )
    right = write_profile(
        development_profile(name="right", assets={"rows": "json://data/b.json"}),
        tmp_path / "right.json",
    )
    validate = runner.invoke(
        app, ["profile", "validate", str(left), "--format", "json"]
    )
    assert validate.exit_code == 0, validate.stdout + validate.stderr
    assert json.loads(validate.stdout)["valid"] is True

    show = runner.invoke(app, ["profile", "show", str(left), "--format", "json"])
    assert show.exit_code == 0
    assert json.loads(show.stdout)["name"] == "left"

    diff = runner.invoke(
        app,
        ["profile", "diff", str(left), str(right), "--format", "json"],
    )
    assert diff.exit_code != 0
    payload = json.loads(diff.stdout)
    assert payload["breaking"] is True
    assert "assets" in payload["changed"]
