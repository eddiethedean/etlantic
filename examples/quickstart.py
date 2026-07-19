"""Smallest complete ETLantic local-runtime pipeline.

Run with:

    uv run python examples/quickstart.py
"""

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
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
            customer_id=customer.customer_id,
            full_name=f"{customer.first_name} {customer.last_name}",
        )
        for customer in customers
    ]


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(
        input=normalized.result,
        asset="customer_sink",
    )


def run_example() -> tuple[PipelineRuntime, object]:
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )
    report = CustomerPipeline.run(profile="development", runtime=runtime)
    return runtime, report


if __name__ == "__main__":
    runtime, report = run_example()
    print(report.to_text())
    for customer in runtime.memory.get("customer_sink"):
        print(customer.model_dump())
