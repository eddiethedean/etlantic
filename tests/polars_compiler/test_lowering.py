# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Unit tests for Polars DTCS expression lowering."""

from __future__ import annotations

import pytest

pytest.importorskip("polars")

import polars as pl

from etlantic_polars.lowering.expr import (
    lower_expr,
    unwrap_literal_value,
)


def test_unwrap_typed_integer_literal() -> None:
    assert unwrap_literal_value({"type": "integer", "value": 18}) == 18


def test_unwrap_typed_string_literal() -> None:
    assert unwrap_literal_value({"type": "string", "value": "x"}) == "x"


def test_lower_typed_literal_is_scalar_not_struct() -> None:
    expr = lower_expr(
        {"kind": "literal", "value": {"type": "integer", "value": 18}},
        parameters={},
    )
    out = pl.select(expr.alias("v")).item()
    assert out == 18


def test_concat_ws_uses_string_separator() -> None:
    expr = lower_expr(
        {
            "kind": "call",
            "callee": "dtcs:concat_ws",
            "args": [
                {"kind": "literal", "value": {"type": "string", "value": "-"}},
                {"kind": "fieldRef", "scope": "column", "target": "a"},
                {"kind": "fieldRef", "scope": "column", "target": "b"},
            ],
        },
        parameters={},
    )
    frame = pl.DataFrame({"a": ["x"], "b": ["y"]}).select(expr.alias("c"))
    assert frame["c"][0] == "x-y"


def test_round_uses_int_scale() -> None:
    expr = lower_expr(
        {
            "kind": "call",
            "callee": "dtcs:round",
            "args": [
                {"kind": "fieldRef", "scope": "column", "target": "v"},
                {"kind": "literal", "value": {"type": "integer", "value": 1}},
            ],
        },
        parameters={},
    )
    frame = pl.DataFrame({"v": [1.26]}).select(expr.alias("r"))
    assert frame["r"][0] == pytest.approx(1.3)


def test_case_when_with_typed_literals() -> None:
    expr = lower_expr(
        {
            "kind": "call",
            "callee": "dtcs:case_when",
            "args": [
                {
                    "kind": "binary",
                    "op": "gt",
                    "left": {"kind": "fieldRef", "scope": "column", "target": "age"},
                    "right": {
                        "kind": "literal",
                        "value": {"type": "integer", "value": 18},
                    },
                },
                {"kind": "literal", "value": {"type": "string", "value": "adult"}},
                {"kind": "literal", "value": {"type": "string", "value": "minor"}},
            ],
        },
        parameters={},
    )
    frame = pl.DataFrame({"age": [17, 21]}).select(expr.alias("label"))
    assert frame["label"].to_list() == ["minor", "adult"]


def test_cast_lowers_to_polars() -> None:
    expr = lower_expr(
        {
            "kind": "call",
            "callee": "dtcs:cast",
            "args": [
                {"kind": "fieldRef", "scope": "field", "target": "v"},
                {
                    "kind": "literal",
                    "value": {"type": "string", "value": "integer"},
                },
            ],
        },
        parameters={},
    )
    frame = pl.DataFrame({"v": ["1", "2"]}).select(expr.alias("n"))
    assert frame["n"].to_list() == [1, 2]


def test_authored_ops_lower_to_polars() -> None:
    expr = lower_expr(
        {
            "kind": "binary",
            "op": "not_eq",
            "left": {"kind": "fieldRef", "scope": "column", "target": "a"},
            "right": {"kind": "fieldRef", "scope": "column", "target": "b"},
        },
        parameters={},
    )
    frame = pl.DataFrame({"a": [1, 2], "b": [1, 3]}).select(expr.alias("x"))
    assert frame["x"].to_list() == [False, True]

    unary = lower_expr(
        {
            "kind": "unary",
            "op": "not",
            "expr": {"kind": "fieldRef", "scope": "column", "target": "flag"},
        },
        parameters={},
    )
    frame2 = pl.DataFrame({"flag": [True, False]}).select(unary.alias("n"))
    assert frame2["n"].to_list() == [False, True]
