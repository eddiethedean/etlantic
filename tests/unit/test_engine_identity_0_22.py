# pyright: reportPrivateUsage=false
"""0.22 WP1: capability-driven engine identity (no privileged name sets)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from etlantic.capabilities import PluginCapabilities
from etlantic.engines import ExecutionFamily, get_engine_registry
from etlantic.plugins.coordinator import (
    should_discover_dataframe_plugins,
    should_discover_spark_plugins,
    should_discover_sql_plugins,
    should_include_transform_compilers,
)
from etlantic.registry import RegistryBundle
from etlantic.runtime.scheduler import ExecutionScheduler
from etlantic.runtime.scheduler_discovery import register_discovered_plugins


def test_synthetic_dataframe_capability_via_registry() -> None:
    registry = get_engine_registry()
    engines = {
        "acme_df": PluginCapabilities(engine="acme_df", dataframe=True),
    }
    assert registry.is_dataframe_engine("acme_df", engines)
    assert (
        registry.resolve_execution_family("acme_df", engines)
        is ExecutionFamily.DATAFRAME
    )


def test_builtin_polars_fallback_without_registration() -> None:
    registry = get_engine_registry()
    assert registry.is_dataframe_engine("polars")
    assert registry.is_dataframe_engine("polars", engines={})
    assert registry.resolve_execution_family("polars") is ExecutionFamily.DATAFRAME


def test_unknown_engine_without_capabilities_is_not_dataframe() -> None:
    registry = get_engine_registry()
    assert not registry.is_dataframe_engine("acme_unknown")
    assert not registry.is_dataframe_engine("acme_unknown", engines={})
    assert registry.resolve_execution_family("acme_unknown") is None


def test_scheduler_registration_does_not_claim_dataframe_execution() -> None:
    scheduler = cast(
        ExecutionScheduler,
        SimpleNamespace(
            info=SimpleNamespace(
                name="acme_scheduler",
                version="1.0.0",
                direct_execution=True,
                external_compilation=False,
                scheduler_protocol="etlantic.scheduler/1",
            )
        ),
    )
    registry = RegistryBundle()

    register_discovered_plugins(registry, plugins={"acme_scheduler": scheduler})

    assert not registry.engines["acme_scheduler"].dataframe
    assert not get_engine_registry().is_dataframe_engine("acme_scheduler", registry)
    assert (
        get_engine_registry().resolve_execution_family("acme_scheduler", registry)
        is ExecutionFamily.SCHEDULER
    )


def test_discover_planning_predicates_for_third_party_dataframe() -> None:
    assert should_discover_dataframe_plugins("acme_df")
    assert should_include_transform_compilers("acme_df", None)
    assert not should_discover_dataframe_plugins("local")
    assert not should_discover_dataframe_plugins("null")
    assert not should_discover_dataframe_plugins("")


def test_discover_planning_predicates_sql_and_spark() -> None:
    assert should_discover_sql_plugins("sql")
    assert should_discover_sql_plugins("acme_sql")
    assert not should_discover_sql_plugins("local")
    assert not should_discover_sql_plugins(None)

    assert should_discover_spark_plugins("pyspark")
    assert should_discover_spark_plugins("acme_spark")
    assert not should_discover_spark_plugins(None)
    assert should_include_transform_compilers("local", "acme_spark")


def test_capability_backed_spark_and_sql_identity() -> None:
    registry = get_engine_registry()
    engines = {
        "acme_spark": PluginCapabilities(
            engine="acme_spark", dataframe=False, spark=True
        ),
        "acme_sql": PluginCapabilities(engine="acme_sql", dataframe=False, sql=True),
    }
    assert registry.is_spark_engine("acme_spark", engines)
    assert registry.is_sql_engine("acme_sql", engines)
    assert (
        registry.resolve_execution_family("acme_spark", engines)
        is ExecutionFamily.SPARK
    )
    assert registry.resolve_execution_family("acme_sql", engines) is ExecutionFamily.SQL


def test_sql_exec_is_sql_engine_uses_capabilities() -> None:
    from etlantic.runtime.sql_exec import is_sql_engine

    engines = {
        "acme_sql": PluginCapabilities(engine="acme_sql", dataframe=False, sql=True),
    }
    assert is_sql_engine("acme_sql", engines)
    assert is_sql_engine("sql")
    assert not is_sql_engine("acme_unknown", engines={})


def test_ownership_from_capabilities_not_engine_name() -> None:
    from etlantic.dataframe.protocol import ArtifactOwnership
    from etlantic.runtime.dataframe_exec import ownership_for_engine

    unsafe = PluginCapabilities(engine="acme_df", dataframe=True, thread_safe=False)
    safe = PluginCapabilities(engine="acme_df", dataframe=True, thread_safe=True)
    assert (
        ownership_for_engine("acme_df", capabilities=unsafe) is ArtifactOwnership.COPIED
    )
    assert (
        ownership_for_engine("acme_df", capabilities=safe) is ArtifactOwnership.SHARED
    )
    assert (
        ownership_for_engine(
            "pandas",
            capabilities=PluginCapabilities(
                engine="pandas", dataframe=True, thread_safe=True
            ),
        )
        is ArtifactOwnership.SHARED
    )


def test_region_strategy_for_capability_spark_engine() -> None:
    from etlantic.model import LogicalGraph, Node, NodeKind, PortSpec
    from etlantic.plan.planner import _form_regions
    from etlantic.registry import ImplementationDescriptor

    engines = {
        "acme_spark": PluginCapabilities(
            engine="acme_spark", dataframe=False, spark=True, lazy=True
        ),
    }
    graph = LogicalGraph(
        pipeline_id="p",
        pipeline_name="P",
        nodes=(
            Node(
                name="step",
                kind=NodeKind.STEP,
                identity="step",
                inputs=(),
                outputs=(
                    PortSpec(
                        name="result",
                        direction="output",
                        contract_type=None,
                        contract_id=None,
                    ),
                ),
            ),
        ),
        edges=(),
    )
    implementations = {
        "step": ImplementationDescriptor(
            transformation_id="t",
            engine="acme_spark",
            identity="impl:acme_spark",
            kind="spark",
        ),
    }
    regions = _form_regions(
        graph,
        implementations,
        default_engine="acme_spark",
        security_domain="default",
        engines=engines,
    )
    assert len(regions) == 1
    assert regions[0].engine == "acme_spark"
    assert regions[0].metadata.get("strategy") == "lazy_dataframe"


def test_interchange_copy_from_thread_safe_not_pandas_name() -> None:
    from etlantic.plan.planner import _interchange_descriptor

    unsafe = PluginCapabilities(engine="acme_a", dataframe=True, thread_safe=False)
    safe = PluginCapabilities(engine="acme_b", dataframe=True, thread_safe=True)
    desc = _interchange_descriptor(
        producer_engine="acme_a",
        consumer_engine="acme_b",
        producer_capabilities=unsafe,
        consumer_capabilities=safe,
        contract_id=None,
    )
    assert desc.ownership == "copied"

    # Engine name "pandas" is not privileged: thread_safe producer stays shared.
    desc_safe = _interchange_descriptor(
        producer_engine="pandas",
        consumer_engine="polars",
        producer_capabilities=PluginCapabilities(
            engine="pandas", dataframe=True, thread_safe=True
        ),
        consumer_capabilities=PluginCapabilities(
            engine="polars", dataframe=True, thread_safe=True
        ),
        contract_id=None,
    )
    assert desc_safe.ownership == "shared"
