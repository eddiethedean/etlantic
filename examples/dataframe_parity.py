"""Parity example: one pipeline, Polars or Pandas via profile."""

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
from etlantic.registry import PlanningContext


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


@NormalizeCustomers.implementation("polars")
def normalize_polars(customers):
    import polars as pl

    frame = customers if hasattr(customers, "with_columns") else pl.DataFrame(customers)
    return frame.with_columns(
        (pl.col("first_name") + " " + pl.col("last_name")).alias("full_name")
    ).select("customer_id", "full_name")


@NormalizeCustomers.implementation("pandas")
def normalize_pandas(customers):
    import pandas as pd

    frame = (
        customers if isinstance(customers, pd.DataFrame) else pd.DataFrame(customers)
    )
    out = frame.copy()
    out["full_name"] = out["first_name"] + " " + out["last_name"]
    return out[["customer_id", "full_name"]]


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="curated")


def run_with_engine(engine: str):
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "customers",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )
    profile = Profile(name=f"{engine}-example", dataframe_engine=engine)
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    report = CustomerPipeline.run(profile=profile, runtime=runtime, context=context)
    from etlantic.reports import render_text

    print(render_text(report))
    for row in runtime.memory.get("curated"):
        print(row.model_dump() if hasattr(row, "model_dump") else row)
    return runtime, report


if __name__ == "__main__":
    import sys

    engine = sys.argv[1] if len(sys.argv) > 1 else "polars"
    run_with_engine(engine)
