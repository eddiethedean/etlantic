"""Private Pandas relational mode-matrix tests (0.14a)."""

from __future__ import annotations

import pytest

pytest.importorskip("pandas")

import pandas as pd

from etlantic.transform.compiler import TransformPlanningContext
from etlantic_pandas import create_transform_compiler
from etlantic_pandas.lowering.actions import apply_action


@pytest.mark.pandas
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
            engine="pandas",
        ),
        requirements={
            "profiles": ["dtcs:profile/portable-relational/1"],
            "actions": ["dtcs:join"],
            "functions": [],
        },
    )
    assert report.supported is True


@pytest.mark.pandas
def test_join_collision_fail_and_null_safe_execution() -> None:
    left = pd.DataFrame({"id": [1, None], "a": [10, 20]})
    right = pd.DataFrame({"id": [1, None], "b": [100, 200]})
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
        frames={"right": right},
    )
    assert len(joined) == 2

    with pytest.raises(ValueError, match="collision"):
        apply_action(
            pd.DataFrame({"id": [1], "x": [1]}),
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
            frames={"right": pd.DataFrame({"id": [1], "x": [2]})},
        )


@pytest.mark.pandas
def test_semi_join_allows_non_key_name_overlap() -> None:
    left = pd.DataFrame({"id": [1, 2], "x": [10, 20]})
    right = pd.DataFrame({"id": [1], "x": [99]})
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
    assert out.to_dict(orient="records") == [{"id": 1, "x": 10}]


@pytest.mark.pandas
def test_union_by_name_reorders_columns() -> None:
    left = pd.DataFrame({"a": [1], "b": [2]})
    right = pd.DataFrame({"b": [3], "a": [4]})
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
    assert list(out.columns) == ["a", "b"]
    assert out.to_dict(orient="records") == [{"a": 1, "b": 2}, {"a": 4, "b": 3}]


@pytest.mark.pandas
def test_analyze_rejects_suffix_collision() -> None:
    compiler = create_transform_compiler()
    report = compiler.analyze(
        {
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
        },
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="s",
            profile_name="t",
            engine="pandas",
        ),
        requirements={
            "profiles": ["dtcs:profile/portable-relational/1"],
            "actions": ["dtcs:join"],
            "functions": [],
        },
    )
    assert report.supported is False
