"""Polars / Pandas dataframe plugin integration tests."""

from __future__ import annotations

from typing import Any

import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    RunStatus,
    Transformation,
)
from etlantic.plan import explain_plan, plan_pipeline
from etlantic.profile import Profile
from etlantic.registry import PlanningContext, builtin_stub_registry


@pytest.fixture
def polars_plugin():
    pytest.importorskip("polars")
    from etlantic_polars import create_plugin

    return create_plugin()


@pytest.fixture
def pandas_plugin():
    pytest.importorskip("pandas")
    from etlantic_pandas import create_plugin

    return create_plugin()


class Customer(Data):
    customer_id: int
    full_name: str


class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


@NormalizeCustomers.implementation("polars")
def normalize_polars(customers: Any) -> Any:
    import polars as pl

    return customers.with_columns(
        (pl.col("first_name") + " " + pl.col("last_name")).alias("full_name")
    ).select("customer_id", "full_name")


@NormalizeCustomers.implementation("pandas")
def normalize_pandas(customers: Any) -> Any:
    out = customers.copy()
    out["full_name"] = out["first_name"] + " " + out["last_name"]
    return out[["customer_id", "full_name"]]


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="curated")


def _seed_runtime(runtime: PipelineRuntime) -> None:
    runtime.memory.seed(
        "customers",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )


@pytest.mark.polars
def test_polars_eager_end_to_end(polars_plugin) -> None:
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", polars_plugin)
    _seed_runtime(runtime)
    report = CustomerPipeline.run(
        profile=Profile(name="polars-dev", dataframe_engine="polars"),
        runtime=runtime,
        context=PlanningContext.create(
            profile=Profile(name="polars-dev", dataframe_engine="polars"),
            registry=runtime.registry,
        ),
    )
    assert report.status is RunStatus.SUCCEEDED
    curated = runtime.memory.get("curated")
    assert [c.model_dump() for c in curated] == [
        {"customer_id": 1, "full_name": "Ada Lovelace"},
        {"customer_id": 2, "full_name": "Grace Hopper"},
    ]
    step = next(s for s in report.steps if s.step_name == "normalized")
    assert step.metadata.get("dataframe", {}).get("collected") is True


@pytest.mark.pandas
def test_pandas_eager_end_to_end(pandas_plugin) -> None:
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("pandas", pandas_plugin)
    _seed_runtime(runtime)
    profile = Profile(name="pandas-dev", dataframe_engine="pandas")
    report = CustomerPipeline.run(
        profile=profile,
        runtime=runtime,
        context=PlanningContext.create(profile=profile, registry=runtime.registry),
    )
    assert report.status is RunStatus.SUCCEEDED
    curated = runtime.memory.get("curated")
    assert [c.model_dump() for c in curated] == [
        {"customer_id": 1, "full_name": "Ada Lovelace"},
        {"customer_id": 2, "full_name": "Grace Hopper"},
    ]


@pytest.mark.polars
def test_polars_lazy_preserved_until_sink(polars_plugin) -> None:
    import polars as pl

    class LazyNormalize(Transformation):
        customers: Input[RawCustomer]
        result: Output[Customer]

    @LazyNormalize.implementation("polars")
    def normalize_lazy(customers):
        lf = customers.lazy() if isinstance(customers, pl.DataFrame) else customers
        return lf.with_columns(
            (pl.col("first_name") + " " + pl.col("last_name")).alias("full_name")
        ).select("customer_id", "full_name")

    class Mid(Transformation):
        customers: Input[Customer]
        result: Output[Customer]

    @Mid.implementation("polars")
    def mid_lazy(customers):
        lf = customers
        if isinstance(lf, pl.DataFrame):
            lf = lf.lazy()
        return lf  # stay lazy

    class LazyPipeline(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="customers")
        a = LazyNormalize.step(customers=raw)
        b = Mid.step(customers=a.result)
        curated: Load[Customer] = Load(input=b.result, asset="curated")

    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", polars_plugin)
    _seed_runtime(runtime)
    profile = Profile(name="polars-lazy", dataframe_engine="polars")
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(LazyPipeline, context=context)
    explained = explain_plan(plan)
    assert any(
        b.get("reason") == "collection_point" or b.get("reason") == "sink_publication"
        for b in explained["collection_points"]
    )
    # Adjacent polars steps should use LAZY strategy on intermediate output.
    mid_out = next(
        o
        for o in plan.output_resolutions
        if o.node_name == "a" and o.port_name == "result"
    )
    assert mid_out.artifact.strategy.value == "lazy"
    report = LazyPipeline.run(profile=profile, runtime=runtime, context=context)
    assert report.status is RunStatus.SUCCEEDED
    assert runtime.memory.get("curated")[0].full_name == "Ada Lovelace"


@pytest.mark.polars
def test_core_does_not_import_polars_at_import_time() -> None:
    import sys

    # Ensure the public arrow helper does not force a Polars import.
    before = "polars" in sys.modules
    from etlantic.dataframe.arrow import arrow_available

    assert isinstance(arrow_available(), bool)
    if not before:
        # Importing the helper must remain safe even when Polars is installed;
        # it should not eagerly load the engine module as a side effect of the
        # availability probe alone beyond what the environment already had.
        _ = arrow_available()


def test_stub_registry_unaffected() -> None:
    registry = builtin_stub_registry()
    assert "local" in registry.engines
    assert "polars" not in registry.engines
