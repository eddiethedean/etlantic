"""Graph validation and Mermaid tests."""

from etlantic import Extract, Input, Load, Output, Pipeline, Transformation
from tests.conftest import Customer, RawCustomer


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


class Echo(Transformation):
    customers: Input[Customer]
    result: Output[Customer]


def test_missing_input_diagnostic() -> None:
    class Pipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        # intentionally omit customers binding via a broken step — use empty by hacking
        normalized = NormalizeCustomers.step()  # type: ignore[call-arg]
        out: Load[Customer] = Load(input=normalized.result, asset="out")

    report = Pipe.validate()
    assert not report.valid
    assert "PMTRN101" in report.codes()


def test_cycle_diagnostic() -> None:
    class Pipe(Pipeline):
        raw: Extract[Customer] = Extract(asset="raw")
        a = Echo.step(customers=raw)
        b = Echo.step(customers=a.result)
        # create cycle by wiring a sink-like self reference is hard with authoring API;
        # build a cycle by making b feed a — not expressible cleanly in class body
        # after a is defined. Instead mutate graph validation via crafted class:
        out: Load[Customer] = Load(input=b.result, asset="out")

    # Force a cyclic edge set by validating a synthetic scenario through
    # the public graph and then checking acyclic happy path is valid.
    assert Pipe.validate().valid

    from etlantic.model import Edge, LogicalGraph, Node, NodeKind
    from etlantic.validation import _detect_cycles

    graph = LogicalGraph(
        pipeline_id="test:Cycle",
        pipeline_name="Cycle",
        nodes=(
            Node(name="a", kind=NodeKind.STEP, identity="a"),
            Node(name="b", kind=NodeKind.STEP, identity="b"),
        ),
        edges=(
            Edge("a", "result", "b", "customers"),
            Edge("b", "result", "a", "customers"),
        ),
    )
    diags = _detect_cycles(graph)
    assert any(d.code == "PMPIPE301" for d in diags)


def test_mermaid_contains_nodes_and_edges() -> None:
    class Pipe(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="raw")
        normalized = NormalizeCustomers.step(customers=raw)
        out: Load[Customer] = Load(input=normalized.result, asset="out")

    text = Pipe.to_mermaid()
    assert text.startswith("flowchart LR")
    assert "Extract: raw" in text
    assert "NormalizeCustomers" in text
    assert "Load: out" in text
