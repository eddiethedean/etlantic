"""Unit tests for diagnostics and reports."""

from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.exceptions import PipelineValidationError


def test_report_valid_when_no_errors() -> None:
    report = ValidationReport(
        diagnostics=(Diagnostic(code="X", severity=Severity.WARNING, message="warn"),)
    )
    assert report.valid
    assert not report.has_errors
    assert len(report.warnings) == 1


def test_raise_for_errors() -> None:
    report = ValidationReport(
        diagnostics=(
            Diagnostic(code="PMPIPE210", severity=Severity.ERROR, message="bad"),
        )
    )
    assert not report.valid
    assert report.has_errors
    try:
        report.raise_for_errors()
    except PipelineValidationError as exc:
        assert exc.report is report
    else:
        raise AssertionError("expected PipelineValidationError")
