"""Expand private differential coverage (null-safe join)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("polars")
pytest.importorskip("sparkless")

import polars as pl

from etlantic.spark.provider import ResourceContext, SparkSessionRequest
from etlantic.transform.compiler import (
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
)
from etlantic_polars import create_transform_compiler as polars_compiler
from etlantic_pyspark import create_provider
from etlantic_pyspark import create_transform_compiler as spark_compiler


def _normalize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = [{k: r[k] for k in sorted(r)} for r in rows]
    return sorted(cleaned, key=lambda r: tuple(str(r.get(k)) for k in sorted(r)))


def _join_plan(*, null_safe: bool = False) -> dict[str, Any]:
    return {
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
                        "leftKey": "id",
                        "rightKey": "id",
                        "nullSafe": null_safe,
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


@pytest.mark.polars
@pytest.mark.spark
def test_differential_null_safe_join() -> None:
    plan = _join_plan(null_safe=True)
    left_rows = [{"id": 1, "a": 10}, {"id": None, "a": 20}]
    right_rows = [{"id": 1, "b": 100}, {"id": None, "b": 200}]
    req = {
        "profiles": ["dtcs:profile/portable-relational/1"],
        "actions": ["dtcs:join"],
        "functions": [],
    }

    pc = polars_compiler()
    assert pc.analyze(
        plan,
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="s",
            profile_name="t",
            engine="polars",
        ),
        requirements=req,
    ).supported
    compiled = pc.compile(
        plan,
        context=TransformCompileContext(
            pipeline_id="p",
            plan_id="pl",
            step_name="s",
            profile_name="t",
            engine="polars",
        ),
        requirements=req,
    )
    bundle = asyncio.run(
        pc.execute(
            compiled,
            inputs={
                "left": pl.DataFrame(left_rows),
                "right": pl.DataFrame(right_rows),
            },
            parameters={},
            context=TransformExecutionContext(
                run_id="r",
                pipeline_id="p",
                plan_id="pl",
                step_name="s",
                engine="polars",
            ),
        )
    )
    polars_out = _normalize(bundle.valid["result"].to_dicts())

    provider = create_provider()
    ctx = ResourceContext(run_id="r", pipeline_id="p", plan_id="pl")
    handle = provider.acquire(
        SparkSessionRequest(app_name="diff-nullsafe", master="local[1]"), ctx
    )
    try:
        sc = spark_compiler()
        compiled_s = sc.compile(
            plan,
            context=TransformCompileContext(
                pipeline_id="p",
                plan_id="pl",
                step_name="s",
                profile_name="t",
                engine="pyspark",
            ),
            requirements=req,
        )
        session = handle.session
        bundle_s = asyncio.run(
            sc.execute(
                compiled_s,
                inputs={
                    "left": session.createDataFrame(left_rows),
                    "right": session.createDataFrame(right_rows),
                },
                parameters={},
                context=TransformExecutionContext(
                    run_id="r",
                    pipeline_id="p",
                    plan_id="pl",
                    step_name="s",
                    engine="pyspark",
                    metadata={"spark_session": session},
                ),
            )
        )
        spark_df = next(iter(bundle_s.valid.values()))
        spark_out = _normalize(
            [
                row.asDict() if hasattr(row, "asDict") else dict(row)
                for row in spark_df.collect()
            ]
        )
    finally:
        provider.release(handle, ctx)

    assert polars_out == spark_out
    assert len(polars_out) == 2
