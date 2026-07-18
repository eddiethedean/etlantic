"""Private Polars relational compiler e2e tests (0.13a)."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("polars")

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
from etlantic.plan import plan_pipeline
from etlantic.registry import PlanningContext
from etlantic.transform import functions as F
from etlantic.transform.compiler import TransformPlanningContext
from etlantic_polars import create_plugin, create_transform_compiler


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


@pytest.mark.polars
def test_analyze_accepts_relational_join() -> None:
    compiler = create_transform_compiler()
    report = compiler.analyze(
        AggregateOrders.to_transform_plan(),
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="s",
            profile_name="t",
            engine="polars",
        ),
        requirements=AggregateOrders.portable_definition().requirements,
    )
    assert report.supported is True


@pytest.mark.polars
def test_analyze_rejects_unknown_join_type_with_path() -> None:
    compiler = create_transform_compiler()
    plan = {
        "planIdentity": "dtcs.transform-plan/2",
        "actions": [
            {
                "id": "j1",
                "kind": {
                    "action": "dtcs:join",
                    "id": "j1",
                    "parameters": {
                        "type": "bogus",
                        "right": "r",
                        "leftKey": "a",
                        "rightKey": "a",
                        "collisionPolicy": "fail",
                    },
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
    assert report.supported is False
    finding = next(f for f in report.findings if "bogus" in f.requirement)
    assert finding.expression_path == "j1"


@pytest.mark.polars
def test_plan_and_run_relational_aggregate() -> None:
    profile = Profile(
        name="polars-relational",
        dataframe_engine="polars",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_plugin())
    _seed(runtime)
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(RelationalPipeline, context=context)
    impl = plan.implementations["aggregated"]
    assert impl.kind == "portable_compiled"
    assert impl.compiler_name == "etlantic-polars"

    report = RelationalPipeline.run(
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
