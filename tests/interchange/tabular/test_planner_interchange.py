# pyright: reportAttributeAccessIssue=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUnusedFunction=false
"""Planner coverage for dataframe interchange descriptors."""

from __future__ import annotations

import pytest

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.capabilities import PluginCapabilities
from etlantic.interchange.tabular import InterchangeDescriptorError
from etlantic.plan import PipelinePlan, explain_plan, plan_pipeline
from etlantic.profile import Profile
from etlantic.registry import PlanningContext, PluginDescriptor, builtin_stub_registry


class _Row(Data):
    value: int


class _PolarsStep(Transformation):
    rows: Input[_Row]
    result: Output[_Row]


@_PolarsStep.implementation("polars")
def _polars_step(rows):  # pragma: no cover - planning only
    return rows


class _PandasStep(Transformation):
    rows: Input[_Row]
    result: Output[_Row]


@_PandasStep.implementation("pandas")
def _pandas_step(rows):  # pragma: no cover - planning only
    return rows


class _CrossEnginePipeline(Pipeline):
    raw: Extract[_Row] = Extract(asset="rows")
    polars_step = _PolarsStep.step(rows=raw)
    pandas_step = _PandasStep.step(rows=polars_step.result)
    out: Load[_Row] = Load(input=pandas_step.result, asset="out")


def _context() -> PlanningContext:
    registry = builtin_stub_registry()
    for engine, thread_safe in (("polars", True), ("pandas", False)):
        registry.register_plugin(
            PluginDescriptor(
                name=f"etlantic-{engine}",
                kind="dataframe",
                engine=engine,
                capabilities=PluginCapabilities(
                    engine=engine,
                    dataframe=True,
                    lazy=engine == "polars",
                    arrow_import=True,
                    arrow_export=True,
                    thread_safe=thread_safe,
                    zero_copy=thread_safe,
                    interchange_mechanisms=frozenset({"arrow_c_data"}),
                ),
            )
        )
    return PlanningContext.create(
        profile=Profile(
            name="cross-engine",
            dataframe_engine="polars",
            implementation_overrides={"pandas_step": "pandas"},
            portable_transform_policy="native",
        ),
        registry=registry,
    )


def test_cross_engine_dataframe_boundary_has_interchange_descriptor(
    monkeypatch,
) -> None:
    monkeypatch.setattr("etlantic.dataframe.arrow.arrow_available", lambda: True)

    plan = plan_pipeline(_CrossEnginePipeline, context=_context())
    boundary = next(
        item
        for item in plan.materialization_boundaries
        if item.reason == "cross_engine" and item.producer_node == "polars_step"
    )
    descriptor = boundary.metadata["interchange"]

    assert descriptor["mechanism"] == "arrow_c_data"
    assert descriptor["producer_engine"] == "polars"
    assert descriptor["consumer_engine"] == "pandas"
    assert descriptor["collection"] is True
    assert len(descriptor["schema_fingerprint"]) == 64
    explained = next(
        item
        for item in explain_plan(plan)["conversion_boundaries"]
        if item["producer_node"] == "polars_step"
    )
    assert explained["interchange"] == descriptor


def test_plan_load_fails_closed_on_invalid_interchange(monkeypatch) -> None:
    monkeypatch.setattr("etlantic.dataframe.arrow.arrow_available", lambda: True)
    data = plan_pipeline(_CrossEnginePipeline, context=_context()).to_dict()
    boundary = next(
        item
        for item in data["materialization_boundaries"]
        if item["reason"] == "cross_engine" and "interchange" in item["metadata"]
    )
    boundary["metadata"]["interchange"]["mechanism"] = "invented"

    with pytest.raises(InterchangeDescriptorError):
        PipelinePlan.from_dict(data)
