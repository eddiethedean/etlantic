"""Local PySpark batch pipeline (ETLantic 0.7).

Requires: pip install etlantic-pyspark

Run with:

    python examples/pyspark_local.py
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


@NormalizeCustomers.implementation("pyspark")
def normalize_pyspark(customers):
    from pyspark.sql import functions as F

    return customers.withColumn(
        "full_name", F.concat_ws(" ", F.col("first_name"), F.col("last_name"))
    ).select("customer_id", "full_name")


class CustomerSparkPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="customer_sink")


def run_example() -> object:
    from etlantic_pyspark import create_plugin, create_provider

    runtime = PipelineRuntime()
    runtime.register_spark_plugin("pyspark", create_plugin())
    runtime.register_spark_provider("local", create_provider())
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )
    profile = Profile(name="spark-local", spark_engine="pyspark")
    return CustomerSparkPipeline.run(profile=profile, runtime=runtime)


if __name__ == "__main__":
    report = run_example()
    print(report.to_text())
