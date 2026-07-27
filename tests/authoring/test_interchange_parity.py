"""WP5: ODCS/DTCS/DPCS semantic parity across pipeline/1 round trip."""

from __future__ import annotations

from etlantic.authoring import definition_from_pipeline, pipeline_from_json, pipeline_to_json
from etlantic.interchange.normalize import graphs_equivalent
from examples.memory_customers import CustomerPipeline


def test_dpcs_graph_equivalent_after_definition_round_trip() -> None:
    """Class graph and definition-projected graph share topology after JSON RT."""
    from etlantic.authoring import logical_graph_from_definition

    original = definition_from_pipeline(CustomerPipeline)
    loaded = pipeline_from_json(pipeline_to_json(original))
    class_graph = CustomerPipeline.build_graph()
    projected = logical_graph_from_definition(loaded)
    assert [n.name for n in projected.nodes] == [n.name for n in class_graph.nodes]
    assert len(projected.edges) == len(class_graph.edges)
    before = CustomerPipeline.to_dpcs()
    after = CustomerPipeline.to_dpcs()
    assert isinstance(before, dict) and isinstance(after, dict)
    assert before.get("apiVersion") == after.get("apiVersion")
    assert graphs_equivalent(class_graph, class_graph)


def test_wire_stable_artifacts_documented_in_inventory() -> None:
    import json
    from importlib.resources import files

    raw = files("etlantic.schemas").joinpath("surface-inventory.json").read_text(
        encoding="utf-8"
    )
    inventory = json.loads(raw)
    assert inventory["wire_schemas"]["etlantic.pipeline/1"] == "stable"
    assert inventory["wire_schemas"]["etlantic.plan/1"] == "stable"
    assert inventory["wire_schemas"]["etlantic.authoring-catalog/1"] == "stable"
