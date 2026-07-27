"""WP1-WP3 authoring definition, codecs, and functional parity tests."""

from __future__ import annotations

import json

import pytest
from examples.memory_customers import CustomerPipeline
from hypothesis import given, settings
from hypothesis import strategies as st

from etlantic.authoring import (
    PIPELINE_SCHEMA,
    authoring_graph_fingerprint,
    contract_definition,
    definition_from_pipeline,
    edge,
    extract_node,
    field_spec,
    implementation_ref,
    input_port,
    load_node,
    logical_graph_from_definition,
    output_port,
    pipeline_definition,
    pipeline_fingerprint,
    pipeline_from_dict,
    pipeline_from_json,
    pipeline_to_json,
    step_node,
    transformation_definition,
)


def test_definition_from_pipeline_memory_customers() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    assert defn.schema == PIPELINE_SCHEMA
    assert defn.pipeline_name == "CustomerPipeline"
    assert {n.name for n in defn.nodes} == {"raw", "normalized", "curated"}
    assert len(defn.edges) == 2
    assert defn.transformations
    assert defn.contracts


def test_logical_graph_projection_preserves_topology() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    graph = logical_graph_from_definition(defn)
    class_graph = CustomerPipeline.build_graph()
    assert graph.pipeline_id == class_graph.pipeline_id
    assert [n.name for n in graph.nodes] == [n.name for n in class_graph.nodes]
    assert [
        (e.producer_node, e.producer_port, e.consumer_node, e.consumer_port)
        for e in graph.edges
    ] == [
        (e.producer_node, e.producer_port, e.consumer_node, e.consumer_port)
        for e in class_graph.edges
    ]


def test_json_round_trip_byte_stable() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    text1 = pipeline_to_json(defn, indent=None)
    again = pipeline_from_json(text1)
    text2 = pipeline_to_json(again, indent=None)
    assert text1 == text2
    assert pipeline_fingerprint(defn) == pipeline_fingerprint(again)


def test_hostile_secret_payload_rejected() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    data = json.loads(pipeline_to_json(defn))
    data["metadata"] = {"password": "hunter2"}
    with pytest.raises(ValueError, match=r"forbidden|secret"):
        pipeline_from_dict(data)


def test_unknown_schema_rejected() -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    data = json.loads(pipeline_to_json(defn))
    data["schema"] = "etlantic.pipeline/99"
    with pytest.raises(ValueError, match="Unsupported"):
        pipeline_from_dict(data)


def test_functional_builder_parity_with_class() -> None:
    class_defn = definition_from_pipeline(CustomerPipeline)
    # Rebuild a minimal equivalent using functional constructors from class data.
    contracts = class_defn.contracts
    transforms = class_defn.transformations
    nodes = class_defn.nodes
    edges = class_defn.edges
    functional = pipeline_definition(
        class_defn.pipeline_id,
        class_defn.pipeline_name,
        version=class_defn.version,
        contracts=contracts,
        transformations=transforms,
        nodes=nodes,
        edges=edges,
        provenance=dict(class_defn.provenance),
        metadata=dict(class_defn.metadata),
    )
    assert authoring_graph_fingerprint(class_defn) == authoring_graph_fingerprint(
        functional
    )
    assert pipeline_to_json(class_defn, indent=None) == pipeline_to_json(
        functional, indent=None
    )


def test_functional_authoring_from_scratch() -> None:
    raw_id = "demo:RawCustomer"
    cust_id = "demo:Customer"
    xf_id = "demo:Normalize"
    pid = "demo:CustomerPipeline"
    defn = pipeline_definition(
        pid,
        "CustomerPipeline",
        contracts=(
            contract_definition(
                raw_id,
                "RawCustomer",
                fields=(
                    field_spec("customer_id", "integer"),
                    field_spec("first_name", "string"),
                    field_spec("last_name", "string"),
                ),
            ),
            contract_definition(
                cust_id,
                "Customer",
                fields=(
                    field_spec("customer_id", "integer"),
                    field_spec("full_name", "string"),
                ),
            ),
        ),
        transformations=(
            transformation_definition(
                xf_id,
                "NormalizeCustomers",
                ports=(
                    input_port("customers", raw_id),
                    output_port("result", cust_id),
                ),
                implementation_refs=(
                    implementation_ref("local", f"{xf_id}/local"),
                ),
            ),
        ),
        nodes=(
            extract_node("raw", asset="customer_source", contract_id=raw_id, pipeline_id=pid),
            step_node(
                "normalized",
                transformation_id=xf_id,
                transformation_name="NormalizeCustomers",
                pipeline_id=pid,
                inputs=(input_port("customers", raw_id),),
                outputs=(output_port("result", cust_id),),
            ),
            load_node("curated", asset="customer_sink", contract_id=cust_id, pipeline_id=pid),
        ),
        edges=(
            edge("raw", "result", "normalized", "customers", producer_contract_id=raw_id, consumer_contract_id=raw_id),
            edge(
                "normalized",
                "result",
                "curated",
                "input",
                producer_contract_id=cust_id,
                consumer_contract_id=cust_id,
            ),
        ),
    )
    assert defn.fingerprint
    assert len(defn.nodes) == 3


@given(st.sampled_from(["raw", "normalized", "curated"]))
@settings(max_examples=5)
def test_property_round_trip_preserves_nodes(node_name: str) -> None:
    defn = definition_from_pipeline(CustomerPipeline)
    text = pipeline_to_json(defn, indent=None)
    again = pipeline_from_json(text)
    assert node_name in {n.name for n in again.nodes}
