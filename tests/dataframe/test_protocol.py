"""Core dataframe protocol unit tests (engine-free)."""

from __future__ import annotations

import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    Transformation,
)
from etlantic.capabilities import PluginCapabilities, negotiate_capabilities
from etlantic.dataframe import (
    DATAFRAME_PROTOCOL_VERSION,
    ArtifactOwnership,
    DataframeValidationPolicy,
)
from etlantic.dataframe.protocol import DATAFRAME_ENGINES, DataframeMetrics
from etlantic.exceptions import PipelineValidationError
from etlantic.plan import explain_plan, plan_pipeline
from etlantic.profile import Profile
from etlantic.registry import (
    PlanningContext,
    PluginDescriptor,
    RegistryBundle,
    builtin_stub_registry,
)
from etlantic.runtime.dataframe_exec import (
    is_dataframe_engine,
    ownership_for_engine,
)


class _Row(Data):
    id: int


class _Identity(Transformation):
    rows: Input[_Row]
    result: Output[_Row]


@_Identity.implementation("local")
def _identity_local(rows: list[_Row]) -> list[_Row]:
    return rows


@_Identity.implementation("polars")
def _identity_polars(rows):  # pragma: no cover - planning-only
    return rows


@_Identity.implementation("pandas")
def _identity_pandas(rows):  # pragma: no cover - planning-only
    return rows


class _LocalPipeline(Pipeline):
    raw: Extract[_Row] = Extract(asset="rows")
    step = _Identity.step(rows=raw)
    out: Load[_Row] = Load(input=step.result, asset="out")


class _PolarsOnly(Transformation):
    rows: Input[_Row]
    result: Output[_Row]


@_PolarsOnly.implementation("polars")
def _polars_only(rows):  # pragma: no cover
    return rows


class _PolarsPipeline(Pipeline):
    raw: Extract[_Row] = Extract(asset="rows")
    step = _PolarsOnly.step(rows=raw)
    out: Load[_Row] = Load(input=step.result, asset="out")


class _PandasOnly(Transformation):
    rows: Input[_Row]
    result: Output[_Row]


@_PandasOnly.implementation("pandas")
def _pandas_only(rows):  # pragma: no cover
    return rows


class _PandasPipeline(Pipeline):
    raw: Extract[_Row] = Extract(asset="rows")
    step = _PandasOnly.step(rows=raw)
    out: Load[_Row] = Load(input=step.result, asset="out")


def test_protocol_version() -> None:
    assert DATAFRAME_PROTOCOL_VERSION == "etlantic.dataframe/1"
    assert "polars" in DATAFRAME_ENGINES
    assert "pandas" in DATAFRAME_ENGINES


def test_expanded_capabilities_flags() -> None:
    caps = PluginCapabilities(
        engine="polars",
        dataframe=True,
        eager=True,
        lazy=True,
        arrow_import=True,
        schema_inspection=True,
    )
    assert caps.supports("lazy")
    assert caps.supports("arrow_import")
    assert not caps.supports("sql")
    restored = PluginCapabilities.from_dict(caps.to_dict())
    assert restored.lazy is True


def test_interchange_capabilities_round_trip_and_support() -> None:
    caps = PluginCapabilities(
        engine="custom",
        interchange_mechanisms=frozenset({"arrow_c_data"}),
    )
    restored = PluginCapabilities.from_dict(caps.to_dict())
    assert restored.interchange_mechanisms == frozenset({"arrow_c_data"})
    assert restored.supports("arrow_c_data")


