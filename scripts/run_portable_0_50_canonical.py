#!/usr/bin/env python3
"""Run the unchanged authored 0.50 canonical pipeline on all seven engines."""

from __future__ import annotations

import asyncio
from typing import Any

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    Transformation,
)
from etlantic.plan import plan_pipeline
from etlantic.registry import PlanningContext
from etlantic.runtime import RunStatus
from etlantic.testing.portable_transform_conformance import (
    default_frame_factory,
    normalize_rows,
    rows_from_frame,
)
from etlantic.transform import functions as F
from etlantic.transform.compiler import (
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
)
from etlantic.transform.local_compiler import LocalTransformCompiler
from etlantic.transform.validate import report_or_raise, validate_plan_budgets


class _ProbeRow(Data):
    value: int


class _ProbeOut(Data):
    value: int


class _ProbeTransform(Transformation):
    rows: Input[_ProbeRow]
    result: Output[_ProbeOut]


@_ProbeTransform.portable
def _probe_transform(rows):
    return rows.filter(F.col("value") > 0).select("value")


class _ProbePipeline(Pipeline):
    raw: Extract[_ProbeRow] = Extract(asset="probe")
    transformed = _ProbeTransform.step(rows=raw)
    curated: Load[_ProbeOut] = Load(input=transformed.result, asset="probe_out")


def _exercise_public_pipeline_path() -> None:
    """Prove the campaign enters through authoring, planning, and runtime APIs."""
    profile = Profile(
        name="canonical-public-path",
        dataframe_engine="local",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.memory.seed("probe", [_ProbeRow(value=1), _ProbeRow(value=-1)])
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(_ProbePipeline, context=context)
    report_or_raise(validate_plan_budgets(plan.to_dict()))
    result = _ProbePipeline.run(profile=profile, runtime=runtime, context=context)
    if result.status is not RunStatus.SUCCEEDED:
        raise AssertionError(f"public canonical probe failed: {result}")
    rows = runtime.memory.get("probe_out") or []
    if [row.model_dump() for row in rows] != [{"value": 1}]:
        raise AssertionError("public canonical probe returned an unexpected result")


def _plan() -> dict[str, Any]:
    return {
        "planIdentity": "dtcs.transform-plan/2",
        "inputs": {"orders": {}, "customers": {}, "bonus": {}},
        "actions": [
            {
                "id": "f",
                "kind": {
                    "id": "f",
                    "action": "dtcs:filter",
                    "target": "orders",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "gt",
                            "left": {
                                "kind": "fieldRef",
                                "scope": "field",
                                "target": "amount",
                            },
                            "right": {
                                "kind": "literal",
                                "value": {"type": "integer", "value": 0},
                            },
                        }
                    },
                },
            },
            {
                "id": "p",
                "kind": {
                    "id": "p",
                    "action": "dtcs:project",
                    "target": "f",
                    "parameters": {"fields": ["customer_id", "amount"]},
                },
            },
            {
                "id": "j",
                "kind": {
                    "id": "j",
                    "action": "dtcs:join",
                    "target": "p",
                    "parameters": {
                        "type": "left",
                        "right": "customers",
                        "leftKey": "customer_id",
                        "rightKey": "customer_id",
                        "collisionPolicy": "fail",
                    },
                },
            },
            {
                "id": "a",
                "kind": {
                    "id": "a",
                    "action": "dtcs:aggregate",
                    "target": "j",
                    "parameters": {
                        "groupBy": ["region"],
                        "aggregates": [
                            {
                                "name": "total",
                                "expression": {
                                    "kind": "call",
                                    "callee": "dtcs:sum",
                                    "args": [
                                        {
                                            "kind": "fieldRef",
                                            "scope": "field",
                                            "target": "amount",
                                        }
                                    ],
                                },
                            }
                        ],
                    },
                },
            },
            {
                "id": "u",
                "kind": {
                    "id": "u",
                    "action": "dtcs:union",
                    "target": "a",
                    "parameters": {"other": "bonus", "mode": "byName"},
                },
            },
            {
                "id": "s",
                "kind": {
                    "id": "s",
                    "action": "dtcs:sort",
                    "target": "u",
                    "parameters": {
                        "keys": [
                            {"column": "total", "direction": "desc", "nulls": "last"}
                        ]
                    },
                },
            },
            {
                "id": "d",
                "kind": {
                    "id": "d",
                    "action": "dtcs:deduplicate",
                    "target": "s",
                    "parameters": {},
                },
            },
            {
                "id": "l",
                "kind": {
                    "id": "l",
                    "action": "dtcs:limit",
                    "target": "d",
                    "parameters": {"count": 3},
                },
            },
        ],
        "outputs": {"result": {}},
        "requirements": {"dependencies": [{"from": "l", "to": "result"}]},
    }


