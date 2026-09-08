#!/usr/bin/env python3
"""Run one authored 0.50 portable pipeline through every public runtime path."""

from __future__ import annotations

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
from etlantic.transform import functions as F


class _Order(Data):
    customer_id: int
    amount: float


class _Customer(Data):
    customer_id: int
    region: str


class _Bonus(Data):
    region: str
    total: float


class _Result(Data):
    region: str
    total: float


class _CanonicalTransform(Transformation):
    orders: Input[_Order]
    customers: Input[_Customer]
    bonus: Input[_Bonus]
    result: Output[_Result]


@_CanonicalTransform.portable
def _canonical_transform(orders, customers, bonus):
    """The one engine-neutral body qualified by the 0.50 campaign."""
    prepared = (
        orders.filter(F.col("amount") > 0)
        .select("customer_id", "amount")
        .join(customers, on="customer_id", how="left", collision_policy="fail")
    )
    totals = prepared.groupBy("region").agg(total=F.sum(F.col("amount")).alias("total"))
    return (
        totals.unionByName(bonus)
        .orderBy(F.col("total").desc_nulls_last())
        .dropDuplicates()
        .limit(3)
    )


class _CanonicalPipeline(Pipeline):
    raw_orders: Extract[_Order] = Extract(asset="orders")
    raw_customers: Extract[_Customer] = Extract(asset="customers")
    raw_bonus: Extract[_Bonus] = Extract(asset="bonus")
    transformed = _CanonicalTransform.step(
        orders=raw_orders,
        customers=raw_customers,
        bonus=raw_bonus,
    )
    curated: Load[_Result] = Load(input=transformed.result, asset="canonical_result")


def _profile(engine: str) -> Profile:
    settings: dict[str, Any] = {
        "name": f"qualification-{engine}",
        "portable_transform_policy": "require",
    }
    if engine in {"local", "polars", "pandas", "datafusion"}:
        settings["dataframe_engine"] = engine
    elif engine in {"sql", "duckdb"}:
        settings["sql_engine"] = engine
    elif engine == "pyspark":
        settings["spark_engine"] = engine
    else:  # pragma: no cover - static campaign inventory
        raise ValueError(f"unknown qualification engine: {engine}")
    return Profile(**settings)


def _register_runtime_engine(runtime: PipelineRuntime, engine: str) -> None:
    """Register only the public plugin surface selected by ``Profile``."""
    if engine == "polars":
        from etlantic_polars import create_plugin

        runtime.register_dataframe_plugin(engine, create_plugin())
    elif engine == "pandas":
        from etlantic_pandas import create_plugin

        runtime.register_dataframe_plugin(engine, create_plugin())
    elif engine == "datafusion":
        from etlantic_datafusion import create_plugin

        runtime.register_dataframe_plugin(engine, create_plugin())
    elif engine == "sql":
        from etlantic_sql import create_plugin

        runtime.register_sql_plugin(engine, create_plugin())
    elif engine == "duckdb":
        from etlantic_duckdb import create_plugin

        runtime.register_sql_plugin(engine, create_plugin())
    elif engine == "pyspark":
        from etlantic_pyspark import create_plugin, create_provider

        runtime.register_spark_plugin(engine, create_plugin())
        runtime.register_spark_provider("local", create_provider())


def _seed(runtime: PipelineRuntime) -> None:
    runtime.memory.seed(
        "orders",
        [
            _Order(customer_id=1, amount=10.0),
            _Order(customer_id=2, amount=5.0),
            _Order(customer_id=3, amount=-1.0),
        ],
    )
    runtime.memory.seed(
        "customers",
        [
            _Customer(customer_id=1, region="east"),
            _Customer(customer_id=2, region="west"),
        ],
    )
    runtime.memory.seed("bonus", [_Bonus(region="north", total=99.0)])


def _rows(value: Any) -> list[dict[str, Any]]:
    return [
        item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for item in (value or [])
    ]


def _run(engine: str) -> None:
    profile = _profile(engine)
    runtime = PipelineRuntime()
    _register_runtime_engine(runtime, engine)
    _seed(runtime)
    context = PlanningContext.create(profile=profile, registry=runtime.registry)

    # This is deliberately the same plan and same profile that the runtime
    # consumes below.  The campaign must not replace it with direct compiler
    # calls or a raw hand-authored plan.
    plan = plan_pipeline(_CanonicalPipeline, context=context)
    implementation = plan.implementations["transformed"]
    if implementation.kind != "portable_compiled" or implementation.engine != engine:
        raise AssertionError(
            f"{engine}: public planning did not select portable runtime"
        )

    report = _CanonicalPipeline.run(profile=profile, runtime=runtime, context=context)
    if report.status is not RunStatus.SUCCEEDED:
        raise AssertionError(f"{engine}: public runtime failed: {report}")
    actual = sorted(
        _rows(runtime.memory.get("canonical_result")), key=lambda row: -row["total"]
    )
    expected = [
        {"region": "north", "total": 99.0},
        {"region": "east", "total": 10.0},
        {"region": "west", "total": 5.0},
    ]
    if actual != expected:
        raise AssertionError(f"{engine}: public runtime result diverged: {actual!r}")


def main() -> int:
    for engine in (
        "local",
        "polars",
        "pandas",
        "sql",
        "pyspark",
        "datafusion",
        "duckdb",
    ):
        _run(engine)
        print(f"{engine}: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
