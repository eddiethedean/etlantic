"""Regression tests for 0.1 P0 correctness bugs."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from etlantic import (
    Extract,
    Input,
    Load,
    Output,
    Parameter,
    Pipeline,
    Transformation,
)
from etlantic.model import LogicalGraph, Node, NodeKind
from etlantic.refs import OutputRef
from tests.conftest import Customer, RawCustomer


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


class EchoCustomer(Transformation):
    customers: Input[Customer]
    result: Output[Customer]


def test_ambiguous_output_ref_is_invalid() -> None:
    class Pipe(Pipeline):
        a: Extract[Customer] = Extract(asset="a")
        b: Extract[Customer] = Extract(asset="b")
        echoed = EchoCustomer.step(
            customers=OutputRef(
                node_name="", port_name="result", contract_type=Customer
            )
        )
        out: Load[Customer] = Load(input=echoed.result, asset="out")

    report = Pipe.validate()
    assert not report.valid
    assert "PMPIPE201" in report.codes()


def test_unknown_subpipeline_binding_is_invalid() -> None:
    class Child(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        normalized = NormalizeCustomers.step(customers=raw)
        curated: Load[Customer] = Load(input=normalized.result, asset="curated")

    class Parent(Pipeline):
        src: Extract[RawCustomer] = Extract(asset="src")
        child = Child.subpipeline(typo=src)
        out: Load[Customer] = Load(input=child.curated, asset="out")

    report = Parent.validate()
    assert not report.valid
    assert "PMPIPE201" in report.codes()
    assert any("typo" in d.message for d in report.errors)


def test_invalid_producer_port_is_invalid() -> None:
    class Pipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        out: Load[RawCustomer] = Load(
            input=OutputRef(
                node_name="raw",
                port_name="nope",
                contract_type=RawCustomer,
            ),
            asset="out",
        )

    report = Pipe.validate()
    assert not report.valid
    assert "PMPIPE201" in report.codes()
    assert any("nope" in d.message for d in report.errors)


def test_transformation_inherits_parent_inputs() -> None:
    class BaseNormalize(Transformation):
        customers: Input[RawCustomer]

    class ChildNormalize(BaseNormalize):
        result: Output[Customer]

    assert [p.name for p in ChildNormalize.inputs()] == ["customers"]
    assert [p.name for p in ChildNormalize.outputs()] == ["result"]

    class Pipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        normalized = ChildNormalize.step(customers=raw)
        out: Load[Customer] = Load(input=normalized.result, asset="out")

    assert Pipe.validate().valid


def test_pipeline_inherits_parent_members() -> None:
    class BasePipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        normalized = NormalizeCustomers.step(customers=raw)
        out: Load[Customer] = Load(input=normalized.result, asset="out")

    class ExtPipe(BasePipe):
        extra: Extract[Customer] = Extract(asset="extra")

    names = ExtPipe.inspect().node_names()
    assert "raw" in names
    assert "normalized" in names
    assert "out" in names
    assert "extra" in names
    assert ExtPipe.validate().valid


def test_parameter_with_default_stores_value() -> None:
    class WithDefault(Transformation):
        customers: Input[RawCustomer]
        minimum_age: Parameter[int] = Parameter[int].with_default(18)
        result: Output[Customer]

    params = WithDefault.parameters()
    assert len(params) == 1
    assert params[0].has_default
    assert params[0].default == 18

    step = WithDefault.step(customers="x")
    assert step.parameters["minimum_age"] == 18


def test_cyclic_subpipeline_nesting_is_diagnostic() -> None:
    class Pipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        out: Load[RawCustomer] = Load(input=raw.result, asset="out")

    from etlantic.pipeline import _building_graphs

    Pipe._cached_graph = None
    Pipe._graph_build_error = None
    _building_graphs.add(Pipe)
    try:
        graph = Pipe.build_graph()
    except RecursionError:
        pytest.fail("re-entrant build_graph raised RecursionError")
    finally:
        _building_graphs.discard(Pipe)

    assert graph.metadata.get("cyclic_subpipeline")
    assert Pipe._graph_build_error is not None

    Pipe._cached_graph = None
    report = Pipe.validate()
    # Fresh build succeeds; ensure prior flag is cleared on subclass init only.
    # Re-set error and ensure validate reports it.
    Pipe._graph_build_error = (
        'Cyclic subpipeline nesting detected while building "Pipe".'
    )
    Pipe._cached_graph = graph
    report = Pipe.validate()
    assert not report.valid
    assert "PMPIPE302" in report.codes()


def test_graph_metadata_is_immutable() -> None:
    graph = LogicalGraph(
        pipeline_id="x",
        pipeline_name="X",
        nodes=(Node(name="n", kind=NodeKind.SOURCE, identity="x/n"),),
    )
    assert isinstance(graph.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        graph.metadata["k"] = "v"  # type: ignore[index]
