"""validate maps trust-phase errors to TRUST_FAILURE exit code."""

from __future__ import annotations

from etlantic.cli import exit_codes as ec
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport


def _trust_exit(report: ValidationReport) -> int:
    """Mirror validate_cmd exit selection (keep in sync with cmds/core.py)."""
    if report.valid:
        return ec.SUCCESS
    trust_phases = {
        "plugin_trust",
        "plugin_discovery",
        "plugin_discover",
        "plugin_authorize",
        "plugin_evaluate",
        "plugin_load",
        "plugin_probe",
    }
    if any(
        d.severity is Severity.ERROR
        and (
            (d.phase or "") in trust_phases
            or (d.phase or "").startswith("plugin_")
            or (d.code or "").startswith("PMPLUG")
        )
        for d in report.diagnostics
    ):
        return ec.TRUST_FAILURE
    return ec.INVALID_MODEL


def _run_status_exit(status: str) -> int:
    """Mirror run_cmd status→exit mapping (keep in sync with cmds/core.py)."""
    if status == "succeeded":
        return ec.SUCCESS
    if status == "partial":
        return ec.PARTIAL_RUN
    if status in {"failed", "timed_out", "cancelled"}:
        return ec.EXECUTION_FAILURE
    return ec.PARTIAL_RUN


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


def test_validate_exit_trust_failure_for_authorize_phase_without_pmplug_prefix() -> (
    None
):
    report = ValidationReport(
        diagnostics=(
            Diagnostic(
                code="PMCFG999",
                severity=Severity.ERROR,
                message="authorize-phase trust failure",
                phase="plugin_authorize",
            ),
        )
    )
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


def test_run_exit_maps_timed_out_and_cancelled_to_execution_failure() -> None:
    assert _run_status_exit("succeeded") == ec.SUCCESS
    assert _run_status_exit("partial") == ec.PARTIAL_RUN
    assert _run_status_exit("failed") == ec.EXECUTION_FAILURE
    assert _run_status_exit("timed_out") == ec.EXECUTION_FAILURE
    assert _run_status_exit("cancelled") == ec.EXECUTION_FAILURE
