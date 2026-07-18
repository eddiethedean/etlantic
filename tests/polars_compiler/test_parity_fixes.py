"""Regression coverage for 0.13 portable parity fixes."""

from __future__ import annotations

import pytest

pytest.importorskip("polars")

import polars as pl

from etlantic.transform.compiler import TransformPlanningContext
from etlantic_polars import create_transform_compiler
from etlantic_polars.lowering.actions import apply_action
from etlantic_polars.lowering.expr import lower_expr


@pytest.mark.polars
def test_union_by_name_reorders_columns() -> None:
    left = pl.DataFrame({"a": [1], "b": [2]})
    right = pl.DataFrame({"b": [3], "a": [4]})
    out = apply_action(
        left,
        {
            "kind": {
                "action": "dtcs:union",
                "parameters": {
                    "other": "right",
                    "mode": "byName",
                    "allowMissingColumns": False,
                },
            }
        },
        parameters={},
        frames={"right": right},
    )
    assert out.columns == ["a", "b"]
    assert out.to_dicts() == [{"a": 1, "b": 2}, {"a": 4, "b": 3}]


@pytest.mark.polars
def test_semi_join_allows_non_key_name_overlap() -> None:
    left = pl.DataFrame({"id": [1, 2], "x": [10, 20]})
    right = pl.DataFrame({"id": [1], "x": [99]})
    out = apply_action(
        left,
        {
            "kind": {
                "action": "dtcs:join",
                "parameters": {
                    "type": "semi",
                    "right": "right",
                    "leftKey": "id",
                    "rightKey": "id",
                    "collisionPolicy": "fail",
                },
            }
        },
        parameters={},
        frames={"right": right},
    )
    assert out.to_dicts() == [{"id": 1, "x": 10}]


@pytest.mark.polars
def test_analyze_rejects_suffix_collision_and_windows() -> None:
    compiler = create_transform_compiler()
    ctx = TransformPlanningContext(
        pipeline_id="p",
        step_name="s",
        profile_name="t",
        engine="polars",
    )
    join_plan = {
        "planIdentity": "dtcs.transform-plan/2",
        "actions": [
            {
                "id": "j1",
                "kind": {
                    "action": "dtcs:join",
                    "id": "j1",
                    "parameters": {
                        "type": "inner",
                        "right": "r",
                        "leftKey": "id",
                        "rightKey": "id",
                        "collisionPolicy": "suffix",
                    },
                    "target": "l",
                },
            }
        ],
    }
    join_report = compiler.analyze(
        join_plan,
        context=ctx,
        requirements={
            "profiles": ["dtcs:profile/portable-relational/1"],
            "actions": ["dtcs:join"],
            "functions": [],
        },
    )
    assert join_report.supported is False
    assert any("collisionPolicy" in f.requirement for f in join_report.findings)

    window_plan = {
        "planIdentity": "dtcs.transform-plan/2",
        "actions": [
            {
                "id": "w1",
                "kind": {
                    "action": "dtcs:with_fields",
                    "id": "w1",
                    "parameters": {
                        "assignments": [
                            {
                                "name": "rn",
                                "expression": {
                                    "kind": "literal",
                                    "value": {"type": "integer", "value": 1},
                                },
                                "window": {"partitionBy": ["id"]},
                            }
                        ]
                    },
                    "target": "l",
                },
            }
        ],
    }
    window_report = compiler.analyze(
        window_plan,
        context=ctx,
        requirements={
            "profiles": ["dtcs:profile/portable-relational-kernel/1"],
            "actions": ["dtcs:with_fields"],
            "functions": [],
        },
    )
    assert window_report.supported is False
    assert any("window" in f.requirement for f in window_report.findings)


@pytest.mark.polars
def test_replace_is_literal() -> None:
    expr = lower_expr(
        {
            "kind": "call",
            "callee": "dtcs:replace",
            "args": [
                {"kind": "fieldRef", "scope": "field", "target": "s"},
                {"kind": "literal", "value": {"type": "string", "value": "a.b"}},
                {"kind": "literal", "value": {"type": "string", "value": "X"}},
            ],
        },
        parameters={},
    )
    out = pl.DataFrame({"s": ["a.b", "ab"]}).select(expr.alias("o"))
    assert out.to_dicts() == [{"o": "X"}, {"o": "ab"}]
