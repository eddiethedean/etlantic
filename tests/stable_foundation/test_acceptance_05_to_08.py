"""Stable-foundation acceptance items 5-8 (engines + Airflow compile)."""

from __future__ import annotations

import pytest

from etlantic import (
    PipelineRuntime,
    Profile,
    compile_plan,
    plan_pipeline,
)
from etlantic.plan import explain_plan
from etlantic.registry import PlanningContext
from etlantic.testing import run_portable_transform_conformance_suite


@pytest.mark.polars
@pytest.mark.pandas
def test_sf_05_equivalent_polars_and_pandas_transformations() -> None:
    """Item 5: equivalent Polars and Pandas portable transformations."""
    pytest.importorskip("polars")
    pytest.importorskip("pandas")
    pytest.importorskip("etlantic_polars")
    pytest.importorskip("etlantic_pandas")

    # Reuse the graduated portable projection helper from the testing foundation.
    from tests.testing.test_testing_foundation_0_37 import _run_portable_projection

    polars_rows = _run_portable_projection("polars")
    pandas_rows = _run_portable_projection("pandas")
    assert (
        polars_rows
        == pandas_rows
        == [
            {"id": 1, "name": "Ada"},
            {"id": 2, "name": "Grace"},
        ]
    )
    from etlantic_pandas import create_transform_compiler as pandas_compiler
    from etlantic_polars import create_transform_compiler as polars_compiler

    run_portable_transform_conformance_suite(polars_compiler())
    run_portable_transform_conformance_suite(pandas_compiler())


@pytest.mark.sql
def test_sf_06_sql_native_pipeline_with_safe_pushdown() -> None:
    """Item 6: SQL-native pipeline with safe fusion/pushdown evidence."""
    pytest.importorskip("sqlalchemy")
    import os

    os.environ.setdefault("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from etlantic.registry import BindingDescriptor, builtin_stub_registry
    from etlantic.sql.discovery import register_discovered_plugins
    from etlantic.sql.expression import col
    from etlantic.sql.helpers import is_safe_identifier
    from etlantic.sql.protocol import RelationRef, SqlExecutionContext, SqlQuery
    from etlantic_sql import create_plugin
    from tests.sql.test_sql_runtime import CustomerPipeline as SqlCustomerPipeline

    assert is_safe_identifier("customer_id")
    assert not is_safe_identifier("customer;drop")

    plugin = create_plugin()
    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": plugin})
    registry.register_binding(
        BindingDescriptor(
            binding="raw_customers", provider="sql", location="raw_customers"
        )
    )
    registry.register_binding(
        BindingDescriptor(
            binding="curated_customers",
            provider="sql",
            location="curated_customers",
            metadata={"write_intent": "insert_select"},
        )
    )
    profile = Profile(name="sf-sql", sql_engine="sql")
    context = PlanningContext.create(profile, registry=registry)
    plan = SqlCustomerPipeline.plan(profile=profile, context=context)
    explanation = explain_plan(plan)
    assert explanation["sql_protocol"] == "etlantic.sql/1"
    assert explanation["sql_fusion"]

    ctx = SqlExecutionContext(
        run_id="sf06",
        pipeline_id="sf06",
        plan_id=plan.plan_id,
        step_name="normalized",
    )
    compiled = plugin.compile_query(
        SqlQuery(
            source=RelationRef(name="raw_customers"),
            columns=(col("customer_id"),),
        ),
        context=ctx,
    )
    assert "SELECT" in compiled.text.upper()
    assert ";" not in RelationRef(name="raw_customers").name


@pytest.mark.spark
def test_sf_07_pyspark_batch_lazy_region_preservation() -> None:
    """Item 7: PySpark batch plan preserves lazy regions / step identities."""
    pytest.importorskip("sparkless")
    pytest.importorskip("etlantic_pyspark")
    from etlantic_pyspark import create_plugin
    from tests.spark.test_spark_runtime import CustomerSparkPipeline

    plugin = create_plugin()
    runtime = PipelineRuntime()
    runtime.register_spark_plugin("pyspark", plugin)
    profile = Profile(name="sf-spark", spark_engine="pyspark")
    plan = plan_pipeline(
        CustomerSparkPipeline,
        context=PlanningContext.create(profile, registry=runtime.registry),
    )
    spark_regions = [r for r in plan.regions if r.engine == "pyspark"]
    assert spark_regions
    assert "normalized" in spark_regions[0].node_names
    assert spark_regions[0].metadata.get("logical_identities")
    explanation = explain_plan(plan)
    assert explanation["spark_protocol"] == "etlantic.spark/1"
    assert explanation["spark_fusion"]
    fusion = plan.metadata["spark_fusion"]
    assert fusion[0]["strategy"] == "lazy_dataframe"
    assert "normalized" in fusion[0]["logical_identities"]


@pytest.mark.airflow
def test_sf_08_airflow_compilation_of_logical_plan() -> None:
    """Item 8: Airflow compilation of the same logical plan."""
    pytest.importorskip("etlantic_airflow")
    from examples.memory_customers import CustomerPipeline as LogicalPipeline

    from etlantic_airflow import create_plugin

    plugin = create_plugin()
    runtime = PipelineRuntime()
    runtime.register_orchestrator_plugin("airflow", plugin)
    profile = Profile(
        name="sf-airflow",
        orchestrator="airflow",
        schedule={
            "type": "cron",
            "expression": "0 2 * * *",
            "timezone": "UTC",
            "catchup": False,
        },
        execution={"retries": 1, "retry_delay_seconds": 60, "max_active_runs": 1},
    )
    plan = plan_pipeline(
        LogicalPipeline,
        context=PlanningContext.create(profile, registry=runtime.registry),
    )
    artifact = compile_plan(plan, target="airflow", profile=profile, plugin=plugin)
    assert artifact.task_ids == {"raw", "normalized", "curated"}
    assert artifact.dependencies["normalized"] == ("raw",)
    assert "PythonOperator" in artifact.source
    assert "password" not in artifact.source.lower()
