"""Attach expansion identity onto ``etlantic.plan/1`` metadata."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from etlantic.plan.model import PipelinePlan
from etlantic.streaming.control import (
    ChildExpansion,
    ExpansionSpec,
    expand_children,
    is_control_kind,
)

EXPANSION_METADATA_KEY = "etlantic.expansion"
STREAMING_METADATA_KEY = "etlantic.streaming"


def expansion_metadata(
    spec: ExpansionSpec,
    children: Sequence[ChildExpansion],
) -> dict[str, Any]:
    """Namespaced plan metadata (identifiers + bounds, no payloads)."""
    return {
        EXPANSION_METADATA_KEY: {
            "spec": spec.to_dict(),
            "children": [child.to_dict() for child in children],
            "child_ids": [child.identity for child in children],
        }
    }


def graph_required_streaming_extras(graph: Any) -> tuple[str, ...]:
    """Extras an engine/orchestrator must claim for this logical graph."""
    required: list[str] = []
    from etlantic.model import NodeKind

    for node in getattr(graph, "nodes", ()) or ():
        if is_control_kind(node.kind):
            if "control.expansion" not in required:
                required.append("control.expansion")
            if (
                node.kind
                in {
                    NodeKind.CONDITIONAL,
                    NodeKind.FAILURE,
                    NodeKind.COMPENSATION,
                }
                and "control.branch" not in required
            ):
                required.append("control.branch")
        streaming_meta = dict(getattr(node, "metadata", {}) or {}).get(
            "etlantic.streaming"
        )
        if streaming_meta and "stream.event_time" not in required:
            required.append("stream.event_time")
    return tuple(required)


def plan_overlay_from_graph(graph: Any, *, plan_id: str) -> dict[str, Any]:
    """Build ``etlantic.expansion`` plan metadata from declared control nodes."""
    expansions: list[dict[str, Any]] = []
    for node in getattr(graph, "nodes", ()) or ():
        if not is_control_kind(node.kind):
            continue
        spec_raw = dict(dict(node.metadata or {}).get("etlantic.expansion") or {})
        keys = tuple(str(k) for k in (spec_raw.get("keys") or ()))
        spec = ExpansionSpec.from_dict(
            {
                "parent_id": node.identity,
                "collection_identity": spec_raw.get("collection_identity")
                or node.identity,
                "bounds": spec_raw.get("bounds") or {},
                "decision_evidence": spec_raw.get("decision_evidence") or {},
            }
        )
        children = expand_children(
            spec,
            keys,
            plan_id=plan_id,
            input_snapshot_id=str(spec_raw.get("input_snapshot_id") or "declared"),
        )
        expansions.append(expansion_metadata(spec, children)[EXPANSION_METADATA_KEY])
    if not expansions:
        return {}
    payload: Any = expansions[0] if len(expansions) == 1 else expansions
    return {EXPANSION_METADATA_KEY: payload}


def expand_plan_metadata(
    plan: PipelinePlan,
    spec: ExpansionSpec,
    keys: Sequence[str],
    *,
    input_snapshot_id: str,
    depth: int = 1,
) -> dict[str, Any]:
    """Compute expansion children for ``plan`` and return metadata overlay."""
    children = expand_children(
        spec,
        keys,
        plan_id=plan.plan_id,
        input_snapshot_id=input_snapshot_id,
        depth=depth,
    )
    return expansion_metadata(spec, children)
