"""Stable 0.47 scheduler / federation / resource diagnostic helpers."""

from __future__ import annotations

from typing import Any

from etlantic.diagnostics import Diagnostic, Severity

SVC_CODES = {
    "memory_store": "PMSVC100",
    "missing_durability": "PMSVC101",
    "role_split": "PMSVC110",
    "fastapi_in_worker": "PMSVC120",
}

FIRE_CODES = {
    "unbounded_catch_up": "PMFIRE100",
    "duplicate_firing": "PMFIRE110",
    "invalid_cron": "PMFIRE120",
    "dst_skip": "PMFIRE130",
    "window_closed": "PMFIRE140",
    "payload_leak": "PMFIRE150",
}

FED_CODES = {
    "incompatible": "PMFED100",
    "version_skew": "PMFED101",
    "missing_dyn_caps": "PMFED110",
    "stale_fence": "PMFED120",
    "unknown_commit_retry": "PMFED130",
    "payload_leak": "PMFED140",
}

RES_CODES = {
    "not_allowlisted": "PMRES140",
    "missing_capability": "PMRES100",
    "placement_reject": "PMRES110",
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


def svc_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    return _build(
        SVC_CODES,
        "PMSVC999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="scheduler_service",
    )


def fire_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    return _build(
        FIRE_CODES,
        "PMFIRE999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="schedule_fire",
    )


def fed_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    return _build(
        FED_CODES,
        "PMFED999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="remote_runtime",
    )


def res_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    return _build(
        RES_CODES,
        "PMRES999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="resource_provider",
    )
