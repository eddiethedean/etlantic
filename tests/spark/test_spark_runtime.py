"""Spark 0.7 unit and integration tests."""

from __future__ import annotations

import pytest

from etlantic import (
    SPARK_PROTOCOL_VERSION,
    STREAMING_STABILITY,
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    Transformation,
    explain_plan,
    plan_pipeline,
)
from etlantic.exceptions import NodeExecutionError, PipelineValidationError
from etlantic.registry import PlanningContext
from etlantic.runtime.spark_exec import (
    assert_batch_not_in_streaming,
    assert_udf_policy,
    is_spark_engine,
)
from etlantic.spark.protocol import (
    ExpressionStrategy,
    SchemaCompatibility,
    SparkUdfPolicy,
)
from etlantic.spark.provider import (
    ResourceContext,
    SessionOwnership,
    SparkSessionRequest,
)
from etlantic.spark.schema import compare_types, map_contract_schema


def test_spark_protocol_constants() -> None:
    assert SPARK_PROTOCOL_VERSION == "etlantic.spark/1"
    assert STREAMING_STABILITY == "experimental"
    assert is_spark_engine("pyspark")
    assert is_spark_engine("spark")
    assert not is_spark_engine("sql")


def test_schema_mapping_lossy_and_unknown() -> None:
    class Customer(Data):
        customer_id: int
        full_name: str

    exact = map_contract_schema(Customer)
    assert exact.overall is SchemaCompatibility.EXACT

    lossy = compare_types("integer", "StringType")
    assert lossy is SchemaCompatibility.LOSSY

    unknown = compare_types("widget", None)
    assert unknown is SchemaCompatibility.UNKNOWN

    observed = map_contract_schema(
        Customer, observed={"customer_id": "StringType", "full_name": "StringType"}
    )
    assert observed.overall is SchemaCompatibility.LOSSY
    assert any(d.get("compatibility") == "lossy" for d in observed.diagnostics)


def test_udf_policy_native_required() -> None:
    with pytest.raises(NodeExecutionError) as exc:
        assert_udf_policy(
            strategies=[ExpressionStrategy.SCALAR_PYTHON_UDF],
            policy=SparkUdfPolicy.NATIVE_REQUIRED,
            node_name="step",
        )
    assert exc.value.code == "PMSPARK310"

    warnings = assert_udf_policy(
        strategies=[ExpressionStrategy.PANDAS_UDF],
        policy=SparkUdfPolicy.WARN,
        node_name="step",
    )
    assert warnings and warnings[0]["code"] == "PMSPARK311"


def test_batch_only_rejected_from_streaming() -> None:
    with pytest.raises(NodeExecutionError) as exc:
        assert_batch_not_in_streaming(
            streaming_region=True, batch_only=True, node_name="batch_step"
        )
    assert exc.value.code == "PMSPARK320"


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


def test_region_fusion_preserves_step_identities() -> None:
    pytest.importorskip("etlantic_pyspark")
    from etlantic.registry import PluginDescriptor
    from etlantic_pyspark import create_plugin

    plugin = create_plugin()
    runtime = PipelineRuntime()
    runtime.register_spark_plugin("pyspark", plugin)
    profile = Profile(name="spark-plan", spark_engine="pyspark")
    plan = plan_pipeline(
        CustomerSparkPipeline,
        context=PlanningContext.create(profile, registry=runtime.registry),
    )
    spark_regions = [r for r in plan.regions if r.engine == "pyspark"]
    assert spark_regions
    region = spark_regions[0]
    assert "normalized" in region.node_names
    assert region.metadata.get("logical_identities")
    explanation = explain_plan(plan)
    assert explanation["spark_protocol"] == "etlantic.spark/1"
    assert explanation["spark_fusion"]
    assert explanation["spark_streaming_stability"] == "experimental"
    dumped = plan.to_dict()
    assert "password" not in str(dumped).lower()
    _ = PluginDescriptor  # imported for typing clarity in related tests


def test_region_split_reason_visible_in_plan_explain() -> None:
    pytest.importorskip("etlantic_pyspark")
    from etlantic_pyspark import create_plugin

    plugin = create_plugin()
    runtime = PipelineRuntime()
    runtime.register_spark_plugin("pyspark", plugin)
    profile = Profile(name="spark-plan", spark_engine="pyspark")
    plan = plan_pipeline(
        CustomerSparkPipeline,
        context=PlanningContext.create(profile, registry=runtime.registry),
    )
    fusion = plan.metadata["spark_fusion"]
    assert fusion[0]["strategy"] == "lazy_dataframe"
    assert "normalized" in fusion[0]["logical_identities"]


