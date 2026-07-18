"""Regression coverage for 0.13 PySpark portable parity fixes."""

from __future__ import annotations

import pytest

pytest.importorskip("sparkless")

from etlantic.spark.provider import ResourceContext, SparkSessionRequest
from etlantic.transform.compiler import TransformPlanningContext
from etlantic_pyspark import create_provider, create_transform_compiler
from etlantic_pyspark.lowering.actions import apply_action
from etlantic_pyspark.lowering.expr import lower_expr


@pytest.fixture
def spark_session():
    provider = create_provider()
    ctx = ResourceContext(run_id="r", pipeline_id="p", plan_id="pl")
    handle = provider.acquire(
        SparkSessionRequest(app_name="parity-fixes", master="local[1]"), ctx
    )
    try:
        yield handle.session
    finally:
        provider.release(handle, ctx)


@pytest.mark.spark
def test_unequal_key_join_coalesces_like_polars(spark_session) -> None:
    left = spark_session.createDataFrame([{"aid": 1, "v": 10}])
    right = spark_session.createDataFrame([{"bid": 1, "w": 100}])
    out = apply_action(
        left,
        {
            "kind": {
                "action": "dtcs:join",
                "parameters": {
                    "type": "inner",
                    "right": "right",
                    "leftKey": "aid",
                    "rightKey": "bid",
                    "collisionPolicy": "fail",
                },
            }
        },
        parameters={},
        frames={"right": right},
    )
    rows = [r.asDict() for r in out.collect()]
    assert out.columns == ["aid", "v", "w"]
    assert rows == [{"aid": 1, "v": 10, "w": 100}]


@pytest.mark.spark
def test_with_fields_replaces_existing_column(spark_session) -> None:
    frame = spark_session.createDataFrame([{"x": 1}])
    out = apply_action(
        frame,
        {
            "kind": {
                "action": "dtcs:with_fields",
                "parameters": {
                    "assignments": [
                        {
                            "name": "x",
                            "expression": {
                                "kind": "literal",
                                "value": {"type": "integer", "value": 9},
                            },
                        }
                    ]
                },
            }
        },
        parameters={},
    )
    assert out.columns == ["x"]
    assert [r.asDict() for r in out.collect()] == [{"x": 9}]


@pytest.mark.spark
def test_substr_is_zero_based_and_replace_is_literal(spark_session) -> None:
    frame = spark_session.createDataFrame([{"s": "abcdef"}, {"s": "a.b"}])
    substr = lower_expr(
        {
            "kind": "call",
            "callee": "dtcs:substr",
            "args": [
                {"kind": "fieldRef", "scope": "field", "target": "s"},
                {"kind": "literal", "value": {"type": "integer", "value": 0}},
                {"kind": "literal", "value": {"type": "integer", "value": 3}},
            ],
        },
        parameters={},
    )
    replaced = lower_expr(
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
    out = frame.select(substr.alias("sub"), replaced.alias("rep")).collect()
    rows = [r.asDict() for r in out]
    assert rows[0]["sub"] == "abc"
    assert rows[1]["rep"] == "X"


@pytest.mark.spark
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
                            "collisionPolicy": "coalesce",
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
            engine="pyspark",
        ),
        requirements={
            "profiles": ["dtcs:profile/portable-relational/1"],
            "actions": ["dtcs:join"],
            "functions": [],
        },
    )
    assert report.supported is False
