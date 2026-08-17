"""CLI and conformance tests for 0.46 streaming."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from etlantic.cli import app
from etlantic.testing import (
    run_schema_registry_conformance_suite,
    run_streaming_conformance_suite,
)


def test_streaming_conformance_passes() -> None:
    report = run_streaming_conformance_suite()
    assert report["passed"] is True
    assert report["checks"]["no_payload_in_report"] is True
    assert report["checks"]["dlq_unauthorized"] is True


def test_registry_conformance_passes() -> None:
    report = run_schema_registry_conformance_suite()
    assert report["passed"] is True


def test_cli_dead_letters_inspect_metadata_only(tmp_path: Path) -> None:
    store = tmp_path / "dlq.json"
    store.write_text(
        json.dumps(
            {
                "authorization_identity": "ops",
                "items": [
                    {
                        "identity": "r1",
                        "envelope": {
                            "op": "insert",
                            "source_position": "1",
                            "order_key": "1",
                            "schema_identity": "s",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "stream",
            "dead-letters",
            "inspect",
            "--store",
            str(store),
            "--principal",
            "ops",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["items"][0]["identity"] == "r1"
    assert "payload" not in json.dumps(payload)


def test_cli_payload_store_rejected(tmp_path: Path) -> None:
    store = tmp_path / "dlq.json"
    store.write_text(
        json.dumps(
            {
                "authorization_identity": "ops",
                "items": [{"identity": "r1", "payload": {"ssn": "1"}}],
            }
        ),
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "stream",
            "dead-letters",
            "inspect",
            "--store",
            str(store),
            "--principal",
            "ops",
        ],
    )
    assert result.exit_code != 0
