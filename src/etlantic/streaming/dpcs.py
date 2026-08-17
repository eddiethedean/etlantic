"""DPCS fragments for explicit control / stream-time nodes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from etlantic.model import LogicalGraph, Node, NodeKind, PortSpec
from etlantic.plan.freeze import mutable_copy
from etlantic.streaming.control import CONTROL_KIND_VALUES, is_control_kind

CONTROL_STEP_PREFIX = "etlantic:"


def control_nodes_to_dpcs_steps(graph: LogicalGraph) -> list[dict[str, Any]]:
    """Serialize map/branch nodes as DPCS step extensions (not Available flattening)."""
    steps: list[dict[str, Any]] = []
    for node in graph.nodes:
        if not is_control_kind(node.kind):
            continue
        steps.append(
            {
                "id": node.name,
                "type": f"{CONTROL_STEP_PREFIX}{node.kind.value}",
                "etlantic:controlKind": node.kind.value,
                "etlantic:identity": node.identity,
                "inputs": [{"id": p.name, "role": p.role} for p in node.inputs],
                "outputs": [{"id": p.name, "role": p.role} for p in node.outputs],
                "metadata": mutable_copy(node.metadata),
            }
        )
    return steps


def control_nodes_from_dpcs_steps(
    steps: list[Mapping[str, Any]],
    *,
    pipeline_id: str,
    pipeline_name: str,
) -> LogicalGraph:
    """Rebuild a LogicalGraph containing only explicit control nodes."""
    nodes: list[Node] = []
    for step in steps:
        kind_raw = str(step.get("etlantic:controlKind") or "")
        type_raw = str(step.get("type") or "")
        if type_raw.startswith(CONTROL_STEP_PREFIX):
            kind_raw = kind_raw or type_raw.removeprefix(CONTROL_STEP_PREFIX)
        if kind_raw not in CONTROL_KIND_VALUES:
            continue
        inputs = tuple(
            PortSpec(
                name=str(p["id"]),
                direction="input",
                contract_type=None,
                contract_id=None,
                role=str(p.get("role") or "valid"),
            )
            for p in (step.get("inputs") or ())
            if isinstance(p, Mapping)
        )
        outputs = tuple(
            PortSpec(
                name=str(p["id"]),
                direction="output",
                contract_type=None,
                contract_id=None,
                role=str(p.get("role") or "valid"),
            )
            for p in (step.get("outputs") or ())
            if isinstance(p, Mapping)
        )
        nodes.append(
            Node(
                name=str(step["id"]),
                kind=NodeKind(kind_raw),
                identity=str(step.get("etlantic:identity") or step["id"]),
                inputs=inputs,
                outputs=outputs,
                metadata=dict(step.get("metadata") or {}),
            )
        )
    return LogicalGraph(
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name,
        nodes=tuple(nodes),
        edges=(),
    )
