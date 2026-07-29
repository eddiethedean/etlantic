"""Shared CLI exit-code selection for trust-phase validation failures."""

from __future__ import annotations

from etlantic.cli import exit_codes as ec
from etlantic.diagnostics import Severity, ValidationReport
from etlantic.plugin_trust import is_non_blocking_trust_diagnostic

_TRUST_PHASES = frozenset(
    {
        "plugin_trust",
        "plugin_discovery",
        "plugin_discover",
        "plugin_authorize",
        "plugin_evaluate",
        "plugin_load",
        "plugin_probe",
    }
)

__all__ = [
    "is_non_blocking_trust_diagnostic",
    "trust_exit_from_report",
    "validation_exit_from_report",
]


def trust_exit_from_report(report: ValidationReport) -> int | None:
    """Return TRUST_FAILURE when the report contains blocking trust-phase errors.

    Sibling discovery allowlist denials (``PMPLUG402`` with discovery phase) are
    ignored so CLI exit codes stay aligned with ``ensure_plugins``. Selected-engine
    ``PMPLUG402`` from ``plugin_trust`` maps to TRUST_FAILURE.
    """
    if report.valid:
        return None
    if any(
        d.severity is Severity.ERROR
        and not is_non_blocking_trust_diagnostic(d)
        and (
            (d.phase or "") in _TRUST_PHASES
            or (d.phase or "").startswith("plugin_")
            or (d.code or "").startswith("PMPLUG")
        )
        for d in report.diagnostics
    ):
        return ec.TRUST_FAILURE
    return None


def validation_exit_from_report(report: ValidationReport) -> int:
    """Map a validation report to validate/plan CLI exit codes."""
    blocking = [
        d
        for d in report.diagnostics
        if d.severity is Severity.ERROR and not is_non_blocking_trust_diagnostic(d)
    ]
    if not blocking:
        return ec.SUCCESS
    trust = trust_exit_from_report(report)
    if trust is not None:
        return trust
    return ec.INVALID_MODEL
