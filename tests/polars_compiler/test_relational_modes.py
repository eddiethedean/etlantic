"""Private Polars relational mode-matrix tests (0.13a)."""

from __future__ import annotations

import pytest

pytest.importorskip("polars")

import polars as pl

from etlantic.transform.compiler import TransformPlanningContext
from etlantic_polars import create_transform_compiler
from etlantic_polars.lowering.actions import apply_action


@pytest.mark.polars
@pytest.mark.parametrize(
    "how",
    ["inner", "left", "right", "full", "semi", "anti", "cross"],
)
def test_analyze_accepts_claimed_join_types(how: str) -> None:
    compiler = create_transform_compiler()
    params: dict = {
        "type": how,
        "right": "r",
        "collisionPolicy": "fail",
    }
    if how != "cross":
        params["leftKey"] = "id"
        params["rightKey"] = "id"
    plan = {
        "planIdentity": "dtcs.transform-plan/2",
        "actions": [
            {
                "id": "j1",
                "kind": {
                    "action": "dtcs:join",
                    "id": "j1",
                    "parameters": params,
                    "target": "l",
                },
            }
        ],
    }
    report = compiler.analyze(
        plan,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="s",
            profile_name="t",
            engine="polars",
        ),
        requirements={
            "profiles": ["dtcs:profile/portable-relational/1"],
            "actions": ["dtcs:join"],
            "functions": [],
        },
    )
    assert report.supported is True


@pytest.mark.polars
@pytest.mark.parametrize("mode", ["byName", "byPosition"])
def test_analyze_accepts_union_modes(mode: str) -> None:
    compiler = create_transform_compiler()
    plan = {
        "planIdentity": "dtcs.transform-plan/2",
        "actions": [
            {
                "id": "u1",
                "kind": {
                    "action": "dtcs:union",
                    "id": "u1",
                    "parameters": {
                        "other": "b",
                        "mode": mode,
                        "allowMissingColumns": False,
                    },
                    "target": "a",
                },
            }
        ],
    }
    report = compiler.analyze(
        plan,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="s",
            profile_name="t",
            engine="polars",
        ),
        requirements={
            "profiles": ["dtcs:profile/portable-relational/1"],
            "actions": ["dtcs:union"],
            "functions": [],
        },
    )
    assert report.supported is True


@pytest.mark.polars
def test_join_collision_fail_and_null_safe_execution() -> None:
    left = pl.DataFrame({"id": [1, None], "a": [10, 20]})
    right = pl.DataFrame({"id": [1, None], "b": [100, 200]})
    frames = {"right": right}
    joined = apply_action(
        left,
        {
            "kind": {
                "action": "dtcs:join",
                "parameters": {
                    "type": "inner",
                    "right": "right",
                    "leftKey": "id",
                    "rightKey": "id",
                    "nullSafe": True,
                    "collisionPolicy": "fail",
                },
            }
        },
        parameters={},
        frames=frames,
    )
    assert joined.height == 2

    with pytest.raises(ValueError, match="collision"):
        apply_action(
            pl.DataFrame({"id": [1], "x": [1]}),
            {
                "kind": {
                    "action": "dtcs:join",
                    "parameters": {
                        "type": "inner",
                        "right": "right",
                        "leftKey": "id",
                        "rightKey": "id",
                        "collisionPolicy": "fail",
                    },
                }
            },
            parameters={},
            frames={"right": pl.DataFrame({"id": [1], "x": [2]})},
        )


@pytest.mark.polars
def test_sort_nulls_and_empty_aggregate() -> None:
    frame = pl.DataFrame({"k": ["b", None, "a"], "v": [2, 1, 3]})
    sorted_frame = apply_action(
        frame,
        {
            "kind": {
                "action": "dtcs:sort",
                "parameters": {
                    "keys": [
                        {
                            "expression": {"kind": "fieldRef", "target": "k"},
                            "direction": "asc",
                            "nulls": "last",
                        }
                    ]
                },
            }
        },
        parameters={},
    )
    assert sorted_frame["k"].to_list() == ["a", "b", None]

    empty = pl.DataFrame(
        {
            "region": pl.Series([], dtype=pl.Utf8),
            "amount": pl.Series([], dtype=pl.Float64),
        }
    )
    agg = apply_action(
        empty,
        {
            "kind": {
                "action": "dtcs:aggregate",
                "parameters": {
                    "groupBy": ["region"],
                    "aggregates": [
                        {
                            "name": "total",
                            "expression": {
                                "kind": "call",
                                "callee": "dtcs:sum",
                                "args": [{"kind": "fieldRef", "target": "amount"}],
                            },
                        }
                    ],
                },
            }
        },
        parameters={},
    )
    assert agg.height == 0
