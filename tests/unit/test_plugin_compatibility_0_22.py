"""WP5: etlantic plugin compatibility report (fixture manifests + CLI)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from etlantic.capabilities import CAPABILITY_VOCABULARY_VERSION
from etlantic.cli import app
from etlantic.plan.model import PLAN_SCHEMA
from etlantic.plugin_compatibility import (
    COMPAT_CORE_PIN,
    COMPAT_MISSING_FIELDS,
    COMPAT_OK,
    COMPAT_PROTOCOL,
    COMPAT_VOCABULARY,
    evaluate_manifest_text,
)
from etlantic.plugin_manifest import compute_manifest_digest

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})


def _manifest(**overrides: object) -> str:
    payload = {
        "schema": "etlantic.plugin_manifest/1",
        "package": "etlantic-echo",
        "version": "0.33.0",
        "protocol_range": "etlantic.dataframe/1",
        "entries": [
            {
                "group": "etlantic.dataframe_plugins",
                "name": "echo",
                "target": "etlantic_echo:create_plugin",
                "protocol": "etlantic.dataframe/1",
                "engine": "echo",
                "capabilities": ["dataframe", "eager"],
            }
        ],
        "capabilities": ["dataframe"],
        "privileges": [],
        "provenance": {"publisher": "test"},
    }
    payload.update(overrides)
    payload["digest"] = compute_manifest_digest(payload)
    return json.dumps(payload)


def test_compatible_manifest_passes() -> None:
    row = evaluate_manifest_text(
        _manifest(),
        python_requires=">=3.11",
        core_requires="etlantic>=0.39,<0.40",
        allowlist=["etlantic-echo"],
    )
    assert row.ok
    assert row.plan_schema == PLAN_SCHEMA
    assert row.capability_vocabulary == CAPABILITY_VOCABULARY_VERSION
    assert row.allowlist_status == "allowed"
    assert any(f.code == COMPAT_OK and f.ok for f in row.findings)
    assert any(f.code == COMPAT_PROTOCOL and f.ok for f in row.findings)


def test_incompatible_protocol_range_fails() -> None:
    row = evaluate_manifest_text(
        _manifest(protocol_range="etlantic.dataframe/99"),
        python_requires=">=3.11",
    )
    assert not row.ok
    assert any(f.code == COMPAT_PROTOCOL and not f.ok for f in row.findings)


def test_missing_required_fields_fails() -> None:
    from etlantic.plugin_compatibility import evaluate_manifest
    from etlantic.plugin_manifest import PluginManifest

    # Bypass from_dict defaults so we can assert the missing-fields finding.
    bare = PluginManifest(
        schema="etlantic.plugin_manifest/1",
        package="",
        version="",
        protocol_range="",
    )
    row = evaluate_manifest(bare)
    assert not row.ok
    assert any(f.code == COMPAT_MISSING_FIELDS and not f.ok for f in row.findings)


def test_incompatible_vocabulary_fails() -> None:
    from etlantic.plugin_compatibility import evaluate_manifest
    from etlantic.plugin_manifest import parse_plugin_manifest

    manifest, _ = parse_plugin_manifest(_manifest(), verify_digest=False)
    assert manifest is not None
    row = evaluate_manifest(
        manifest,
        advertised_vocabulary="etlantic.capabilities/99",
    )
    assert not row.ok
    assert any(f.code == COMPAT_VOCABULARY and not f.ok for f in row.findings)


def test_core_pin_mismatch_fails() -> None:
    row = evaluate_manifest_text(
        _manifest(),
        core_requires="etlantic>=9.0,<10",
    )
    assert not row.ok
    assert any(f.code == COMPAT_CORE_PIN and not f.ok for f in row.findings)


def test_allowlist_block_fails() -> None:
    row = evaluate_manifest_text(
        _manifest(),
        allowlist=["etlantic-other"],
    )
    assert not row.ok
    assert row.allowlist_status == "blocked"


def test_allowlist_pin_mismatch_fails() -> None:
    row = evaluate_manifest_text(
        _manifest(),
        allowlist={"etlantic-echo": "==0.22.0"},
    )
    assert not row.ok
    assert row.allowlist_status == "blocked"


def test_entry_protocol_mismatch_under_star_fails() -> None:
    row = evaluate_manifest_text(
        _manifest(
            protocol_range="*",
            entries=[
                {
                    "group": "etlantic.dataframe_plugins",
                    "name": "echo",
                    "target": "etlantic_echo:create_plugin",
                    "protocol": "etlantic.dataframe/99",
                    "engine": "echo",
                    "capabilities": ["dataframe"],
                }
            ],
        ),
    )
    assert not row.ok
    assert any(f.code == COMPAT_PROTOCOL and not f.ok for f in row.findings)


def test_cli_compatibility_json_unknown_package() -> None:
    result = runner.invoke(
        app,
        ["plugin", "compatibility", "etlantic-does-not-exist-xyz", "--format", "json"],
    )
    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["plugins"][0]["package"] == "etlantic-does-not-exist-xyz"


def test_cli_compatibility_help() -> None:
    result = runner.invoke(app, ["plugin", "compatibility", "--help"])
    assert result.exit_code == 0
    assert "compatibility" in result.stdout.lower()
