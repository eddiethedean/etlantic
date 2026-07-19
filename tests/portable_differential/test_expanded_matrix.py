"""Expanded private differential matrix (nulls, Unicode, ordering, empty)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("polars")
pytest.importorskip("pandas")

import pandas as pd
import polars as pl

from etlantic.testing import normalize_rows
from etlantic.transform.compiler import (
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
)
from etlantic_pandas import create_transform_compiler as pandas_compiler
from etlantic_polars import create_transform_compiler as polars_compiler


def _exec(compiler: Any, plan: dict[str, Any], inputs: dict[str, Any]) -> list[dict]:
    req = {
        "profiles": [
            "dtcs:profile/portable-relational-kernel/1",
            "dtcs:profile/portable-relational/1",
        ],
        "actions": list(
            {(a.get("kind") or {}).get("action") for a in (plan.get("actions") or [])}
        ),
        "functions": [],
    }
    # Collect functions from plan shallowly.
    funcs: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("kind") == "call" and isinstance(node.get("callee"), str):
                funcs.add(node["callee"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(plan)
    req["functions"] = sorted(funcs)
    engine = compiler.info.engine
    assert compiler.analyze(
        plan,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="s",
            profile_name="t",
            engine=engine,
        ),
        requirements=req,
    ).supported
    compiled = compiler.compile(
        plan,
        context=TransformCompileContext(
            pipeline_id="p",
            plan_id="pl",
            step_name="s",
            profile_name="t",
            engine=engine,
        ),
        requirements=req,
    )
    bundle = asyncio.run(
        compiler.execute(
            compiled,
            inputs=inputs,
            parameters={},
            context=TransformExecutionContext(
                run_id="r",
                pipeline_id="p",
                plan_id="pl",
                step_name="s",
                engine=engine,
            ),
        )
    )
    frame = next(iter(bundle.valid.values()))
    if hasattr(frame, "to_dicts"):
        rows = frame.to_dicts()
    else:
        rows = frame.to_dict(orient="records")
    return normalize_rows(rows)


@pytest.mark.polars
@pytest.mark.pandas
def test_differential_unicode_and_ordering() -> None:
    plan = {
        "planIdentity": "dtcs.transform-plan/2",
        "inputs": {"t": {"id": "t"}},
        "actions": [
            {
                "id": "s1",
                "kind": {
                    "action": "dtcs:sort",
                    "id": "s1",
                    "parameters": {
                        "keys": [
                            {"column": "name", "direction": "asc", "nulls": "last"}
                        ]
                    },
                    "target": "t",
                },
            }
        ],
        "outputs": {"result": {"id": "result"}},
        "requirements": {
            "dependencies": [{"from": "s1", "to": "result", "reason": "lineage"}]
        },
    }
    rows = [
        {"name": "café", "n": 2},
        {"name": "Cafe", "n": 1},
        {"name": None, "n": 3},
        {"name": "🍎", "n": 4},
    ]
    polars_out = _exec(polars_compiler(), plan, {"t": pl.DataFrame(rows)})
    pandas_out = _exec(pandas_compiler(), plan, {"t": pd.DataFrame(rows)})
    assert polars_out == pandas_out


@pytest.mark.polars
@pytest.mark.pandas
def test_differential_unequal_key_join() -> None:
    plan = {
        "planIdentity": "dtcs.transform-plan/2",
        "inputs": {"left": {"id": "left"}, "right": {"id": "right"}},
        "actions": [
            {
                "id": "j1",
                "kind": {
                    "action": "dtcs:join",
                    "id": "j1",
                    "parameters": {
                        "type": "inner",
                        "right": "right",
                        "leftKey": "aid",
                        "rightKey": "bid",
                        "collisionPolicy": "fail",
                    },
                    "target": "left",
                },
            }
        ],
        "outputs": {"result": {"id": "result"}},
        "requirements": {
            "dependencies": [{"from": "j1", "to": "result", "reason": "lineage"}]
        },
    }
    left = [{"aid": 1, "v": 10}]
    right = [{"bid": 1, "w": 100}]
    polars_out = _exec(
        polars_compiler(),
        plan,
        {"left": pl.DataFrame(left), "right": pl.DataFrame(right)},
    )
    pandas_out = _exec(
        pandas_compiler(),
        plan,
        {"left": pd.DataFrame(left), "right": pd.DataFrame(right)},
    )
    assert polars_out == pandas_out == [{"aid": 1, "v": 10, "w": 100}]
