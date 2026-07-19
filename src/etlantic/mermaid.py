"""Mermaid diagram generation from logical graphs."""

from __future__ import annotations

from etlantic.model import LogicalGraph, NodeKind


def graph_to_mermaid(graph: LogicalGraph) -> str:
    """Render a logical pipeline graph as a Mermaid flowchart.

    Output is deterministic for a given graph.
    """
    lines: list[str] = ["flowchart LR"]
    node_ids: dict[str, str] = {}

    for index, node in enumerate(graph.nodes):
        safe_id = f"n{index}"
        node_ids[node.name] = safe_id
        label = _node_label(node.name, node.kind, node.transformation_name)
        lines.append(f'    {safe_id}["{label}"]')

    for edge in graph.edges:
        src = node_ids.get(edge.producer_node)
        dst = node_ids.get(edge.consumer_node)
        if src is None or dst is None:
            continue
        edge_label = edge.producer_port
        if edge.producer_port != edge.consumer_port:
            edge_label = f"{edge.producer_port}->{edge.consumer_port}"
        lines.append(f"    {src} -- {edge_label} --> {dst}")

    return "\n".join(lines) + "\n"


def _node_label(name: str, kind: NodeKind, transformation_name: str | None) -> str:
    if kind is NodeKind.SOURCE:
        return f"Extract: {name}"
    if kind is NodeKind.SINK:
        return f"Load: {name}"
    if kind is NodeKind.SUBPIPELINE:
        return f"Subpipeline: {name}"
    if transformation_name:
        return f"{name}\\n({transformation_name})"
    return name
