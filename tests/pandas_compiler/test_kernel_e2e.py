"""Private Pandas kernel compiler e2e tests (0.14a)."""

from __future__ import annotations

import pytest

pytest.importorskip("pandas")

from etlantic import (
    Data,
    Input,
    Output,
    Parameter,
    Pipeline,
    PipelineRuntime,
    Profile,
    RunStatus,
    Sink,
    Source,
    Transformation,
)
from etlantic.plan import explain_plan, plan_pipeline
from etlantic.registry import PlanningContext
from etlantic.transform import functions as F
from etlantic.transform.compiler import TransformPlanningContext
from etlantic_pandas import create_plugin, create_transform_compiler


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


class PortablePandasPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(input=normalized.result, binding="curated")


def _seed(runtime: PipelineRuntime) -> None:
    runtime.memory.seed(
        "customers",
        [
            RawCustomer(customer_id=1, email="A@X.COM", age=30),
            RawCustomer(customer_id=2, email="b@y.com", age=10),
        ],
    )


@pytest.mark.pandas
def test_analyze_accepts_relational_requirements() -> None:
    compiler = create_transform_compiler()
    report = compiler.analyze(
        {"planIdentity": "dtcs.transform-plan/2"},
        context=TransformPlanningContext(
            pipeline_id="p",
            step_name="s",
            profile_name="t",
            engine="pandas",
        ),
        requirements={
            "profiles": ["dtcs:profile/portable-relational/1"],
            "actions": ["dtcs:join"],
            "functions": [],
        },
    )
    assert report.supported is True
    assert compiler.info.capabilities.lazy is False
    assert compiler.info.capabilities.eager is True


@pytest.mark.pandas
def test_plan_portable_without_native_callable() -> None:
    assert "pandas" not in NormalizeCustomers.implementations()
    profile = Profile(
        name="pandas-portable",
        dataframe_engine="pandas",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("pandas", create_plugin())
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(PortablePandasPipeline, context=context)
    impl = plan.implementations["normalized"]
    assert impl.kind == "portable_compiled"
    assert impl.compiler_name == "etlantic-pandas"
    explained = explain_plan(plan)
    step = next(s for s in explained["steps"] if s["node"] == "normalized")
    assert step["implementation_kind"] == "portable_compiled"


@pytest.mark.pandas
def test_run_portable_kernel_on_pandas() -> None:
    profile = Profile(
        name="pandas-portable",
        dataframe_engine="pandas",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("pandas", create_plugin())
    _seed(runtime)
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    report = PortablePandasPipeline.run(
        profile=profile,
        runtime=runtime,
        context=context,
    )
    assert report.status is RunStatus.SUCCEEDED
    rows = list(runtime.memory.get("curated") or [])
    assert [r.model_dump() for r in rows] == [
        {"customer_id": 1, "email": "a@x.com", "age": 30}
    ]
