"""Roadmap 0.1 acceptance scenarios."""

from __future__ import annotations

from etlantic import (
    Extract,
    Input,
    Load,
    Output,
    Parameter,
    Pipeline,
    Transformation,
)
from tests.conftest import Customer, Metrics, Order, RawCustomer, Rejection


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]


class ValidateCustomers(Transformation):
    customers: Input[Customer]
    valid: Output[Customer]
    rejected: Output[Rejection]
    metrics: Output[Metrics]


class EnrichOrders(Transformation):
    orders: Input[Order]
    customers: Input[Customer]
    result: Output[Order]


def test_multi_source_multi_output_without_backend() -> None:
    class MultiPipeline(Pipeline):
        raw_customers: Extract[RawCustomer] = Extract(asset="customers")
        raw_orders: Extract[Order] = Extract(asset="orders")
        normalized = NormalizeCustomers.step(customers=raw_customers)
        validated = ValidateCustomers.step(customers=normalized.result)
        enriched = EnrichOrders.step(
            orders=raw_orders,
            customers=validated.valid,
        )
        good: Load[Customer] = Load(input=validated.valid, asset="good")
        bad: Load[Rejection] = Load(input=validated.rejected, asset="bad")
        stats: Load[Metrics] = Load(input=validated.metrics, asset="stats")
        orders_out: Load[Order] = Load(input=enriched.result, asset="orders_out")

    graph = MultiPipeline.inspect()
    assert graph.node_names() == (
        "raw_customers",
        "raw_orders",
        "normalized",
        "validated",
        "enriched",
        "good",
        "bad",
        "stats",
        "orders_out",
    )
    report = MultiPipeline.validate()
    assert report.valid, list(report.diagnostics)


def test_downstream_references_named_output_port() -> None:
    class Pipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        normalized = NormalizeCustomers.step(customers=raw)
        validated = ValidateCustomers.step(customers=normalized.result)
        out: Load[Customer] = Load(input=validated.valid, asset="out")

    edges = Pipe.inspect().edges
    assert any(
        e.producer_node == "normalized"
        and e.producer_port == "result"
        and e.consumer_node == "validated"
        for e in edges
    )
    assert any(
        e.producer_node == "validated"
        and e.producer_port == "valid"
        and e.consumer_node == "out"
        for e in edges
    )


def test_two_instances_of_same_transformation_are_distinct() -> None:
    class Pipe(Pipeline):
        raw_a: Extract[RawCustomer] = Extract(asset="a")
        raw_b: Extract[RawCustomer] = Extract(asset="b")
        first = NormalizeCustomers.step(customers=raw_a, minimum_age=18)
        second = NormalizeCustomers.step(customers=raw_b, minimum_age=21)
        out_a: Load[Customer] = Load(input=first.result, asset="out_a")
        out_b: Load[Customer] = Load(input=second.result, asset="out_b")

    graph = Pipe.inspect()
    assert graph.node_map()["first"].identity != graph.node_map()["second"].identity
    assert (
        graph.node_map()["first"].transformation_id
        == graph.node_map()["second"].transformation_id
    )
    # Each load wires to the correct step instance
    producers = {
        (e.consumer_node, e.producer_node)
        for e in graph.edges
        if e.consumer_node in {"out_a", "out_b"}
    }
    assert ("out_a", "first") in producers
    assert ("out_b", "second") in producers


def test_incompatible_wiring_names_both_endpoints() -> None:
    class Pipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        # Load expects Customer but receives RawCustomer
        bad: Load[Customer] = Load(input=raw.result, asset="bad")

    report = Pipe.validate()
    assert not report.valid
    errors = report.filter(code="PMPIPE210").diagnostics
    assert len(errors) == 1
    err = errors[0]
    assert "Customer" in err.message
    assert "RawCustomer" in err.message
    assert err.path == ("pipeline", "bad", "input")
    assert err.related == (("pipeline", "raw", "result"),)


def test_inspect_is_deterministic() -> None:
    class Pipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        normalized = NormalizeCustomers.step(customers=raw)
        out: Load[Customer] = Load(input=normalized.result, asset="out")

    g1 = Pipe.inspect()
    g2 = Pipe.inspect()
    assert g1.pipeline_id == g2.pipeline_id
    assert g1.node_names() == g2.node_names()
    assert g1.edges == g2.edges
    assert Pipe.to_mermaid() == Pipe.to_mermaid()
