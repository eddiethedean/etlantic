"""IDE foundations: editor-neutral protocols, analysis, and trusted policy (0.44)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from etlantic.ide.commands import execute_command
from etlantic.ide.protocol import (
    PROTOCOL_VERSION,
    DiagnosticPayload,
    ExplainPreview,
    GraphPreview,
    IdeCommand,
    IdeResult,
    ImpactPreview,
    LineagePreview,
    LocationLink,
    PlanPreview,
    SemanticDiff,
    SymbolPayload,
)
from etlantic.ide.trust import (
    TrustAuditRecord,
    TrustedWorkspacePolicy,
    deny_untrusted,
)

COMMAND_SCHEMAS: dict[str, dict[str, Any]] = {
    "validate": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "etlantic.validate",
        "type": "object",
        "required": ["target"],
        "properties": {
            "target": {"type": "string"},
            "profile": {"type": "string", "default": "development"},
        },
    },
    "plan": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "etlantic.plan",
        "type": "object",
        "required": ["target"],
        "properties": {
            "target": {"type": "string"},
            "profile": {"type": "string", "default": "development"},
        },
    },
    "explain": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "etlantic.plan.explain",
        "type": "object",
        "required": ["target"],
        "properties": {
            "target": {"type": "string"},
            "profile": {"type": "string", "default": "development"},
        },
    },
    "generate": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "etlantic.generate",
        "type": "object",
        "required": ["target"],
        "properties": {
            "target": {"type": "string"},
            "output": {"type": "string", "default": "contracts"},
            "sqlmodel": {"type": "boolean", "default": False},
        },
    },
    "run_selected": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "etlantic.run_selected",
        "type": "object",
        "required": ["target"],
        "properties": {
            "target": {"type": "string"},
            "profile": {"type": "string", "default": "development"},
            "run_one": {"type": ["string", "null"]},
            "run_until": {"type": ["string", "null"]},
            "nodes": {"type": ["array", "null"], "items": {"type": "string"}},
            "no_write": {"type": "boolean", "default": False},
        },
    },
    "report": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "etlantic.report",
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {"type": "string"},
            "store_dir": {"type": ["string", "null"]},
        },
    },
}

RESULT_SCHEMAS: dict[str, dict[str, Any]] = {
    "validation": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "etlantic.validation_result",
        "type": "object",
        "required": ["valid"],
        "properties": {
            "valid": {"type": "boolean"},
            "phases": {"type": "array", "items": {"type": "string"}},
        },
    },
    "plan": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "etlantic.plan_result",
        "type": "object",
        "required": ["plan_id", "fingerprint"],
        "properties": {
            "plan_id": {"type": "string"},
            "fingerprint": {"type": "string"},
            "profile_name": {"type": "string"},
        },
    },
    "report": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "etlantic.report_result",
        "type": "object",
        "required": ["run_id", "status"],
        "properties": {
            "run_id": {"type": "string"},
            "status": {"type": "string"},
            "pipeline_id": {"type": "string"},
        },
    },
}


def list_commands() -> list[str]:
    return sorted(COMMAND_SCHEMAS)


def get_command_schema(name: str) -> dict[str, Any]:
    if name not in COMMAND_SCHEMAS:
        raise KeyError(f"Unknown IDE command schema: {name}")
    return dict(COMMAND_SCHEMAS[name])


def get_result_schema(name: str) -> dict[str, Any]:
    if name not in RESULT_SCHEMAS:
        raise KeyError(f"Unknown IDE result schema: {name}")
    return dict(RESULT_SCHEMAS[name])


def write_schemas(directory: str | Path) -> dict[str, Path]:
    """Write command/result JSON Schema artifacts for editor consumption."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, schema in COMMAND_SCHEMAS.items():
        path = root / f"command_{name}.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        written[f"command:{name}"] = path
    for name, schema in RESULT_SCHEMAS.items():
        path = root / f"result_{name}.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        written[f"result:{name}"] = path
    return written


class WorkspaceSymbolIndex:
    """Minimal workspace symbol index foundation (compat with 0.9).

    Prefer :class:`etlantic.ide.analysis.WorkspaceIndex` for full analysis.
    """

    def __init__(self) -> None:
        self._symbols: dict[str, dict[str, Any]] = {}

    def index_pipeline(self, name: str, *, module: str, kind: str = "pipeline") -> None:
        self._symbols[name] = {"name": name, "module": module, "kind": kind}

    def search(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        return [s for s in self._symbols.values() if q in s["name"].lower()]

    def to_dict(self) -> dict[str, Any]:
        return {"symbols": list(self._symbols.values())}


__all__ = [
    "COMMAND_SCHEMAS",
    "PROTOCOL_VERSION",
    "RESULT_SCHEMAS",
    "DiagnosticPayload",
    "ExplainPreview",
    "GraphPreview",
    "IdeCommand",
    "IdeResult",
    "ImpactPreview",
    "LineagePreview",
    "LocationLink",
    "PlanPreview",
    "SemanticDiff",
    "SymbolPayload",
    "TrustAuditRecord",
    "TrustedWorkspacePolicy",
    "WorkspaceSymbolIndex",
    "deny_untrusted",
    "execute_command",
    "get_command_schema",
    "get_result_schema",
    "list_commands",
    "write_schemas",
]
