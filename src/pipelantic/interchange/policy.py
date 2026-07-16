"""Supported contract-format version policy."""

from __future__ import annotations

from dataclasses import dataclass

from pipelantic.diagnostics import Diagnostic, Severity, ValidationReport

SUPPORTED_ODCS_VERSIONS: frozenset[str] = frozenset({"v3.0.0", "3.0.0"})
SUPPORTED_DTCS_VERSIONS: frozenset[str] = frozenset({"1.0.0"})
SUPPORTED_DPCS_VERSIONS: frozenset[str] = frozenset({"1.0.0"})

DEFAULT_ODCS_VERSION = "v3.0.0"
DEFAULT_DTCS_VERSION = "1.0.0"
DEFAULT_DPCS_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class VersionPolicy:
    """Fail-closed supported-version sets for ODCS, DTCS, and DPCS."""

    odcs: frozenset[str] = SUPPORTED_ODCS_VERSIONS
    dtcs: frozenset[str] = SUPPORTED_DTCS_VERSIONS
    dpcs: frozenset[str] = SUPPORTED_DPCS_VERSIONS


DEFAULT_POLICY = VersionPolicy()


def normalize_odcs_version(version: str | None) -> str | None:
    """Normalize ODCS apiVersion strings for policy comparison."""
    if version is None:
        return None
    value = version.strip()
    if not value:
        return None
    if value.startswith("v"):
        return value
    return f"v{value}"


def check_odcs_version(
    version: str | None,
    *,
    path: tuple[str, ...] = (),
    policy: VersionPolicy = DEFAULT_POLICY,
) -> ValidationReport:
    """Return diagnostics when an ODCS apiVersion is missing or unsupported."""
    normalized = normalize_odcs_version(version)
    if normalized is None:
        return ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMDATA201",
                    severity=Severity.ERROR,
                    message="ODCS document is missing apiVersion.",
                    path=path,
                    help="Set apiVersion to a supported ODCS version such as v3.0.0.",
                )
            ]
        )
    candidates = {normalized, normalized.lstrip("v"), version or ""}
    if candidates.isdisjoint(policy.odcs) and normalized not in {
        normalize_odcs_version(v) for v in policy.odcs
    }:
        return ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMDATA202",
                    severity=Severity.ERROR,
                    message=f"Unsupported ODCS apiVersion {version!r}.",
                    path=path,
                    help=f"Supported versions: {', '.join(sorted(policy.odcs))}.",
                    metadata={"apiVersion": version},
                )
            ]
        )
    return ValidationReport()


def check_dtcs_version(
    version: str | None,
    *,
    path: tuple[str, ...] = (),
    policy: VersionPolicy = DEFAULT_POLICY,
) -> ValidationReport:
    """Return diagnostics when a DTCS version is missing or unsupported."""
    if not version:
        return ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMGEN201",
                    severity=Severity.ERROR,
                    message="DTCS document is missing dtcsVersion.",
                    path=path,
                    help="Set dtcsVersion to a supported DTCS version such as 1.0.0.",
                )
            ]
        )
    if version not in policy.dtcs:
        return ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMGEN202",
                    severity=Severity.ERROR,
                    message=f"Unsupported DTCS dtcsVersion {version!r}.",
                    path=path,
                    help=f"Supported versions: {', '.join(sorted(policy.dtcs))}.",
                    metadata={"dtcsVersion": version},
                )
            ]
        )
    return ValidationReport()


def check_dpcs_version(
    version: str | None,
    *,
    path: tuple[str, ...] = (),
    policy: VersionPolicy = DEFAULT_POLICY,
) -> ValidationReport:
    """Return diagnostics when a DPCS version is missing or unsupported."""
    if not version:
        return ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMGEN211",
                    severity=Severity.ERROR,
                    message="DPCS document is missing dpcsVersion.",
                    path=path,
                    help="Set dpcsVersion to a supported DPCS version such as 1.0.0.",
                )
            ]
        )
    if version not in policy.dpcs:
        return ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMGEN212",
                    severity=Severity.ERROR,
                    message=f"Unsupported DPCS dpcsVersion {version!r}.",
                    path=path,
                    help=f"Supported versions: {', '.join(sorted(policy.dpcs))}.",
                    metadata={"dpcsVersion": version},
                )
            ]
        )
    return ValidationReport()
