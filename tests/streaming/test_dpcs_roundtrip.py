"""DPCS control-node fragments round-trip."""

from __future__ import annotations

from etlantic.model import LogicalGraph, Node, NodeKind, PortSpec
from etlantic.streaming.dpcs import (
    control_nodes_from_dpcs_steps,
    control_nodes_to_dpcs_steps,
)


def test_control_dpcs_roundtrip() -> None:
    graph = LogicalGraph(
        pipeline_id="p1",
        pipeline_name="P1",
        nodes=(
            Node(
                name="fanout",
                kind=NodeKind.MAP,
                identity="fanout",
                inputs=(
                    PortSpec(
                        name="in",
                        direction="input",
                        contract_type=None,
                        contract_id=None,
                    ),
                ),
                outputs=(
                    PortSpec(
                        name="out",
                        direction="output",
                        contract_type=None,
                        contract_id=None,
                    ),
                ),
                metadata={"etlantic.expansion": {"max_children": 8}},
            ),
            Node(name="src", kind=NodeKind.SOURCE, identity="src"),
        ),
        edges=(),
    )
    steps = control_nodes_to_dpcs_steps(graph)
    assert len(steps) == 1
    assert steps[0]["type"] == "etlantic:map"
    restored = control_nodes_from_dpcs_steps(
        steps, pipeline_id="p1", pipeline_name="P1"
    )
    assert restored.nodes[0].kind is NodeKind.MAP
    assert restored.nodes[0].metadata["etlantic.expansion"]["max_children"] == 8
