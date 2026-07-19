"""Run a portable kernel transform on Polars without a native implementation.

Requires:

    uv sync --group dataframes

Or from published packages:

    pip install etlantic==0.14.0 etlantic-polars==0.14.0

Run with:

    uv run python examples/portable_polars_kernel.py
"""

from __future__ import annotations

from typing import Any

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
    Transformation,
)
from etlantic.plan import explain_plan, plan_pipeline
from etlantic.registry import PlanningContext
from etlantic.transform import functions as F
from etlantic_polars import create_plugin


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
def normalize(customers, minimum_age):
    return (
        customers.filter(F.col("age") >= minimum_age)
        .withColumn("email", F.lower(F.col("email")))
        .select("customer_id", "email", "age")
    )


class PortablePolarsPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="curated")


def run_example() -> tuple[PipelineRuntime, object, dict[str, Any]]:
    assert "polars" not in NormalizeCustomers.implementations()
    profile = Profile(
        name="polars-portable",
        dataframe_engine="polars",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_plugin())
    runtime.memory.seed(
        "customers",
        [
            RawCustomer(customer_id=1, email="A@X.COM", age=30),
            RawCustomer(customer_id=2, email="b@y.com", age=10),
        ],
    )
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(PortablePolarsPipeline, context=context)
    explained = explain_plan(plan)
    report = PortablePolarsPipeline.run(
        profile=profile,
        runtime=runtime,
        context=context,
    )
    return runtime, report, explained


if __name__ == "__main__":
    runtime, report, explained = run_example()
    print(report.to_text())
    step = next(s for s in explained["steps"] if s["node"] == "normalized")
    print(
        "implementation_kind=",
        step.get("implementation_kind"),
        "compiler=",
        (step.get("compiler") or {}).get("name"),
    )
    for row in runtime.memory.get("curated") or []:
        data = row.model_dump() if hasattr(row, "model_dump") else dict(row)
        print(data)
