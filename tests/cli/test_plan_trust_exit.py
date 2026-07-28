"""plan command maps trust-phase planning errors to TRUST_FAILURE."""

from __future__ import annotations

from etlantic.cli import exit_codes as ec
from etlantic.cli.trust_exit import trust_exit_from_report, validation_exit_from_report
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport


def test_plan_trust_exit_for_pmplug() -> None:
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
    assert trust_exit_from_report(report) == ec.TRUST_FAILURE


def test_plan_trust_exit_none_for_structural_planning_failure() -> None:
    report = ValidationReport(
        diagnostics=(
            Diagnostic(
                code="PMPLAN301",
                severity=Severity.ERROR,
                message="capability missing",
                phase="planning",
            ),
        )
    )
    assert trust_exit_from_report(report) is None
    assert validation_exit_from_report(report) == ec.INVALID_MODEL