def _inputs() -> dict[str, list[dict[str, Any]]]:
    return {
        "orders": [
            {"customer_id": 1, "amount": 10},
            {"customer_id": 2, "amount": 5},
            {"customer_id": 3, "amount": -1},
        ],
        "customers": [
            {"customer_id": 1, "region": "east"},
            {"customer_id": 2, "region": "west"},
        ],
        "bonus": [{"region": "north", "total": 99}],
    }


def _compilers() -> list[Any]:
    from etlantic_duckdb import create_transform_compiler as duckdb

    from etlantic_datafusion import create_transform_compiler as datafusion
    from etlantic_pandas import create_transform_compiler as pandas
    from etlantic_polars import create_transform_compiler as polars
    from etlantic_pyspark import create_transform_compiler as pyspark
    from etlantic_sql import create_transform_compiler as sql

    return [
        LocalTransformCompiler(),
        polars(),
        pandas(),
        sql(),
        pyspark(),
        datafusion(),
        duckdb(),
    ]


def main() -> int:
    _exercise_public_pipeline_path()
    plan = _plan()
    expected = normalize_rows(
        [
            {"region": "north", "total": 99},
            {"region": "east", "total": 10},
            {"region": "west", "total": 5},
        ]
    )
    for compiler in _compilers():
        factory = default_frame_factory(compiler.info.engine)
        try:
            profile = Profile(
                name=f"qualification-{compiler.info.engine}",
                dataframe_engine=(
                    compiler.info.engine
                    if compiler.info.engine
                    in {"local", "polars", "pandas", "duckdb", "datafusion"}
                    else None
                ),
                sql_engine="sql" if compiler.info.engine == "sql" else None,
                spark_engine="pyspark" if compiler.info.engine == "pyspark" else None,
                portable_transform_policy="require",
            )
            if profile.portable_transform_policy != "require":
                raise AssertionError(
                    "canonical qualification must require portable execution"
                )
            report_or_raise(validate_plan_budgets(plan))
            planning = TransformPlanningContext(
                "qualification", "canonical", "qualification", compiler.info.engine
            )
            report = compiler.analyze(plan, context=planning)
            if not report.supported:
                raise AssertionError(f"{compiler.info.engine}: {report.findings!r}")
            compiled = compiler.compile(
                plan,
                context=TransformCompileContext(
                    "qualification",
                    "plan",
                    "canonical",
                    "qualification",
                    compiler.info.engine,
                ),
            )
            metadata: dict[str, Any] = {}
            session = getattr(
                getattr(factory, "_etlantic_handle", None), "session", None
            )
            if session is not None:
                metadata["spark_session"] = session
            bundle = asyncio.run(
                compiler.execute(
                    compiled,
                    inputs={name: factory(rows) for name, rows in _inputs().items()},
                    parameters={},
                    context=TransformExecutionContext(
                        "qualification",
                        "qualification",
                        "plan",
                        "canonical",
                        compiler.info.engine,
                        metadata=metadata,
                    ),
                )
            )
            actual = normalize_rows(rows_from_frame(bundle.valid["result"]))
            if any(set(row) != {"region", "total"} for row in actual):
                raise AssertionError(
                    f"{compiler.info.engine}: contract fields diverged"
                )
            if actual != expected:
                raise AssertionError(
                    f"{compiler.info.engine}: normalized canonical result diverged"
                )
            print(f"{compiler.info.engine}: pass")
        finally:
            provider = getattr(factory, "_etlantic_provider", None)
            handle = getattr(factory, "_etlantic_handle", None)
            resource_context = getattr(factory, "_etlantic_ctx", None)
            if provider and handle and resource_context:
                provider.release(handle, resource_context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
