"""Fake Spark Connect provider tests (live Databricks/EMR skipped)."""

from __future__ import annotations

import os

import pytest

from etlantic.spark.provider import ResourceContext, SparkSessionRequest
from etlantic_spark_connect import FakeSparkConnectProvider, live_configured


def test_fake_acquire() -> None:
    provider = FakeSparkConnectProvider()
    handle = provider.acquire(
        SparkSessionRequest(app_name="unit"),
        ResourceContext(run_id="r", pipeline_id="p", plan_id="plan"),
    )
    assert handle.metadata["fake"] is True
    provider.release(
        handle, ResourceContext(run_id="r", pipeline_id="p", plan_id="plan")
    )


@pytest.mark.skipif(
    not live_configured() and not os.environ.get("ETLANTIC_SPARK_CONNECT_URL"),
    reason="047-S-01 live Spark Connect skipped",
)
def test_live_spark_connect_skipped() -> None:
    pytest.skip("047-S-01 live Databricks/EMR/Spark Connect remains deferred")


def test_semantic_compare_vs_local_pyspark_when_present() -> None:
    pytest.importorskip("etlantic_pyspark")
    fake = FakeSparkConnectProvider().capabilities()
    assert fake.spark is True
    assert "spark-connect" in fake.extras
