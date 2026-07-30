"""Prefect ExecutionScheduler example (requires etlantic-prefect).

Run with:

    uv run --group prefect python examples/prefect_run.py
"""

from __future__ import annotations

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


class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str


class Customer(Data):
    customer_id: int
    full_name: str


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


@NormalizeCustomers.implementation("local")
def normalize_customers(customers: list[RawCustomer]) -> list[Customer]:
    return [
        Customer(
            customer_id=row.customer_id,
            full_name=f"{row.first_name} {row.last_name}",
        )
        for row in customers
    ]


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(
        input=normalized.result,
        asset="customer_sink",
    )


def run_example() -> tuple[PipelineRuntime, object]:
    from etlantic_prefect import create_plugin

    runtime = PipelineRuntime()
    runtime.register_scheduler_plugin("prefect", create_plugin())
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )
    profile = Profile(name="prefect-demo", orchestrator="prefect")
    report = CustomerPipeline.run(profile=profile, runtime=runtime)
    return runtime, report


if __name__ == "__main__":
    runtime, report = run_example()
    print(report.to_text())
    print("scheduler:", report.metadata.get("etlantic.scheduler"))
    for customer in runtime.memory.get("customer_sink"):
        print(customer.model_dump())
