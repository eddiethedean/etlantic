"""Bounded, redacted, provenance-linked context bundles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from etlantic.agents.diagnostics import ctx_diagnostic
from etlantic.authoring.lifecycle import inspect_pipeline_like, validate_pipeline_like
from etlantic.authoring.preview import plan_preview
from etlantic.diagnostics import Diagnostic
from etlantic.runtime.logging import redact_value

CONTEXT_BUNDLE_SCHEMA = "etlantic.context_bundle/1"

_LEAK_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "credential",
        "payload",
        "source_row",
        "subject_value",
        "api_key",
    }
)
_LEAK_EXACT_KEYS = frozenset({"rows", "records", "subjects", "source_rows"})

DEFAULT_BUDGETS = {
    "max_bytes": 262144,
    "max_nodes": 256,
    "max_diagnostics": 200,
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _is_leak_key(key: str) -> bool:
    lowered = str(key).lower()
    if lowered in _LEAK_EXACT_KEYS:
        return True
    return any(token in lowered for token in _LEAK_KEYS)


def _redact_mapping(value: Any, *, diagnostics: list[Diagnostic]) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _is_leak_key(str(key)):
                diagnostics.append(
                    ctx_diagnostic(
                        "redaction",
                        f"Redacted untrusted key {key!r} from context bundle.",
                        severity="warning",
                        path=("bundle", str(key)),
                    )
                )
                out[str(key)] = "[redacted]"
                continue
            out[str(key)] = _redact_mapping(item, diagnostics=diagnostics)
        return out
    if isinstance(value, list):
        return [_redact_mapping(item, diagnostics=diagnostics) for item in value]
    if isinstance(value, str):
        return str(redact_value(value))
    return value


def _strip_hostile(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _strip_hostile(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_hostile(item) for item in value]
    if isinstance(value, str) and _contains_instruction_injection(value):
        return "[omitted-hostile-text]"
    return value


def _has_unredacted_leak(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _is_leak_key(str(key)) and item != "[redacted]":
                return True
            if _has_unredacted_leak(item):
                return True
        return False
    if isinstance(value, list):
        return any(_has_unredacted_leak(item) for item in value)
    return False


def _contains_instruction_injection(text: str) -> bool:
    lowered = text.lower()
    needles = (
        "ignore previous instructions",
        "grant additional tools",
        "resolve secrets",
        "submit a run",
        "install plugins",
    )
    return any(needle in lowered for needle in needles)


@dataclass
class ContextBundle:
    """Machine-readable inspection bundle. Never authoritative."""

    schema: str = CONTEXT_BUNDLE_SCHEMA
    pipeline_id: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    freshness: str = field(default_factory=_now)
    redacted: bool = True
    graph: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    budgets: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_BUDGETS))
    ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "pipeline_id": self.pipeline_id,
            "sources": list(self.sources),
            "freshness": self.freshness,
            "redacted": self.redacted,
            "graph": self.graph,
            "plan": self.plan,
            "diagnostics": list(self.diagnostics),
            "budgets": dict(self.budgets),
            "ok": self.ok,
        }


def assemble_context_bundle(
    pipeline: Any,
    *,
    profile: str | Any | None = "development",
    budgets: Mapping[str, int] | None = None,
) -> ContextBundle:
    """Assemble a bounded bundle from inspect/validate/plan. No execution."""
    limits = dict(DEFAULT_BUDGETS)
    limits.update(dict(budgets or {}))
    findings: list[Diagnostic] = []
    graph_payload: dict[str, Any] | None = None
    plan_payload: dict[str, Any] | None = None
    pipeline_id: str | None = None
    sources: list[dict[str, Any]] = []

    graph = inspect_pipeline_like(pipeline)
    pipeline_id = graph.pipeline_id
    nodes = [
        {
            "name": n.name,
            "kind": n.kind.value,
            "binding": n.binding,
        }
        for n in graph.nodes
    ]
    if len(nodes) > int(limits["max_nodes"]):
        findings.append(
            ctx_diagnostic(
                "budget",
                "Context bundle exceeded the node budget.",
                path=("graph", "nodes"),
                metadata={"max_nodes": limits["max_nodes"], "count": len(nodes)},
            )
        )
        nodes = nodes[: int(limits["max_nodes"])]
    graph_payload = {
        "pipeline_id": graph.pipeline_id,
        "nodes": nodes,
        "edges": [
            {
                "from": f"{e.producer_node}.{e.producer_port}",
                "to": f"{e.consumer_node}.{e.consumer_port}",
            }
            for e in graph.edges
        ],
    }
    sources.append({"kind": "inspect", "identity": str(pipeline_id or "graph")})

    report = validate_pipeline_like(pipeline, profile=profile)
    sources.append(
        {
            "kind": "validate",
            "identity": str(pipeline_id or "validate"),
        }
    )
    findings.extend(list(report.diagnostics)[: int(limits["max_diagnostics"])])

    try:
        from etlantic.authoring.definition import PipelineDefinition
        from etlantic.authoring.normalize import definition_from_pipeline
        from etlantic.authoring.types import is_pipeline_class

        if isinstance(pipeline, PipelineDefinition):
            defn = pipeline
        elif is_pipeline_class(pipeline):
            defn = definition_from_pipeline(pipeline)
        else:
            defn = None
        if defn is not None:
            planned, plan_report = plan_preview(defn, profile=profile)
            findings.extend(
                list(plan_report.diagnostics)[: int(limits["max_diagnostics"])]
            )
            if planned is not None:
                plan_payload = planned.to_dict()
                if not planned.fingerprint:
                    findings.append(
                        ctx_diagnostic(
                            "missing_provenance",
                            "Plan preview produced no fingerprint.",
                            path=("plan", "fingerprint"),
                        )
                    )
                sources.append(
                    {
                        "kind": "plan",
                        "identity": planned.pipeline_id,
                        "fingerprint": planned.fingerprint,
                    }
                )
    except Exception as exc:  # pragma: no cover - defensive
        findings.append(
            ctx_diagnostic(
                "stale",
                f"Plan preview unavailable: {exc}",
                severity="warning",
            )
        )

    dumped = json.dumps(
        {"graph": graph_payload, "plan": plan_payload},
        default=str,
        sort_keys=True,
    )
    if _contains_instruction_injection(dumped):
        findings.append(
            ctx_diagnostic(
                "hostile",
                "Untrusted project text attempted to grant tools or secrets.",
                path=("bundle",),
            )
        )
        graph_payload = _strip_hostile(graph_payload)
        plan_payload = _strip_hostile(plan_payload)
    if len(dumped.encode("utf-8")) > int(limits["max_bytes"]):
        findings.append(
            ctx_diagnostic(
                "budget",
                "Context bundle exceeded the byte budget.",
                metadata={"max_bytes": limits["max_bytes"]},
            )
        )
        plan_payload = None
        shrunk = json.dumps(
            {"graph": graph_payload, "plan": None},
            default=str,
            sort_keys=True,
        )
        if len(shrunk.encode("utf-8")) > int(limits["max_bytes"]):
            graph_payload = {
                "pipeline_id": pipeline_id,
                "nodes": [],
                "edges": [],
            }

    redacted_graph = _redact_mapping(graph_payload, diagnostics=findings)
    redacted_plan = _redact_mapping(plan_payload, diagnostics=findings)
    if _has_unredacted_leak(redacted_graph) or _has_unredacted_leak(redacted_plan):
        findings.append(
            ctx_diagnostic(
                "leakage",
                "Context bundle still contained secret, row, or payload material.",
                path=("bundle",),
            )
        )
        redacted_graph = _redact_mapping(redacted_graph, diagnostics=findings)
        redacted_plan = _redact_mapping(redacted_plan, diagnostics=findings)
    ok = not any(d.severity.value == "error" for d in findings)
    return ContextBundle(
        pipeline_id=pipeline_id,
        sources=sources,
        redacted=True,
        graph=redacted_graph if isinstance(redacted_graph, dict) else None,
        plan=redacted_plan if isinstance(redacted_plan, dict) else None,
        diagnostics=[d.to_dict() for d in findings],
        budgets=limits,
        ok=ok,
    )
