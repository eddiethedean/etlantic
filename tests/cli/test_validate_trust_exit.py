"""validate maps trust-phase errors to TRUST_FAILURE exit code."""

from __future__ import annotations

from etlantic.cli import exit_codes as ec
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport


def _trust_exit(report: ValidationReport) -> int:
    """Mirror validate_cmd exit selection (keep in sync with cmds/core.py)."""
    if report.valid:
        return ec.SUCCESS
    trust_phases = {"plugin_trust", "plugin_discovery", "plugin_discover"}
    if any(
        d.severity is Severity.ERROR
        and ((d.phase or "") in trust_phases or (d.code or "").startswith("PMPLUG"))
        for d in report.diagnostics
    ):
        return ec.TRUST_FAILURE
    return ec.INVALID_MODEL


def test_validate_exit_trust_failure_for_pmplug() -> None:
    report = ValidationReport(
        diagnostics=(
            Diagnostic(
                code="PMPLUG401",
                severity=Severity.ERROR,
                message="empty allowlist",
                phase="plugin_trust",
            ),
        )
    )
    assert report.valid is False
    assert _trust_exit(report) == ec.TRUST_FAILURE


def test_validate_exit_invalid_model_for_structural() -> None:
    report = ValidationReport(
        diagnostics=(
            Diagnostic(
                code="PMPIPE201",
                severity=Severity.ERROR,
                message="bad wiring",
                phase="structural",
            ),
        )
    )
    assert _trust_exit(report) == ec.INVALID_MODEL
