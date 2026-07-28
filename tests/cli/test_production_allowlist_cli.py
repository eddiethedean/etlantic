"""CLI empty production allowlist emits one PMPLUG401 and exit 11."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from etlantic.cli import app
from etlantic.cli import exit_codes as ec

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})


def test_validate_bare_production_profile_single_pmplug401() -> None:
    result = runner.invoke(
        app,
        [
            "validate",
            "examples/memory_customers.py:CustomerPipeline",
            "--profile",
            "production",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == ec.TRUST_FAILURE, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    diags = payload.get("diagnostics") or []
    error_codes = [
        d.get("code")
        for d in diags
        if isinstance(d, dict) and str(d.get("severity", "")).lower() == "error"
    ]
    assert error_codes.count("PMPLUG401") == 1, error_codes
    assert "plugin_allowlist" in result.stdout