def test_missing_spark_plugin_fails_planning() -> None:
    from etlantic.registry import builtin_stub_registry

    profile = Profile(name="spark-missing", spark_engine="pyspark")
    ctx = PlanningContext.create(profile, registry=builtin_stub_registry())
    with pytest.raises(PipelineValidationError):
        plan_pipeline(CustomerSparkPipeline, context=ctx)


@pytest.mark.spark
def test_local_spark_provider() -> None:
    pytest.importorskip("sparkless")
    from etlantic_pyspark import create_provider

    provider = create_provider()
    ctx = ResourceContext(
        run_id="run-test",
        pipeline_id="pipe",
        plan_id="plan",
    )
    handle = provider.acquire(
        SparkSessionRequest(app_name="etlantic-test", master="local[1]"),
        ctx,
    )
    assert handle.session is not None
    assert "password" not in handle.to_dict()
    assert handle.ownership is SessionOwnership.PROVIDER
    # External session must not be stopped
    external = handle.session
    ext_handle = provider.acquire(
        SparkSessionRequest(
            app_name="ext",
            ownership=SessionOwnership.EXTERNAL,
            metadata={"session": external},
        ),
        ctx,
    )
    provider.release(ext_handle, ctx)
    # Still usable
    assert external.range(1).count() == 1
    provider.release(handle, ctx)


@pytest.mark.spark
def test_pipeline_with_local_spark() -> None:
    pytest.importorskip("sparkless")
    from etlantic_pyspark import create_plugin, create_provider

    plugin = create_plugin()
    provider = create_provider()
    runtime = PipelineRuntime()
    runtime.register_spark_plugin("pyspark", plugin)
    runtime.register_spark_provider("local", provider)
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
            RawCustomer(customer_id=2, first_name="Grace", last_name="Hopper"),
        ],
    )
    profile = Profile(name="spark-run", spark_engine="pyspark")
    report = CustomerSparkPipeline.run(profile=profile, runtime=runtime)
    assert report.status.value == "succeeded"
    sink = runtime.memory.get("customer_sink")
    assert len(sink) == 2
    names = {c.full_name for c in sink}
    assert names == {"Ada Lovelace", "Grace Hopper"}
    spark_steps = [s for s in report.steps if s.metadata.get("spark")]
    assert spark_steps
    # Region compile recorded on the transform step
    assert any((s.metadata.get("spark") or {}).get("compiled") for s in spark_steps)


@pytest.mark.spark
def test_pyspark_to_delta_pipeline(tmp_path) -> None:
    pytest.importorskip("sparkless")
    from etlantic.spark.protocol import (
        DatasetRef,
        SparkExecutionContext,
        SparkWrite,
        SparkWriteMode,
    )
    from etlantic_pyspark import create_plugin, create_provider

    plugin = create_plugin()
    provider = create_provider()
    ctx = ResourceContext(run_id="r", pipeline_id="p", plan_id="pl")
    handle = provider.acquire(
        SparkSessionRequest(app_name="delta-test", master="local[1]"), ctx
    )
    plugin.bind_session(handle)
    session = handle.session
    df = session.createDataFrame(
        [{"customer_id": 1, "full_name": "Ada Lovelace"}],
        schema="customer_id LONG, full_name STRING",
    )
    path = str(tmp_path / "customers.parquet")
    write = SparkWrite(
        source=df,
        target=DatasetRef(name="customers", format="parquet", path=path),
        mode=SparkWriteMode.OVERWRITE,
    )
    result = plugin.execute_write(
        write,
        context=SparkExecutionContext(
            run_id="r",
            pipeline_id="p",
            plan_id="pl",
            step_name="curated",
        ),
    )
    assert result.metrics.rows_affected == 1
    assert result.schema_observation is not None
    # Merge without delta fails closed when format isn't delta and delta disabled
    merge = SparkWrite(
        source=df,
        target=DatasetRef(name="customers", format="json", path=str(tmp_path / "x")),
        mode=SparkWriteMode.MERGE,
        merge_keys=("customer_id",),
    )
    plugin._delta_enabled = False
    merge_result = plugin.execute_write(
        merge,
        context=SparkExecutionContext(
            run_id="r", pipeline_id="p", plan_id="pl", step_name="curated"
        ),
    )
    assert any(d["code"] == "PMSPARK331" for d in merge_result.diagnostics)
    provider.release(handle, ctx)


def test_streaming_stability_labeled_experimental() -> None:
    from etlantic.spark.streaming import StreamingQuerySpec

    spec = StreamingQuerySpec(checkpoint_location="/tmp/ckpt")
    assert spec.to_dict()["stability"] == "experimental"
