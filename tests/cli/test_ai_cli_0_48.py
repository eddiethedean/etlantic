"""CLI tests for context bundle, proposal validate, and generate --kind agents."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from etlantic.cli import app

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})
_TARGET = "tests.fixtures.sample_pipeline:SamplePipeline"


def test_context_bundle_cli() -> None:
    result = runner.invoke(app, ["context", "bundle", _TARGET, "--format", "json"])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "etlantic.context_bundle/1"


def test_proposal_validate_cli(tmp_path: Path) -> None:
    proposal = tmp_path / "proposal.json"
    proposal.write_text(
        json.dumps(
            {
                "schema": "etlantic.proposal/1",
                "task_id": "scaffold_model",
                "files": [{"path": "ok.py", "content": "x = 1\n"}],
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["proposal", "validate", str(proposal), "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["applied"] is False


def test_generate_kind_agents(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["generate", "--kind", "agents", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert (tmp_path / "AGENTS.md").is_file()
    payload = json.loads(result.stdout)
    assert payload["kind"] == "agents"
