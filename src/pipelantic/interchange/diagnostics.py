"""Map foreign toolkit validation reports into Pipelantic diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pipelantic.diagnostics import (
    Diagnostic,
    Severity,
    SourceLocation,
    ValidationReport,
)

_SEVERITY_MAP = {
    "error": Severity.ERROR,
    "warning": Severity.WARNING,
    "info": Severity.INFO,
    "hint": Severity.HINT,
    "note": Severity.INFO,
}


def _severity(value: Any) -> Severity:
    if isinstance(value, Severity):
        return value
    key = str(value or "error").lower()
    return _SEVERITY_MAP.get(key, Severity.ERROR)


def map_toolkit_diagnostics(
    items: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
    *,
    default_code: str,
    source_path: str | None = None,
    path: tuple[str, ...] = (),
) -> ValidationReport:
    """Convert toolkit diagnostic dicts into a :class:`ValidationReport`."""
    if not items:
        return ValidationReport()
    diagnostics: list[Diagnostic] = []
    for item in items:
        code = str(item.get("id") or item.get("code") or default_code)
        message = str(item.get("message") or "Toolkit validation failed.")
        help_text = item.get("remediation") or item.get("help")
        object_ref = item.get("objectRef") or item.get("object_ref")
        diagnostics.append(
            Diagnostic(
                code=code if ":" in code or code.startswith("PM") else default_code,
                severity=_severity(item.get("severity")),
                message=message,
                path=path + ((str(object_ref),) if object_ref else ()),
                help=str(help_text) if help_text else None,
                source=SourceLocation(
                    path=source_path,
                    object_ref=str(object_ref) if object_ref else None,
                ),
                metadata={
                    "toolkit_code": code,
                    "stage": item.get("stage"),
                    "category": item.get("category"),
                },
            )
        )
    return ValidationReport.from_diagnostics(diagnostics)


def report_has_errors(report: Mapping[str, Any] | ValidationReport) -> bool:
    """Return True when a toolkit or Pipelantic report contains errors."""
    if isinstance(report, ValidationReport):
        return not report.valid
    items = report.get("diagnostics") or []
    return any(str(item.get("severity", "")).lower() == "error" for item in items)
