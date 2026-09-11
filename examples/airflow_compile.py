"""Compile a portable pipeline to an Airflow DAG module (ETLantic 0.34.0).

Requires:

    uv sync --group airflow --group airflow-runtime

Or from published packages:

    pip install etlantic==0.51.0 etlantic-airflow==0.51.0

Run with:

    uv run python examples/airflow_compile.py
"""

from __future__ import annotations

from pathlib import Path

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
    compile_plan,
    plan_pipeline,
)
from etlantic.registry import PlanningContext
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
def normalize(customers):
    return customers.select(
        "customer_id",
        F.concat_ws(" ", F.col("first_name"), F.col("last_name")).alias("full_name"),
    )


class CustomerAirflowPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="customer_sink")


def main() -> None:
    from etlantic_airflow import create_plugin

    plugin = create_plugin()
    runtime = PipelineRuntime()
    runtime.register_orchestrator_plugin("airflow", plugin)
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )

    local_profile = Profile(
        name="local",
        orchestrator="local",
        portable_transform_policy="require",
    )
    report = CustomerAirflowPipeline.run(profile=local_profile, runtime=runtime)
    print(report.to_text())
    assert report.status.value == "succeeded"

    airflow_profile = Profile(
        name="airflow",
        orchestrator="airflow",
        portable_transform_policy="require",
        schedule={
            "type": "cron",
            "expression": "0 2 * * *",
            "timezone": "UTC",
            "catchup": False,
        },
        execution={"retries": 1, "retry_delay_seconds": 60, "max_active_runs": 1},
    )
    plan = plan_pipeline(
        CustomerAirflowPipeline,
        context=PlanningContext.create(airflow_profile, registry=runtime.registry),
    )
    artifact = compile_plan(
        plan, target="airflow", profile=airflow_profile, plugin=plugin
    )
    out = Path("examples") / "_generated_customer_airflow_dag.py"
    artifact.write(out)
    print(f"Wrote {out} dag_id={artifact.dag_id} tasks={sorted(artifact.task_ids)}")
    print(artifact.explain())


if __name__ == "__main__":
    main()
