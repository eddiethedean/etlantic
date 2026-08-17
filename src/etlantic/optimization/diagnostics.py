"""Stable optimization diagnostic helpers (PMOPT*)."""

from __future__ import annotations

from typing import Any

from etlantic.diagnostics import Diagnostic, Severity

OPT_CODES = {
    "missing_evidence": "PMOPT100",
    "stale_evidence": "PMOPT101",
    "conflicting_evidence": "PMOPT102",
    "missing_proof": "PMOPT110",
    "proof_rejected": "PMOPT111",
    "unknown_rewrite_kind": "PMOPT112",
    "policy_rejected": "PMOPT120",
    "capability_rejected": "PMOPT121",
    "budget_exceeded": "PMOPT130",
    "pass_not_allowlisted": "PMOPT140",
    "pass_prereq_unmet": "PMOPT141",
    "determinism_mismatch": "PMOPT150",
    "shadow_regression": "PMOPT160",
}


def optimization_diagnostic(
    code_key: str,
    message: str,
    *,
    severity: str = "warning",
    path: tuple[str, ...] | list[str] | str | None = None,
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    """Build a Diagnostic with a stable PMOPT code."""
    code = OPT_CODES.get(code_key, "PMOPT999")
    sev = Severity(severity)
    if path is None:
        path_t: tuple[str, ...] = ()
    elif isinstance(path, str):
        path_t = (path,)
    else:
        path_t = tuple(str(p) for p in path)
    return Diagnostic(
        code=code,
        severity=sev,
        message=message,
        path=path_t,
        help=help,
        metadata=dict(metadata or {}),
        phase="optimization",
    )
