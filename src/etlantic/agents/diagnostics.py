"""Experimental 0.48 AI/context/proposal/MCP diagnostic helpers."""

from __future__ import annotations

from typing import Any

from etlantic.diagnostics import Diagnostic, Severity

CTX_CODES = {
    "budget": "PMCTX100",
    "missing_provenance": "PMCTX110",
    "stale": "PMCTX120",
    "redaction": "PMCTX130",
    "leakage": "PMCTX140",
    "hostile": "PMCTX150",
}

PROP_CODES = {
    "invalid": "PMPROP100",
    "sandbox": "PMPROP110",
    "impact": "PMPROP120",
    "untrusted": "PMPROP130",
    "execution_denied": "PMPROP140",
}

GUIDE_CODES = {
    "conflict": "PMGUIDE100",
    "overwrite": "PMGUIDE110",
    "malformed_region": "PMGUIDE120",
}

MCP_CODES = {
    "method_denied": "PMMCP100",
    "tool_expansion": "PMMCP110",
    "not_allowlisted": "PMMCP140",
    "secret_denied": "PMMCP150",
    "network_denied": "PMMCP160",
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


def ctx_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    return _build(
        CTX_CODES,
        "PMCTX999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="context_bundle",
    )


def prop_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    return _build(
        PROP_CODES,
        "PMPROP999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="proposal_sandbox",
    )


def guide_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    return _build(
        GUIDE_CODES,
        "PMGUIDE999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="agent_guidance",
    )


def mcp_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    return _build(
        MCP_CODES,
        "PMMCP999",
        code_key,
        message,
        severity=severity,
        path=path,
        help=help,
        metadata=metadata,
        phase="mcp_authority",
    )
