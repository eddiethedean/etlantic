"""Validate, plan, and run the sample project locally.

From the repository root:

    uv run python -m examples.sample_project.run_local
"""

from etlantic import PipelineRuntime

from .contracts import RawCustomer
from .pipeline import CustomerPipeline


def main() -> None:
    CustomerPipeline.validate(profile="development").raise_for_errors()
    CustomerPipeline.plan(profile="development")

    runtime = PipelineRuntime()
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )
    report = CustomerPipeline.run(profile="development", runtime=runtime)
    print(report.status.value)
    for customer in runtime.memory.get("customer_sink"):
        print(customer.model_dump())


if __name__ == "__main__":
    main()
