"""Correctness regressions for 0.5.0 dataframe wiring."""

from __future__ import annotations

import tempfile
from pathlib import Path

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
from etlantic.dataframe.discovery import discover_dataframe_plugins
from etlantic.dataframe.protocol import (
    DataframeExecutionContext,
    DataframeValidationOutcome,
    DataframeValidationPolicy,
    ValidationDecision,
)
from etlantic.plan import plan_pipeline
from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
from etlantic.profile import Profile
from etlantic.registry import PlanningContext
from etlantic.runtime.artifacts import ArtifactStore
from etlantic.schema_drift import normalize_schema_from_fields


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
def normalize_polars(customers):  # type: ignore[no-untyped-def]
    import polars as pl

    return customers.with_columns(
        (pl.col("first_name") + " " + pl.col("last_name")).alias("full_name")
    ).select("customer_id", "full_name")


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Load[Customer] = Load(input=normalized.result, asset="curated")


def _seed(runtime: PipelineRuntime) -> None:
    runtime.memory.seed(
        "customers",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )


@pytest.mark.polars
def test_run_without_explicit_context_uses_discovered_plugins() -> None:
    """Default Pipeline.run must use runtime-discovered plugins (no context=)."""
    pytest.importorskip("polars")
    runtime = PipelineRuntime()
    assert "polars" in runtime.dataframe_plugins
    _seed(runtime)
    report = CustomerPipeline.run(
        profile=Profile(name="polars-default", dataframe_engine="polars"),
        runtime=runtime,
    )
    assert report.status is RunStatus.SUCCEEDED
    assert runtime.memory.get("curated")[0].full_name == "Ada Lovelace"


@pytest.mark.polars
def test_discovery_without_manual_register() -> None:
    pytest.importorskip("polars")
    found = discover_dataframe_plugins()
    assert "polars" in found
    runtime = PipelineRuntime()
    # Do not call register_dataframe_plugin; discovery alone must plan/run.
    assert "polars" in runtime.registry.engines
    _seed(runtime)
    report = CustomerPipeline.run(
        profile=Profile(name="discovered", dataframe_engine="polars"),
        runtime=runtime,
    )
    assert report.status is RunStatus.SUCCEEDED


