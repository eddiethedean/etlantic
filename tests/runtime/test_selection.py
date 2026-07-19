"""RunSelection unit tests."""

from __future__ import annotations

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.runtime.request import RunSelection


class Row(Data):
    id: int


class T(Transformation):
    rows: Input[Row]
    result: Output[Row]


class P(Pipeline):
    a: Extract[Row] = Extract(asset="a")
    b = T.step(rows=a)
    c = T.step(rows=b.result)
    d: Load[Row] = Load(input=c.result, asset="d")


def test_selection_forms() -> None:
    graph = P.build_graph()
    assert RunSelection.all().resolve(graph) == ("a", "b", "c", "d")
    assert RunSelection.only("b").resolve(graph) == ("a", "b")
    assert RunSelection.until("b").resolve(graph) == ("a", "b")
    assert RunSelection.from_("b").resolve(graph) == ("a", "b", "c", "d")
    assert RunSelection.between("b", "c").resolve(graph) == ("a", "b", "c")
    assert RunSelection.upstream_of("c").resolve(graph) == ("a", "b", "c")
    assert RunSelection.downstream_of("c").resolve(graph) == ("c", "d")
