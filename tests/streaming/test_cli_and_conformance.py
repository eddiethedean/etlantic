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


def _schema_store(tmp_path: Path, *, fingerprint: str = "abc123") -> Path:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "subjects": {
                    "orders-value": [
                        {
                            "version": 1,
                            "format": "json_schema",
                            "fingerprint": fingerprint,
                            "compatibility": "backward",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def test_cli_schemas_check_requires_store_and_does_not_register(
    tmp_path: Path,
) -> None:
    store = _schema_store(tmp_path, fingerprint="abc123")
    runner = CliRunner()
    missing = runner.invoke(
        app,
        [
            "stream",
            "schemas",
            "check",
            "--subject",
            "orders-value",
            "--fingerprint",
            "abc123",
        ],
    )
    assert missing.exit_code != 0
    ok = runner.invoke(
        app,
        [
            "stream",
            "schemas",
            "check",
            "--store",
            str(store),
            "--subject",
            "orders-value",
            "--fingerprint",
            "abc123",
        ],
    )
    assert ok.exit_code == 0
    payload = json.loads(ok.stdout)
    assert payload["ok"] is True
    incompatible = runner.invoke(
        app,
        [
            "stream",
            "schemas",
            "check",
            "--store",
            str(store),
            "--subject",
            "orders-value",
            "--fingerprint",
            "other-fingerprint",
        ],
    )
    assert incompatible.exit_code == 10
    bad = json.loads(incompatible.stdout)
    assert bad["ok"] is False
    assert bad["diagnostic"] == "PMREG100"
    unknown = runner.invoke(
        app,
        [
            "stream",
            "schemas",
            "check",
            "--store",
            str(store),
            "--subject",
            "missing-subject",
            "--fingerprint",
            "abc123",
        ],
    )
    assert unknown.exit_code == 10
    missing_subject = json.loads(unknown.stdout)
    assert missing_subject["ok"] is False
    assert missing_subject["diagnostic"] == "PMREG110"