@pytest.mark.polars
def test_fan_out_keeps_in_memory_not_durable() -> None:
    polars = pytest.importorskip("polars")

    class Branch(Transformation):
        customers: Input[Customer]
        result: Output[Customer]

    @Branch.implementation("polars")
    def branch_impl(customers):
        lf = customers.lazy() if isinstance(customers, polars.DataFrame) else customers
        return lf

    class FanOutPipeline(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="customers")
        normalized = NormalizeCustomers.step(customers=raw)
        left = Branch.step(customers=normalized.result)
        right = Branch.step(customers=normalized.result)
        sink_l: Load[Customer] = Load(input=left.result, asset="left")
        sink_r: Load[Customer] = Load(input=right.result, asset="right")

    runtime = PipelineRuntime()
    _seed(runtime)
    profile = Profile(name="fanout", dataframe_engine="polars")
    plan = plan_pipeline(
        FanOutPipeline,
        context=PlanningContext.create(profile=profile, registry=runtime.registry),
    )
    mid = next(
        o
        for o in plan.output_resolutions
        if o.node_name == "normalized" and o.port_name == "result"
    )
    assert mid.artifact.strategy is ArtifactStrategy.IN_MEMORY
    assert any(
        b.reason == "fan_out_reuse" and b.producer_node == "normalized"
        for b in plan.materialization_boundaries
    )
    report = FanOutPipeline.run(profile=profile, runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED


@pytest.mark.polars
def test_multi_output_port_collect_and_validation() -> None:
    polars = pytest.importorskip("polars")

    class Split(Transformation):
        customers: Input[RawCustomer]
        good: Output[Customer]
        bad: Output[Customer]

    @Split.implementation("polars")
    def split_impl(customers: polars.DataFrame) -> dict[str, polars.DataFrame]:
        good = customers.with_columns(
            (polars.col("first_name") + " " + polars.col("last_name")).alias(
                "full_name"
            )
        ).select("customer_id", "full_name")
        bad = good.head(0)
        return {"good": good, "bad": bad}

    class MultiOutPipeline(Pipeline):
        raw: Extract[RawCustomer] = Extract(asset="customers")
        split = Split.step(customers=raw)
        curated: Load[Customer] = Load(input=split.good, asset="curated")

    runtime = PipelineRuntime()
    _seed(runtime)
    report = MultiOutPipeline.run(
        profile=Profile(name="multi", dataframe_engine="polars"),
        runtime=runtime,
    )
    assert report.status is RunStatus.SUCCEEDED
    assert len(runtime.memory.get("curated")) == 2


@pytest.mark.polars
def test_schema_observation_uses_frame_inspect() -> None:
    polars = pytest.importorskip("polars")
    from etlantic.runtime.orchestrator import _observe_records_schema
    from etlantic_polars import create_plugin

    plugin = create_plugin()
    frame = polars.DataFrame({"customer_id": [1], "full_name": ["Ada Lovelace"]})
    obs = _observe_records_schema("normalized", frame, layer="current", plugin=plugin)
    assert obs is not None
    names = {f.name for f in obs.schema.fields}
    assert names == {"customer_id", "full_name"}
    assert "value" not in names
    bogus = normalize_schema_from_fields(
        [{"name": "value", "logical_type": "DataFrame", "required": True}],
        identity="bogus",
    )
    assert obs.schema.fingerprint() != bogus.fingerprint()


@pytest.mark.polars
def test_quarantine_populates_invalid_channel() -> None:
    polars = pytest.importorskip("polars")
    from etlantic_polars import create_plugin

    plugin = create_plugin()
    context = DataframeExecutionContext(
        run_id="r",
        pipeline_id="p",
        plan_id="plan",
        step_name="s",
        engine="polars",
        collect=True,
        validation_policy=DataframeValidationPolicy(
            input_outcome=DataframeValidationOutcome.QUARANTINE,
            output_outcome=DataframeValidationOutcome.QUARANTINE,
        ),
    )
    frame = polars.DataFrame(
        [
            {"customer_id": 1, "full_name": "Ada"},
            {"customer_id": "bad", "full_name": "Nope"},
        ]
    )
    valid, decision, diags, invalid = plugin.validate_frame(
        frame,
        contract_type=Customer,
        context=context,
        boundary="output_validation",
        port_name="result",
    )
    assert decision is ValidationDecision.QUARANTINED
    assert invalid is not None
    assert plugin.row_count(invalid) == 1
    assert plugin.row_count(valid) == 1
    assert diags


@pytest.mark.pandas
def test_pandas_quarantine_and_object_dtype_warning() -> None:
    pytest.importorskip("pandas")
    import pandas as pd

    from etlantic.dataframe.protocol import ArtifactOwnership
    from etlantic_pandas import create_plugin

    plugin = create_plugin()
    context = DataframeExecutionContext(
        run_id="r",
        pipeline_id="p",
        plan_id="plan",
        step_name="s",
        engine="pandas",
        collect=True,
        validation_policy=DataframeValidationPolicy(
            input_outcome=DataframeValidationOutcome.QUARANTINE,
            output_outcome=DataframeValidationOutcome.QUARANTINE,
        ),
    )
    frame = pd.DataFrame(
        [
            {"customer_id": 1, "full_name": "Ada"},
            {"customer_id": "bad", "full_name": "Nope"},
        ]
    )
    valid, decision, diags, invalid = plugin.validate_frame(
        frame,
        contract_type=Customer,
        context=context,
        boundary="output_validation",
        port_name="result",
    )
    assert decision is ValidationDecision.QUARANTINED
    assert invalid is not None
    assert plugin.row_count(invalid) == 1
    assert plugin.row_count(valid) == 1
    assert any(d.get("code") == "PMDF420" for d in diags)

    owned = plugin.ensure_ownership(
        valid, ownership=ArtifactOwnership.COPIED, context=context
    )
    owned.loc[:, "full_name"] = "MUTATED"
    assert list(valid["full_name"]) == ["Ada"]
    assert list(owned["full_name"]) == ["MUTATED"]


@pytest.mark.polars
def test_durable_store_rejects_native_frames() -> None:
    polars = pytest.importorskip("polars")
    ref = ArtifactRef(
        identity="test:frame",
        logical_output="n.result",
        strategy=ArtifactStrategy.DURABLE,
        security_domain="default",
    )
    with tempfile.TemporaryDirectory() as tmp:
        store = ArtifactStore(workspace=Path(tmp))
        with pytest.raises(TypeError, match="durably serialize"):
            store.put(ref, polars.DataFrame({"a": [1]}), durable=True)


@pytest.mark.polars
def test_lazyframe_dtype_mismatch_fail_closed() -> None:
    polars = pytest.importorskip("polars")
    from etlantic_polars import create_plugin

    plugin = create_plugin()
    context = DataframeExecutionContext(
        run_id="r",
        pipeline_id="p",
        plan_id="plan",
        step_name="s",
        engine="polars",
        collect=False,
        validation_policy=DataframeValidationPolicy(
            output_outcome=DataframeValidationOutcome.FAIL,
        ),
    )
    lf = polars.LazyFrame({"customer_id": ["1"], "full_name": ["Ada"]})
    _, decision, diags, _ = plugin.validate_frame(
        lf,
        contract_type=Customer,
        context=context,
        boundary="output_validation",
    )
    assert decision is ValidationDecision.FAILED
    assert any(d.get("code") == "PMDF412" for d in diags)
