"""Unified CLI output helpers."""

from __future__ import annotations

import json
from typing import Any

import typer

from etlantic.diagnostics import Diagnostic, ValidationReport


def emit_payload(data: Any, *, fmt: str, quiet: bool = False) -> None:
    """Emit structured or human CLI output."""
    if quiet and fmt == "human":
        return
    if fmt == "sarif" and isinstance(data, dict) and "runs" in data:
        typer.echo(json.dumps(data, indent=2, sort_keys=True))
        return
    if fmt == "json":
        typer.echo(json.dumps(data, indent=2, sort_keys=True, default=str))
        return
    if isinstance(data, dict):
        for key, value in data.items():
            typer.echo(f"{key}: {value}")
    else:
        typer.echo(str(data))


def diagnostic_to_dict(d: Diagnostic) -> dict[str, Any]:
    """Serialize a diagnostic for JSON/SARIF parity."""
    payload: dict[str, Any] = {
        "code": d.code,
        "severity": d.severity.value,
        "message": d.message,
        "path": list(d.path),
        "phase": d.phase,
    }
    if d.help:
        payload["help"] = d.help
    if d.related:
        payload["related"] = list(d.related)
    if d.source is not None:
        payload["source"] = {
            "path": d.source.path,
            "line": d.source.line,
            "column": d.source.column,
            "object_ref": d.source.object_ref,
            "symbol": d.source.symbol,
        }
    if d.actions:
        payload["actions"] = [
            {
                "kind": a.kind,
                "title": a.title,
                "edit_suggestion": a.edit_suggestion,
                "arguments": dict(a.arguments or {}),
            }
            for a in d.actions
        ]
    if d.metadata:
        payload["metadata"] = dict(d.metadata)
    return payload


def render_diagnostic_human(d: Diagnostic, *, verbose: bool = False) -> str:
    """Format one diagnostic for human-readable CLI output."""
    parts = [f"[{d.severity.value}] {d.code}: {d.message}"]
    if d.phase:
        parts.append(f"  phase: {d.phase}")
    if verbose and d.help:
        parts.append(f"  help: {d.help}")
    if verbose and d.source is not None and d.source.path:
        loc = d.source.path
        if d.source.line is not None:
            loc = f"{loc}:{d.source.line}"
        parts.append(f"  at: {loc}")
    if verbose and d.actions:
        for action in d.actions:
            parts.append(f"  action: {action.title} ({action.kind})")
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
