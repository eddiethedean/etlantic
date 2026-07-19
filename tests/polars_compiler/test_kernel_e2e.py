"""Private Polars kernel compiler e2e tests (0.12)."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("polars")

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Parameter,
    Pipeline,
    PipelineRuntime,
    Profile,
    RunStatus,
    Transformation,
)
from etlantic.plan import explain_plan, plan_pipeline
from etlantic.registry import PlanningContext
from etlantic.transform import functions as F
from etlantic_polars import create_plugin, create_transform_compiler


class RawCustomer(Data):
    customer_id: int
    email: str
    age: int


class Customer(Data):
    customer_id: int
    email: str
    age: int


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]


@NormalizeCustomers.portable
def _normalize(customers, minimum_age):
    return (
        customers.filter(F.col("age") >= minimum_age)
        .withColumn("email", F.lower(F.col("email")))
        .select("customer_id", "email", "age")
    )


class PortablePolarsPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="curated")


def _seed(runtime: PipelineRuntime) -> None:
    runtime.memory.seed(
        "customers",
        [
            RawCustomer(customer_id=1, email="A@X.COM", age=30),
            RawCustomer(customer_id=2, email="b@y.com", age=10),
        ],
    )


@pytest.mark.polars
def test_analyze_accepts_relational_join_requirements() -> None:
    """0.13 Polars claims portable-relational/1 including joins."""
    compiler = create_transform_compiler()
    from etlantic.transform.compiler import TransformPlanningContext

    report = compiler.analyze(
        {"planIdentity": "dtcs.transform-plan/2"},
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
    assert report.supported is True


@pytest.mark.polars
def test_plan_portable_without_native_callable() -> None:
    assert "polars" not in NormalizeCustomers.implementations()
    profile = Profile(
        name="polars-portable",
        dataframe_engine="polars",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_plugin())
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(PortablePolarsPipeline, context=context)
    impl = plan.implementations["normalized"]
    assert impl.kind == "portable_compiled"
    assert impl.compiler_name == "etlantic-polars"
    assert impl.portable_plan is not None
    explained = explain_plan(plan)
    step = next(s for s in explained["steps"] if s["node"] == "normalized")
    assert step["implementation_kind"] == "portable_compiled"
    assert step["ir_fingerprint"]


@pytest.mark.polars
def test_run_portable_kernel_on_polars() -> None:
    profile = Profile(
        name="polars-portable",
        dataframe_engine="polars",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_plugin())
    _seed(runtime)
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    report = PortablePolarsPipeline.run(
        profile=profile,
        runtime=runtime,
        context=context,
    )
    assert report.status is RunStatus.SUCCEEDED
    curated: list[Any] = list(runtime.memory.get("curated") or [])
    assert len(curated) == 1
    row = curated[0]
    data = row.model_dump() if hasattr(row, "model_dump") else dict(row)
    assert data["customer_id"] == 1
    assert data["email"] == "a@x.com"


@pytest.mark.polars
def test_require_plans_relational_join() -> None:
    """Joins are inside the 0.13 Polars claim set — planning must succeed."""

    class JoinCustomers(Transformation):
        left: Input[RawCustomer]
        right: Input[Customer]
        result: Output[Customer]

    @JoinCustomers.portable
    def _join(left, right):
        return left.join(right, on="customer_id", how="inner").select(
            "customer_id", "email", "age"
        )

    class JoinPipeline(Pipeline):
        raw_left: Extract[RawCustomer] = Extract(asset="left")
        raw_right: Extract[Customer] = Extract(asset="right")
        joined = JoinCustomers.step(left=raw_left, right=raw_right)
        out: Load[Customer] = Load(input=joined.result, asset="out")

    profile = Profile(
        name="polars-portable",
        dataframe_engine="polars",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_plugin())
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(JoinPipeline, context=context)
    assert plan.implementations["joined"].kind == "portable_compiled"
