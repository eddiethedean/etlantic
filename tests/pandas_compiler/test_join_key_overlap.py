"""Regression: unequal-key joins must not drop left data columns."""

from __future__ import annotations

import pytest

pytest.importorskip("pandas")

import pandas as pd

from etlantic_pandas.lowering.actions import apply_action


def _join_action(how: str) -> dict:
    return {
        "kind": {
            "action": "dtcs:join",
            "parameters": {
                "type": how,
                "leftKey": "aid",
                "rightKey": "bid",
                "right": "right",
                "collisionPolicy": "fail",
            },
        }
    }


@pytest.mark.pandas
def test_unequal_key_preserves_left_column_named_like_right_key() -> None:
    left = pd.DataFrame({"aid": [1], "bid": [9], "v": ["L"]})
    right = pd.DataFrame({"bid": [1], "w": ["R"]})
    out = apply_action(
        left,
        _join_action("inner"),
        parameters={},
        frames={"right": right},
    )
    assert "bid" in out.columns
    assert int(out.loc[0, "bid"]) == 9
    assert out.loc[0, "w"] == "R"
    assert "v" in out.columns


@pytest.mark.pandas
def test_semi_anti_with_left_column_named_like_right_key() -> None:
    left = pd.DataFrame({"aid": [1, 2], "bid": [9, 8], "v": ["a", "b"]})
    right = pd.DataFrame({"bid": [1], "w": ["R"]})
    semi = apply_action(
        left,
        _join_action("semi"),
        parameters={},
        frames={"right": right},
    )
    anti = apply_action(
        left,
        _join_action("anti"),
        parameters={},
        frames={"right": right},
    )
    assert list(semi.columns) == ["aid", "bid", "v"]
    assert list(anti.columns) == ["aid", "bid", "v"]
    assert len(semi) == 1
    assert len(anti) == 1
    assert int(semi.iloc[0]["bid"]) == 9


@pytest.mark.pandas
def test_cross_join_with_reserved_name() -> None:
    left = pd.DataFrame({"_etlantic_cross": [7], "a": [1]})
    right = pd.DataFrame({"b": [2]})
    out = apply_action(
        left,
        {
            "kind": {
                "action": "dtcs:join",
                "parameters": {
                    "type": "cross",
                    "right": "right",
                    "collisionPolicy": "fail",
                },
            }
        },
        parameters={},
        frames={"right": right},
    )
    assert "_etlantic_cross" in out.columns
    assert int(out.loc[0, "_etlantic_cross"]) == 7
    assert int(out.loc[0, "b"]) == 2
