"""RunSelection unit tests."""

from __future__ import annotations

from pipelantic import Data, Input, Output, Pipeline, Sink, Source, Transformation
from pipelantic.runtime.request import RunSelection


class Row(Data):
    id: int


class T(Transformation):
    rows: Input[Row]
    result: Output[Row]


class P(Pipeline):
    a: Source[Row] = Source(binding="a")
    b = T.step(rows=a)
    c = T.step(rows=b.result)
    d: Sink[Row] = Sink(input=c.result, binding="d")


def test_selection_forms() -> None:
    graph = P.build_graph()
    assert RunSelection.all().resolve(graph) == ("a", "b", "c", "d")
    assert "b" in RunSelection.only("b").resolve(graph)
    assert RunSelection.until("b").resolve(graph) == ("a", "b")
    assert "c" in RunSelection.from_("b").resolve(graph)
    assert RunSelection.between("b", "c").resolve(graph)
    assert "a" in RunSelection.upstream_of("c").resolve(graph)
    assert "d" in RunSelection.downstream_of("c").resolve(graph)
