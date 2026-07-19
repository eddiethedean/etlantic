"""Shared graph IR and visualization exporters beyond Mermaid (0.9).

Public helpers:

- ``logical_graph_to_ir`` / ``plan_to_ir`` — build a ``GraphIR``
- ``graph_to_dot`` — Graphviz DOT text
- ``graph_to_html`` — single-page HTML lineage document
- ``lineage_export`` — JSON lineage document (``etlantic.lineage/1``)

CLI: ``etlantic viz dot|html|lineage``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any

from etlantic.mermaid import graph_to_mermaid
from etlantic.model import Edge, LogicalGraph, Node, NodeKind
from etlantic.plan.model import PipelinePlan


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: str
    label: str
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    target: str
    label: str = ""


@dataclass(frozen=True, slots=True)
class GraphIR:
    """Backend-neutral graph intermediate representation."""

    title: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "nodes": [
                {"id": n.id, "label": n.label, "kind": n.kind, "metadata": n.metadata}
                for n in self.nodes
            ],
            "edges": [
                {"source": e.source, "target": e.target, "label": e.label}
                for e in self.edges
            ],
        }


def logical_graph_to_ir(graph: LogicalGraph) -> GraphIR:
    nodes = tuple(
        GraphNode(
            id=node.name,
            label=node.name,
            kind=node.kind.value,
            metadata={
                "binding": node.binding,
                "asset": node.binding,
                "transformation": node.transformation_name,
            },
        )
        for node in graph.nodes
    )
    edges = tuple(
        GraphEdge(
            source=e.producer_node,
            target=e.consumer_node,
            label=f"{e.producer_port}->{e.consumer_port}",
        )
        for e in graph.edges
    )
    return GraphIR(
        title=graph.pipeline_name or graph.pipeline_id,
        nodes=nodes,
        edges=edges,
    )


def plan_to_ir(plan: PipelinePlan) -> GraphIR:
    return logical_graph_to_ir(plan.logical_graph)


def graph_to_dot(ir: GraphIR) -> str:
    """Export Graphviz DOT (no graphviz binary required to generate text)."""
    lines = [f'digraph "{_escape_id(ir.title)}" {{', "  rankdir=LR;"]
    for node in ir.nodes:
        shape = {
            NodeKind.SOURCE.value: "cylinder",
            NodeKind.SINK.value: "folder",
            NodeKind.STEP.value: "box",
        }.get(node.kind, "ellipse")
        lines.append(
            f'  "{_escape_id(node.id)}" '
            f'[label="{_escape_label(node.label)}", shape={shape}];'
        )
    for edge in ir.edges:
        label = f' [label="{_escape_label(edge.label)}"]' if edge.label else ""
        lines.append(
            f'  "{_escape_id(edge.source)}" -> "{_escape_id(edge.target)}"{label};'
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def ir_to_logical_graph(ir: GraphIR) -> LogicalGraph:
    """Rebuild a LogicalGraph suitable for Mermaid rendering."""
    kind_values = {k.value for k in NodeKind}
    nodes = tuple(
        Node(
            name=n.id,
            kind=NodeKind(n.kind) if n.kind in kind_values else NodeKind.STEP,
            identity=f"node:{n.id}",
            binding=n.metadata.get("binding"),
            transformation_name=n.metadata.get("transformation"),
        )
        for n in ir.nodes
    )
    edges = tuple(
        Edge(
            producer_node=e.source,
            producer_port=(e.label.split("->")[0] if "->" in e.label else "out"),
            consumer_node=e.target,
            consumer_port=(e.label.split("->")[1] if "->" in e.label else "in"),
        )
        for e in ir.edges
    )
    return LogicalGraph(
        pipeline_id=ir.title,
        pipeline_name=ir.title,
        nodes=nodes,
        edges=edges,
    )


def graph_to_html(ir: GraphIR, *, include_mermaid: bool = True) -> str:
    """Simple HTML lineage/docs page (stdlib only)."""
    rows = "".join(
        f"<tr><td>{escape(n.kind)}</td><td>{escape(n.id)}</td>"
        f"<td>{escape(n.label)}</td></tr>"
        for n in ir.nodes
    )
    edge_rows = "".join(
        f"<tr><td>{escape(e.source)}</td><td>{escape(e.target)}</td>"
        f"<td>{escape(e.label)}</td></tr>"
        for e in ir.edges
    )
    mermaid_block = ""
    if include_mermaid:
        mermaid = graph_to_mermaid(ir_to_logical_graph(ir))
        mermaid_block = f"<pre class='mermaid'>{escape(mermaid)}</pre>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{escape(ir.title)} lineage</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0; }}
    td, th {{ border: 1px solid #ccc; padding: 0.4rem 0.75rem; text-align: left; }}
    pre {{ background: #f6f8fa; padding: 1rem; overflow: auto; }}
  </style>
</head>
<body>
  <h1>{escape(ir.title)}</h1>
  <h2>Nodes</h2>
  <table><thead><tr><th>Kind</th><th>Id</th><th>Label</th></tr></thead>
  <tbody>{rows}</tbody></table>
  <h2>Edges</h2>
  <table><thead><tr><th>From</th><th>To</th><th>Label</th></tr></thead>
  <tbody>{edge_rows}</tbody></table>
  <h2>Graphviz DOT</h2>
  <pre>{escape(graph_to_dot(ir))}</pre>
  {mermaid_block}
</body>
</html>
"""


def lineage_export(ir: GraphIR) -> dict[str, Any]:
    """JSON lineage document suitable for docs / agents."""
    return {
        "schema": "etlantic.lineage/1",
        "title": ir.title,
        "nodes": [n.id for n in ir.nodes],
        "edges": [
            {"from": e.source, "to": e.target, "label": e.label} for e in ir.edges
        ],
        "graph": ir.to_dict(),
    }


def _escape_id(value: str) -> str:
    return value.replace('"', '\\"')


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
