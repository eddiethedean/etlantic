"""0.32 Delta storage ops — fail-closed without delta-spark; live when present."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("sparkless")

from etlantic.spark.protocol import (
    DatasetRef,
    SparkCompilationContext,
    SparkExecutionContext,
    SparkPlanRegion,
)
from etlantic.testing.spark import run_spark_conformance_suite
from etlantic_pyspark.plugin import PySparkPlugin


def _ctx(step: str = "storage") -> SparkExecutionContext:
    return SparkExecutionContext(
        run_id="r1",
        pipeline_id="p1",
        plan_id="plan",
        step_name=step,
        region_id="region-1",
        job_group="jg-1",
    )


@pytest.mark.spark
def test_spark_conformance_includes_storage_caps() -> None:
    run_spark_conformance_suite(PySparkPlugin())


@pytest.mark.spark
def test_compile_records_cache_points() -> None:
    plugin = PySparkPlugin()
    region = SparkPlanRegion(
        identity="r",
        node_names=("a", "b"),
        metadata={"a": {"cache": True}, "b": {"checkpoint": True}},
    )
    compiled = plugin.compile(
        region,
        context=SparkCompilationContext(
            run_id="r", pipeline_id="p", plan_id="pl", region_id="r"
        ),
    )
    assert compiled.cache_points == ("a",)
    assert compiled.checkpoint_points == ("b",)
    assert compiled.logical_identities["a"] == "r:a"


@pytest.mark.spark
def test_storage_ops_fail_closed_without_delta() -> None:
    plugin = PySparkPlugin()
    target = DatasetRef(name="t", path="/tmp/does-not-exist.delta", format="delta")
    for op in ("optimize", "vacuum", "history", "time_travel", "schema_evolution"):
        result = plugin.execute_storage_op(
            operation=op,
            target=target,
            context=_ctx(op),
            options={"version_as_of": 0} if op == "time_travel" else {},
        )
        assert result.diagnostics
        assert any(str(d.get("severity")) == "error" for d in result.diagnostics), op


@pytest.mark.spark
def test_cancel_without_session_is_safe() -> None:
    plugin = PySparkPlugin()
    result = plugin.cancel(context=_ctx(), job_group="jg-1")
    assert result.metrics.cancelled is False
    assert "cancel" in result.metrics.actions


@pytest.mark.spark
def test_storage_merge_error_is_no_write() -> None:
    plugin = PySparkPlugin()
    target = DatasetRef(name="t", path="/tmp/x.delta", format="delta")
    result = plugin.execute_storage_op(
        operation="merge",
        target=target,
        context=_ctx("merge"),
        options={},  # missing source → error
    )
    assert any(str(d.get("severity")) == "error" for d in result.diagnostics)
    assert result.metrics.actions == ["no_write"]


@pytest.mark.spark
def test_merge_write_requires_delta_format() -> None:
    from etlantic.spark.protocol import SparkWrite, SparkWriteMode

    plugin = PySparkPlugin()
    plugin._delta_enabled = True
    # Bind a minimal session-less path by stubbing _to_dataframe after format gate.
    write = SparkWrite(
        mode=SparkWriteMode.MERGE,
        source=[{"id": 1}],
        target=DatasetRef(name="t", path="/tmp/x.parquet", format="parquet"),
        merge_keys=("id",),
    )

    class _FakeSession:
        pass

    plugin._session = _FakeSession()

    def _fake_to_df(_session: object, value: object) -> object:
        return value

    plugin._to_dataframe = _fake_to_df  # type: ignore[method-assign]
    result = plugin.execute_write(write, context=_ctx("w"))
    assert any(d.get("code") == "PMSPARK331" for d in result.diagnostics)
    assert result.metrics.actions == ["no_write"]


@pytest.mark.spark
@pytest.mark.skipif(
    os.environ.get("ETLANTIC_DELTA_LIVE", "").strip().lower()
    not in {"1", "true", "yes"},
    reason="Set ETLANTIC_DELTA_LIVE=1 for live Delta tests",
)
def test_delta_live_optional() -> None:
    """Live Delta suite runs only when delta-spark + real PySpark are available."""
    pytest.importorskip("delta")
    # Live path exercised by plugin integration environments; keep marker honest.
    assert PySparkPlugin().capabilities().supports("storage.delta.merge")
