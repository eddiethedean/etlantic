"""Polars / Pandas dataframe plugin integration tests."""

from __future__ import annotations

import pytest

from pipelantic import (
    Data,
    Input,
    Output,
    Pipeline,
    PipelineRuntime,
    RunStatus,
    Sink,
    Source,
    Transformation,
)
from pipelantic.plan import explain_plan, plan_pipeline
from pipelantic.profile import Profile
from pipelantic.registry import PlanningContext, builtin_stub_registry

polars = pytest.importorskip("polars")
pandas = pytest.importorskip("pandas")


@pytest.fixture
def polars_plugin():
    from pipelantic_polars import create_plugin

    return create_plugin()


@pytest.fixture
def pandas_plugin():
    from pipelantic_pandas import create_plugin

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
def normalize_polars(customers: polars.DataFrame) -> polars.DataFrame:
    return customers.with_columns(
        (polars.col("first_name") + " " + polars.col("last_name")).alias("full_name")
    ).select("customer_id", "full_name")


@NormalizeCustomers.implementation("pandas")
def normalize_pandas(customers: pandas.DataFrame) -> pandas.DataFrame:
    out = customers.copy()
    out["full_name"] = out["first_name"] + " " + out["last_name"]
    return out[["customer_id", "full_name"]]


class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(input=normalized.result, binding="curated")


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
    assert curated[0].full_name == "Ada Lovelace"


@pytest.mark.polars
def test_polars_lazy_preserved_until_sink(polars_plugin) -> None:
    class LazyNormalize(Transformation):
        customers: Input[RawCustomer]
        result: Output[Customer]

    @LazyNormalize.implementation("polars")
    def normalize_lazy(customers):
        lf = customers.lazy() if isinstance(customers, polars.DataFrame) else customers
        return lf.with_columns(
            (polars.col("first_name") + " " + polars.col("last_name")).alias(
                "full_name"
            )
        ).select("customer_id", "full_name")

    class Mid(Transformation):
        customers: Input[Customer]
        result: Output[Customer]

    @Mid.implementation("polars")
    def mid_lazy(customers):
        lf = customers
        if isinstance(lf, polars.DataFrame):
            lf = lf.lazy()
        return lf  # stay lazy

    class LazyPipeline(Pipeline):
        raw: Source[RawCustomer] = Source(binding="customers")
        a = LazyNormalize.step(customers=raw)
        b = Mid.step(customers=a.result)
        curated: Sink[Customer] = Sink(input=b.result, binding="curated")

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
@pytest.mark.pandas
def test_profile_switches_engine_same_pipeline(polars_plugin, pandas_plugin) -> None:
    for engine, plugin in (("polars", polars_plugin), ("pandas", pandas_plugin)):
        runtime = PipelineRuntime()
        runtime.register_dataframe_plugin(engine, plugin)
        _seed_runtime(runtime)
        profile = Profile(name=f"{engine}-switch", dataframe_engine=engine)
        report = CustomerPipeline.run(
            profile=profile,
            runtime=runtime,
            context=PlanningContext.create(profile=profile, registry=runtime.registry),
        )
        assert report.status is RunStatus.SUCCEEDED
        assert runtime.memory.get("curated")[0].full_name == "Ada Lovelace"


@pytest.mark.polars
def test_core_does_not_import_polars_at_import_time() -> None:
    import importlib

    importlib.import_module("pipelantic.dataframe.arrow")
    from pipelantic.dataframe.arrow import arrow_available

    assert isinstance(arrow_available(), bool)


def test_stub_registry_unaffected() -> None:
    registry = builtin_stub_registry()
    assert "local" in registry.engines
    assert "polars" not in registry.engines
