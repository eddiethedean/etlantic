"""Private Polars ↔ PySpark ↔ Pandas differential corpus (0.14)."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("polars")
pytest.importorskip("pandas")
pytest.importorskip("sparkless")

from etlantic import (
    Data,
    Input,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    RunStatus,
    Sink,
    Source,
    Transformation,
)
from etlantic.registry import PlanningContext
from etlantic.transform import functions as F
from etlantic_pandas import create_plugin as create_pandas_plugin
from etlantic_polars import create_plugin as create_polars_plugin
from etlantic_pyspark import create_plugin as create_spark_plugin
from etlantic_pyspark import create_provider


class Order(Data):
    order_id: int
    customer_id: int
    amount: float


class Customer(Data):
    customer_id: int
    region: str


class AggOut(Data):
    region: str
    total: float


class AggregateOrders(Transformation):
    orders: Input[Order]
    customers: Input[Customer]
    result: Output[AggOut]


@AggregateOrders.portable
def _agg(orders, customers):
    joined = orders.join(customers, on="customer_id", how="left")
    return joined.groupBy("region").agg(total=F.sum(F.col("amount")).alias("total"))


class RelationalPipeline(Pipeline):
    orders: Source[Order] = Source(binding="orders")
    customers: Source[Customer] = Source(binding="customers")
    aggregated = AggregateOrders.step(orders=orders, customers=customers)
    curated: Sink[AggOut] = Sink(input=aggregated.result, binding="curated")


def _normalize_rows(rows: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        data = row.model_dump() if hasattr(row, "model_dump") else dict(row)
        cleaned = {k: data[k] for k in sorted(data)}
        out.append(cleaned)
    return sorted(out, key=lambda r: tuple(str(r[k]) for k in sorted(r)))


def _seed(runtime: PipelineRuntime) -> None:
    runtime.memory.seed(
        "orders",
        [
            Order(order_id=1, customer_id=1, amount=10.0),
            Order(order_id=2, customer_id=1, amount=5.0),
            Order(order_id=3, customer_id=2, amount=7.0),
        ],
    )
    runtime.memory.seed(
        "customers",
        [
            Customer(customer_id=1, region="east"),
            Customer(customer_id=2, region="west"),
        ],
    )


def _run_polars() -> list[dict[str, Any]]:
    profile = Profile(
        name="polars-diff",
        dataframe_engine="polars",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_polars_plugin())
    _seed(runtime)
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    report = RelationalPipeline.run(profile=profile, runtime=runtime, context=context)
    assert report.status is RunStatus.SUCCEEDED
    return _normalize_rows(list(runtime.memory.get("curated") or []))


def _run_spark() -> list[dict[str, Any]]:
    profile = Profile(
        name="spark-diff",
        spark_engine="pyspark",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_spark_plugin("pyspark", create_spark_plugin())
    runtime.register_spark_provider("local", create_provider())
    _seed(runtime)
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    report = RelationalPipeline.run(profile=profile, runtime=runtime, context=context)
    assert report.status is RunStatus.SUCCEEDED
    return _normalize_rows(list(runtime.memory.get("curated") or []))


def _run_pandas() -> list[dict[str, Any]]:
    profile = Profile(
        name="pandas-diff",
        dataframe_engine="pandas",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("pandas", create_pandas_plugin())
    _seed(runtime)
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    report = RelationalPipeline.run(profile=profile, runtime=runtime, context=context)
    assert report.status is RunStatus.SUCCEEDED
    return _normalize_rows(list(runtime.memory.get("curated") or []))


@pytest.mark.polars
@pytest.mark.pandas
@pytest.mark.spark
def test_differential_aggregate_pipeline() -> None:
    polars_rows = _run_polars()
    spark_rows = _run_spark()
    pandas_rows = _run_pandas()
    assert polars_rows == spark_rows == pandas_rows
    assert polars_rows == [
        {"region": "east", "total": 15.0},
        {"region": "west", "total": 7.0},
    ]


@pytest.mark.spark
@pytest.mark.real_pyspark
def test_catalyst_no_udf_on_real_pyspark() -> None:
    """Gated real-PySpark acceptance: plan is Catalyst-visible without UDFs."""
    import os

    if os.environ.get("SPARKLESS_TEST_MODE", "").lower() != "pyspark":
        pytest.skip("Set SPARKLESS_TEST_MODE=pyspark for real PySpark Catalyst checks")

    from etlantic.spark.provider import ResourceContext, SparkSessionRequest
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )
    from etlantic_pyspark import create_provider, create_transform_compiler

    provider = create_provider()
    ctx = ResourceContext(run_id="r", pipeline_id="p", plan_id="pl")
    handle = provider.acquire(
        SparkSessionRequest(app_name="catalyst-check", master="local[1]"), ctx
    )
    try:
        compiler = create_transform_compiler()
        plan = AggregateOrders.to_transform_plan()
        compiled = compiler.compile(
            plan,
            context=TransformCompileContext(
                pipeline_id="p",
                plan_id="pl",
                step_name="aggregated",
                profile_name="t",
                engine="pyspark",
            ),
            requirements=AggregateOrders.portable_definition().requirements,
        )
        session = handle.session
        orders = session.createDataFrame(
            [
                {"order_id": 1, "customer_id": 1, "amount": 10.0},
                {"order_id": 2, "customer_id": 1, "amount": 5.0},
            ]
        )
        customers = session.createDataFrame([{"customer_id": 1, "region": "east"}])
        import asyncio

        bundle = asyncio.run(
            compiler.execute(
                compiled,
                inputs={"orders": orders, "customers": customers},
                parameters={},
                context=TransformExecutionContext(
                    run_id="r",
                    pipeline_id="p",
                    plan_id="pl",
                    step_name="aggregated",
                    engine="pyspark",
                    metadata={"spark_session": session},
                ),
            )
        )
        df = next(iter(bundle.valid.values()))
        # Prefer explain string when available (PySpark); sparkless may omit JVM.
        explained = ""
        if hasattr(df, "explain"):
            try:
                explained = str(df._jdf.queryExecution())
            except Exception:
                explained = ""
        assert "PythonUDF" not in explained
        assert "FlatMapGroupsInPandas" not in explained
    finally:
        provider.release(handle, ctx)
