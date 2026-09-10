"""In-memory CustomerPipeline demo (SDK seed + run).

This is not the docs Quickstart. For the canonical first success, use:

    etlantic init --with-toml

Run this companion with:

    uv run python examples/memory_customers.py
"""

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
from etlantic.transform import functions as F


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


@NormalizeCustomers.portable
def normalize_customers(customers):
    return customers.select(
        "customer_id",
        F.concat_ws(" ", F.col("first_name"), F.col("last_name")).alias("full_name"),
    )


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(
        input=normalized.result,
        asset="customer_sink",
    )


def run_example() -> tuple[PipelineRuntime, object]:
    """Validate, plan, and run the in-memory demo (used by CI)."""
    profile = Profile(
        name="development",
        dataframe_engine="local",
        portable_transform_policy="require",
    )
    validation = CustomerPipeline.validate(profile=profile)
    validation.raise_for_errors()
    CustomerPipeline.plan(profile=profile)

    runtime = PipelineRuntime()
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )
    report = CustomerPipeline.run(profile=profile, runtime=runtime)
    return runtime, report


def main() -> None:
    runtime, report = run_example()
    print(report.status.value)
    for customer in runtime.memory.get("customer_sink"):
        print(customer.model_dump())


if __name__ == "__main__":
    main()
