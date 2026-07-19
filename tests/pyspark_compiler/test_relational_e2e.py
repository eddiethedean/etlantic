"""Private PySpark portable compiler e2e tests (0.13b, sparkless by default)."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("sparkless")

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    RunStatus,
    Transformation,
)
from etlantic.plan import plan_pipeline
from etlantic.registry import PlanningContext
from etlantic.transform import functions as F
from etlantic.transform.compiler import TransformPlanningContext
from etlantic_pyspark import create_plugin, create_provider, create_transform_compiler


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


class RelationalSparkPipeline(Pipeline):
    orders: Extract[Order] = Extract(asset="orders")
    customers: Extract[Customer] = Extract(asset="customers")
    aggregated = AggregateOrders.step(orders=orders, customers=customers)
    curated: Load[AggOut] = Load(input=aggregated.result, asset="curated")


@pytest.mark.spark
def test_analyze_accepts_kernel_and_relational() -> None:
    compiler = create_transform_compiler()
    assert (
        "dtcs:profile/portable-relational-kernel/1"
        in compiler.info.capabilities.profiles
    )
    assert "dtcs:profile/portable-relational/1" in compiler.info.capabilities.profiles
    report = compiler.analyze(
        AggregateOrders.to_transform_plan(),
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="s",
            profile_name="t",
            engine="pyspark",
        ),
        requirements=AggregateOrders.portable_definition().requirements,
    )
    assert report.supported is True


@pytest.mark.spark
def test_plan_and_run_relational_aggregate_sparkless() -> None:
    profile = Profile(
        name="spark-portable",
        spark_engine="pyspark",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_spark_plugin("pyspark", create_plugin())
    runtime.register_spark_provider("local", create_provider())
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
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(RelationalSparkPipeline, context=context)
    impl = plan.implementations["aggregated"]
    assert impl.kind == "portable_compiled"
    assert impl.compiler_name == "etlantic-pyspark"
    assert impl.engine == "pyspark"

    report = RelationalSparkPipeline.run(
        profile=profile,
        runtime=runtime,
        context=context,
    )
    assert report.status is RunStatus.SUCCEEDED
    curated: list[Any] = list(runtime.memory.get("curated") or [])
    by_region = {
        (row.model_dump() if hasattr(row, "model_dump") else dict(row))["region"]: (
            row.model_dump() if hasattr(row, "model_dump") else dict(row)
        )["total"]
        for row in curated
    }
    assert by_region == {"east": 15.0, "west": 7.0}
    spark_meta = [
        s.metadata.get("spark")
        for s in report.steps
        if (s.metadata or {}).get("spark", {}).get("portable_compiled")
    ]
    assert spark_meta
    assert spark_meta[0].get("udf_policy") == "deny"