def test_dataframe_engine_and_ownership_use_registered_capabilities() -> None:
    registry = RegistryBundle()
    caps = PluginCapabilities(
        engine="custom-frame",
        dataframe=True,
        thread_safe=True,
    )
    registry.register_plugin(
        PluginDescriptor(
            name="custom-frame",
            kind="dataframe",
            engine="custom-frame",
            capabilities=caps,
        )
    )
    registry.register_plugin(
        PluginDescriptor(
            name="kind-only-frame",
            kind="dataframe",
            engine="kind-only-frame",
        )
    )

    assert is_dataframe_engine("pandas")
    assert is_dataframe_engine("custom-frame", registry=registry)
    assert is_dataframe_engine("kind-only-frame", registry=registry)
    assert (
        ownership_for_engine("custom-frame", capabilities=caps)
        is ArtifactOwnership.SHARED
    )
    assert (
        ownership_for_engine(
            "custom-frame",
            capabilities=PluginCapabilities(
                engine="custom-frame",
                dataframe=True,
                thread_safe=False,
            ),
        )
        is ArtifactOwnership.COPIED
    )
    assert (
        ownership_for_engine("custom-frame", fan_out=True, capabilities=caps)
        is ArtifactOwnership.COPIED
    )
    assert (
        ownership_for_engine(
            "pandas",
            capabilities=PluginCapabilities(
                engine="pandas",
                dataframe=True,
                thread_safe=True,
            ),
        )
        is ArtifactOwnership.SHARED
    )
    assert (
        ownership_for_engine(
            "acme_df",
            capabilities=PluginCapabilities(
                engine="acme_df",
                dataframe=True,
                thread_safe=False,
            ),
        )
        is ArtifactOwnership.COPIED
    )


def test_local_registry_is_not_dataframe_engine() -> None:
    registry = builtin_stub_registry()
    assert registry.engines["local"].dataframe is False
    assert registry.plugins["local"].kind == "runtime"


def test_planning_context_auto_requires_dataframe_caps() -> None:
    registry = builtin_stub_registry()
    registry.register_plugin(
        PluginDescriptor(
            name="acme-lazy-df",
            kind="dataframe",
            version="0.23.0",
            engine="acme_lazy",
            capabilities=PluginCapabilities(
                engine="acme_lazy",
                dataframe=True,
                eager=True,
                lazy=True,
            ),
        )
    )
    ctx = PlanningContext.create(
        profile=Profile(name="p", dataframe_engine="acme_lazy"),
        registry=registry,
    )
    assert "dataframe" in ctx.required_capabilities
    assert "lazy" in ctx.required_capabilities


def test_plan_fails_without_polars_plugin() -> None:
    from etlantic.engines import get_engine_registry

    profile = Profile(name="p", dataframe_engine="polars")
    caps = get_engine_registry().default_capabilities(profile)
    context = PlanningContext(
        profile=profile,
        registry=builtin_stub_registry(),
        required_capabilities=caps,
    )
    with pytest.raises(PipelineValidationError) as exc:
        plan_pipeline(_PolarsPipeline, context=context)
    assert any(d.code in {"PMPLAN401", "PMPLAN410"} for d in exc.value.report.errors)


def test_pandas_fails_lazy_requirement() -> None:
    registry = RegistryBundle()
    registry.register_plugin(
        PluginDescriptor(
            name="etlantic-pandas",
            kind="dataframe",
            version="0.5.0",
            engine="pandas",
            capabilities=PluginCapabilities(
                engine="pandas",
                dataframe=True,
                eager=True,
                lazy=False,
            ),
        )
    )
    context = PlanningContext(
        profile=Profile(name="p", dataframe_engine="pandas"),
        registry=registry,
        required_capabilities=["dataframe", "eager", "lazy"],
    )
    with pytest.raises(PipelineValidationError) as exc:
        plan_pipeline(_PandasPipeline, context=context)
    assert any(d.code in {"PMPLAN402", "PMPLAN411"} for d in exc.value.report.errors)


def test_explain_includes_collection_metadata() -> None:
    plan = plan_pipeline(
        _LocalPipeline, context=PlanningContext.create(profile="development")
    )
    explained = explain_plan(plan)
    assert "collection_points" in explained
    assert "conversion_boundaries" in explained
    assert explained["dataframe_protocol"] == DATAFRAME_PROTOCOL_VERSION


def test_negotiate_lazy_unsupported() -> None:
    available = PluginCapabilities(
        engine="pandas", dataframe=True, eager=True, lazy=False
    )
    results = negotiate_capabilities(requirements=["lazy"], available=available)
    assert results[0].decision.value == "unsupported"


def test_validation_policy_roundtrip() -> None:
    policy = DataframeValidationPolicy.from_dict(
        {"input_outcome": "warn", "output_outcome": "reject"}
    )
    assert policy.to_dict()["input_outcome"] == "warn"
    assert ArtifactOwnership.COPIED.value == "copied"
    assert DataframeMetrics().to_dict()["collected"] is False
