"""Stable streaming diagnostic helpers (PMDYN*, PMSTR*, PMDLQ*, PMREG*)."""

from __future__ import annotations

from typing import Any

from etlantic.diagnostics import Diagnostic, Severity

DYN_CODES = {
    "unbounded_expansion": "PMDYN100",
    "bound_exhausted": "PMDYN101",
    "nondeterministic_identity": "PMDYN110",
    "python_branch": "PMDYN120",
    "unsupported_control": "PMDYN130",
}

STR_CODES = {
    "unsupported_semantics": "PMSTR100",
    "capability_degrade": "PMSTR110",
    "handoff_gap": "PMSTR200",
    "handoff_overlap": "PMSTR201",
    "silent_offset": "PMSTR210",
    "backpressure": "PMSTR300",
}

DLQ_CODES = {
    "unbounded_retry": "PMDLQ100",
    "silent_offset_advance": "PMDLQ110",
    "payload_leak": "PMDLQ120",
    "unauthorized_payload": "PMDLQ121",
    "missing_authorization": "PMDLQ130",
    "unreconciled": "PMDLQ140",
}

REG_CODES = {
    "incompatible": "PMREG100",
    "ambiguous": "PMREG101",
    "stale_cache": "PMREG102",
    "unavailable": "PMREG110",
    "not_allowlisted": "PMREG140",
    "silent_reinterpret": "PMREG150",
}


def _build(
    codes: dict[str, str],
    fallback: str,
    code_key: str,
    message: str,
    *,
    severity: str,
    path: tuple[str, ...] | list[str] | str | None,
    help: str | None,
    metadata: dict[str, Any] | None,
    phase: str,
) -> Diagnostic:
    code = codes.get(code_key, fallback)
    if path is None:
        path_t: tuple[str, ...] = ()
    elif isinstance(path, str):
        path_t = (path,)
    else:
        path_t = tuple(str(p) for p in path)
    return Diagnostic(
        code=code,
        severity=Severity(severity),
        message=message,
        path=path_t,
        help=help,
        metadata=dict(metadata or {}),
        phase=phase,
    )


def dyn_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    """Build a Diagnostic with a stable PMDYN code."""
    return _build(
        DYN_CODES,
        "PMDYN999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="expansion",
    )


def str_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    """Build a Diagnostic with a stable PMSTR code."""
    return _build(
        STR_CODES,
        "PMSTR999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="streaming",
    )


def dlq_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    """Build a Diagnostic with a stable PMDLQ code."""
    return _build(
        DLQ_CODES,
        "PMDLQ999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="record_error",
    )


def reg_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    """Build a Diagnostic with a stable PMREG code."""
    return _build(
        REG_CODES,
        "PMREG999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="schema_registry",
    )
