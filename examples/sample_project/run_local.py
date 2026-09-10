"""Validate, plan, and run the sample project locally.

From the repository root:

    uv run python -m examples.sample_project.run_local
"""

from etlantic import PipelineRuntime, Profile

from .contracts import RawCustomer
from .pipeline import CustomerPipeline


def main() -> None:
    profile = Profile(
        name="development",
        dataframe_engine="local",
        portable_transform_policy="require",
    )
    CustomerPipeline.validate(profile=profile).raise_for_errors()
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
    print(report.status.value)
    for customer in runtime.memory.get("customer_sink"):
        print(customer.model_dump())


if __name__ == "__main__":
    main()
