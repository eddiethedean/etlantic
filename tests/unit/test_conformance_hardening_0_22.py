"""WP3: capability-truthfulness + Spark conformance hardening (public suites)."""

from __future__ import annotations

import pytest

from etlantic.capabilities import PluginCapabilities
from etlantic.spark.protocol import (
    SPARK_PROTOCOL_VERSION,
    CompiledSparkPlan,
    DatasetRef,
    SparkPlanRegion,
    SparkPluginInfo,
)
from etlantic.testing import (
    assert_capability_claims_consistent,
    assert_capability_matches_behavior,
    run_spark_conformance_suite,
)


def test_consistent_claims_pass() -> None:
    caps = PluginCapabilities(engine="echo", dataframe=True, eager=True)
    assert_capability_claims_consistent(caps)


def test_overstated_sql_claim_fails_with_finding() -> None:
    # sql_merge implies sql; claiming merge without sql is inconsistent.
    caps = PluginCapabilities(engine="liar", sql=False, sql_merge=True)
    with pytest.raises(AssertionError) as exc:
        assert_capability_claims_consistent(caps)
    assert "sql_merge" in str(exc.value)
    assert "sql" in str(exc.value)


def test_unknown_vocabulary_major_fails() -> None:
    caps = PluginCapabilities(
        engine="future", vocabulary_version="etlantic.capabilities/2"
    )
    with pytest.raises(AssertionError):
        assert_capability_claims_consistent(caps)


def test_capability_matches_behavior_overstated() -> None:
    caps = PluginCapabilities(engine="e", lazy=True)
    with pytest.raises(AssertionError):
        assert_capability_matches_behavior(caps, "lazy", lambda: False)


def test_capability_matches_behavior_undeclared() -> None:
    caps = PluginCapabilities(engine="e", lazy=False)
    with pytest.raises(AssertionError):
        assert_capability_matches_behavior(caps, "lazy", lambda: True)


def test_capability_matches_behavior_agrees() -> None:
    caps = PluginCapabilities(engine="e", lazy=True)
    assert_capability_matches_behavior(caps, "lazy", lambda: True)


class _FakeSparkPlugin:
    """Minimal session-free Spark plugin honoring etlantic.spark/1 compile."""

    def __init__(self, caps: PluginCapabilities) -> None:
        self._caps = caps

    @property
    def info(self) -> SparkPluginInfo:
        return SparkPluginInfo(
            name="fake-spark",
            engine="pyspark",
            version="0.0.1",
            protocol_version=SPARK_PROTOCOL_VERSION,
            capabilities=self._caps,
        )

    def capabilities(self) -> PluginCapabilities:
        return self._caps

    def dataset_from_binding(self, *, binding, location=None, metadata=None):
        return DatasetRef(name=binding, format="memory")

    def compile(self, region: SparkPlanRegion, *, context) -> CompiledSparkPlan:
        return CompiledSparkPlan(
            region_id=region.identity,
            node_names=region.node_names,
        )

    def cancel(self, *, run_id: str | None = None) -> None:
        return None

    def execute_storage_op(self, op, *, context=None):
        raise NotImplementedError("fake plugin does not execute storage ops")


def test_spark_conformance_passes_for_honest_plugin() -> None:
    caps = PluginCapabilities(engine="pyspark", spark=True, dataframe=False)
    run_spark_conformance_suite(_FakeSparkPlugin(caps))


def test_spark_conformance_fails_for_overstated_plugin() -> None:
    # spark_merge implies spark; missing spark root must be rejected.
    caps = PluginCapabilities(
        engine="pyspark", spark=False, spark_merge=True, dataframe=False
    )
    with pytest.raises(AssertionError):
        run_spark_conformance_suite(_FakeSparkPlugin(caps))
