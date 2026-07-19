"""Subpipeline embedding tests."""

from etlantic import Extract, Input, Load, Output, Pipeline, Transformation
from tests.conftest import Customer, RawCustomer


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


class CustomerCurationPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="raw.customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="curated.customers")


class ScoreCustomers(Transformation):
    customers: Input[Customer]
    result: Output[Customer]


def test_subpipeline_embeds_and_exposes_sink_ports() -> None:
    class AnalyticsPipeline(Pipeline):
        customers_in: Extract[RawCustomer] = Extract(asset="inbound")
        customers = CustomerCurationPipeline.subpipeline(raw=customers_in)
        scored = ScoreCustomers.step(customers=customers.curated)
        out: Load[Customer] = Load(input=scored.result, asset="scored")

    graph = AnalyticsPipeline.inspect()
    assert "customers" in graph.node_names()
    node = graph.node_map()["customers"]
    assert node.kind.value == "subpipeline"
    assert node.nested_graph is not None
    assert "curated" in {p.name for p in node.outputs}

    report = AnalyticsPipeline.validate()
    assert report.valid, list(report.diagnostics)

    # Parent wires into subpipeline public source port named "raw"
    assert any(
        e.consumer_node == "customers" and e.consumer_port == "raw" for e in graph.edges
    )
    # Parent consumes subpipeline public sink port "curated"
    assert any(
        e.producer_node == "customers" and e.producer_port == "curated"
        for e in graph.edges
    )
