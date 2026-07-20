"""SARIF 2.1.0 diagnostic rendering for CI."""

from __future__ import annotations

from typing import Any

from etlantic.diagnostics import Diagnostic, Severity, ValidationReport

_SARIF_LEVEL = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "note",
    Severity.HINT: "note",
}


def diagnostics_to_sarif(
    diagnostics: list[Diagnostic] | tuple[Diagnostic, ...],
    *,
    tool_name: str = "etlantic",
    tool_version: str | None = None,
) -> dict[str, Any]:
    """Convert ETLantic diagnostics into a SARIF 2.1.0 log object."""
    from etlantic import __version__

    version = tool_version or __version__
    results: list[dict[str, Any]] = []
    for diagnostic in diagnostics:
        path = "/".join(str(p) for p in diagnostic.path if p is not None)
        result: dict[str, Any] = {
            "ruleId": diagnostic.code,
            "level": _SARIF_LEVEL.get(diagnostic.severity, "note"),
            "message": {"text": diagnostic.message},
        }
        if path:
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": path or "pipeline"},
                    }
                }
            ]
        properties: dict[str, Any] = {}
        if diagnostic.phase:
            properties["phase"] = diagnostic.phase
        if diagnostic.help:
            properties["help"] = diagnostic.help
        if diagnostic.actions:
            properties["actions"] = [
                {
                    "kind": a.kind,
                    "title": a.title,
                    "edit_suggestion": a.edit_suggestion,
                }
                for a in diagnostic.actions
            ]
        if properties:
            result["properties"] = properties
        results.append(result)
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": tool_name,
                        "informationUri": "https://github.com/eddiethedean/etlantic",
                        "version": version,
                    }
                },
                "results": results,
            }
        ],
    }


def validation_report_to_sarif(report: ValidationReport) -> dict[str, Any]:
    """Render a ValidationReport as SARIF."""
    return diagnostics_to_sarif(report.diagnostics)
