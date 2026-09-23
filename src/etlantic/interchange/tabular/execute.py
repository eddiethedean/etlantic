# pyright: reportUnknownArgumentType=false
"""Runtime lookup helpers for planned tabular interchange boundaries."""

from __future__ import annotations

from etlantic.interchange.tabular.descriptor import InterchangeDescriptor
from etlantic.plan.model import PipelinePlan


def boundary_for_input(
    plan: PipelinePlan,
    consumer_node: str,
    input_port: str,
) -> InterchangeDescriptor | None:
    """Return the planned cross-engine descriptor for one consumer input."""
    edges = {
        (edge.producer_node, edge.producer_port)
        for edge in plan.logical_graph.edges
        if edge.consumer_node == consumer_node and edge.consumer_port == input_port
    }
    for boundary in plan.materialization_boundaries:
        if boundary.reason != "cross_engine":
            continue
        metadata = boundary.metadata or {}
        metadata_matches = (
            metadata.get("consumer_node") == consumer_node
            and metadata.get("consumer_port") == input_port
        )
        edge_matches = (boundary.producer_node, boundary.producer_port) in edges
        has_consumer_metadata = (
            "consumer_node" in metadata or "consumer_port" in metadata
        )
        if has_consumer_metadata and not metadata_matches:
            continue
        if not has_consumer_metadata and not edge_matches:
            continue
        raw = metadata.get("interchange")
        if isinstance(raw, InterchangeDescriptor):
            return raw
        if isinstance(raw, dict):
            return InterchangeDescriptor.from_dict(raw)
    return None


__all__ = ["boundary_for_input"]
