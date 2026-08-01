"""Unified CLI output helpers."""

from __future__ import annotations

import json
from typing import Any

import typer

from etlantic.diagnostics import Diagnostic, ValidationReport


def emit_payload(data: Any, *, fmt: str, quiet: bool = False) -> None:
    """Emit structured or human CLI output."""
    from etlantic.runtime.logging import redact_value

    if quiet and fmt == "human":
        return
    safe = redact_value(data)
    if fmt == "sarif" and isinstance(safe, dict) and "runs" in safe:
        typer.echo(json.dumps(safe, indent=2, sort_keys=True))
        return
    if fmt == "json":
        typer.echo(json.dumps(safe, indent=2, sort_keys=True, default=str))
        return
    if isinstance(safe, dict):
        for key, value in safe.items():
            typer.echo(f"{key}: {value}")
    else:
        typer.echo(str(safe))


def diagnostic_to_dict(d: Diagnostic) -> dict[str, Any]:
    """Serialize a diagnostic for JSON/SARIF parity (secret-safe)."""
    return d.to_dict()


def render_diagnostic_human(d: Diagnostic, *, verbose: bool = False) -> str:
    """Format one diagnostic for human-readable CLI output."""
    from etlantic.runtime.logging import redact_message

    safe = d.to_dict()
    parts = [f"[{safe['severity']}] {safe['code']}: {safe['message']}"]
    if safe.get("phase"):
        parts.append(f"  phase: {safe['phase']}")
    if verbose and safe.get("help"):
        parts.append(f"  help: {safe['help']}")
    source = safe.get("source")
    if verbose and isinstance(source, dict) and source.get("path"):
        loc = source["path"]
        if source.get("line") is not None:
            loc = f"{loc}:{source['line']}"
        parts.append(f"  at: {loc}")
    if verbose and safe.get("actions"):
        for action in safe["actions"]:
            title = redact_message(str(action.get("title") or ""))
            kind = action.get("kind")
            parts.append(f"  action: {title} ({kind})")
    return "\n".join(parts)


def emit_validation_report(
    report: ValidationReport,
    *,
    fmt: str,
    prefix: str = "",
    verbose: bool = False,
    quiet: bool = False,
) -> None:
    """Emit a validation report in human, json, or sarif format."""
    if fmt == "sarif":
        from etlantic.diagnostics.sarif import validation_report_to_sarif

        emit_payload(validation_report_to_sarif(report), fmt="json", quiet=quiet)
        return
    if fmt == "json":
        emit_payload(
            {
                "valid": report.valid,
                "phases": list(report.phases),
                "diagnostics": [diagnostic_to_dict(d) for d in report.diagnostics],
            },
            fmt="json",
            quiet=quiet,
        )
        return
    if quiet:
        return
    status = "valid" if report.valid else "invalid"
    if prefix:
        typer.echo(f"{prefix}: {status}")
    for diagnostic in report.diagnostics:
        typer.echo(render_diagnostic_human(diagnostic, verbose=verbose))


def report_to_payload(report: ValidationReport) -> dict[str, Any]:
    return {
        "valid": report.valid,
        "phases": list(report.phases),
        "diagnostics": [diagnostic_to_dict(d) for d in report.diagnostics],
    }
