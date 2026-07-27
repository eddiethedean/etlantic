"""Optional Polars-to-Pandas runtime interchange integration test."""

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
from etlantic.dataframe.discovery import register_discovered_plugins
from etlantic.interchange.tabular import InterchangeEvidence, InterchangeMechanism
from etlantic.interchange.tabular.execute import boundary_for_input
from etlantic.interchange.tabular.reconcile import reconcile_interchange_evidence
from etlantic.lifecycle import PipelineRuntime
from etlantic.profile import Profile
from etlantic.registry import PlanningContext, builtin_stub_registry
from etlantic.runtime import RunStatus

pd = pytest.importorskip("pandas")
if not hasattr(pd, "DataFrame"):
    pytest.skip("installed pandas module has no DataFrame", allow_module_level=True)
pl = pytest.importorskip("polars")
if not hasattr(pl, "DataFrame"):
    pytest.skip("installed polars module has no DataFrame", allow_module_level=True)

etlantic_pandas = pytest.importorskip("etlantic_pandas")
etlantic_polars = pytest.importorskip("etlantic_polars")


class _Row(Data):
    value: int


class _PolarsIdentity(Transformation):
    rows: Input[_Row]
    result: Output[_Row]


@_PolarsIdentity.implementation("polars")
def _polars_identity(rows):
    assert isinstance(rows, pl.DataFrame)
    return rows


class _PandasIdentity(Transformation):
    rows: Input[_Row]
    result: Output[_Row]


@_PandasIdentity.implementation("pandas")
def _pandas_identity(rows):
    assert isinstance(rows, pd.DataFrame)
    return rows


class _CrossEnginePipeline(Pipeline):
    raw: Extract[_Row] = Extract(asset="rows")
    polars_step = _PolarsIdentity.step(rows=raw)
    pandas_step = _PandasIdentity.step(rows=polars_step.result)
    out: Load[_Row] = Load(input=pandas_step.result, asset="out")


def test_polars_to_pandas_pipeline_honors_planned_interchange() -> None:
    plugins = {
        "polars": etlantic_polars.create_plugin(),
        "pandas": etlantic_pandas.create_plugin(),
    }
    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins=plugins)
    profile = Profile(
        name="cross-engine",
        dataframe_engine="polars",
        implementation_overrides={"pandas_step": "pandas"},
        portable_transform_policy="native",
    )
    context = PlanningContext.create(profile=profile, registry=registry)
    runtime = PipelineRuntime(registry=registry, dataframe_plugins=plugins)
    runtime.memory.seed("rows", [_Row(value=1), _Row(value=2)])

    plan = _CrossEnginePipeline.plan(profile=profile, context=context)
    descriptor = boundary_for_input(plan, "pandas_step", "rows")
    assert descriptor is not None

    report = _CrossEnginePipeline.run(
        profile=profile,
        context=context,
        runtime=runtime,
    )

    assert report.status is RunStatus.SUCCEEDED
    assert [row.value for row in runtime.memory.get("out")] == [1, 2]

    pandas_step = next(s for s in report.steps if s.step_name == "pandas_step")
    dataframe_meta = pandas_step.metadata.get("dataframe") or {}
    evidence_items = (dataframe_meta.get("extras") or {}).get("interchange_evidence")
    assert evidence_items
    observed_raw = evidence_items[0]
    observed = InterchangeEvidence(
        evidence_id=observed_raw["evidence_id"],
        mechanism=InterchangeMechanism(observed_raw["mechanism"]),
        copy_observed=observed_raw["copy_observed"],
        zero_copy_reported=observed_raw["zero_copy_reported"],
        fallback_reason=observed_raw.get("fallback_reason"),
        cleanup_status=observed_raw["cleanup_status"],
        notes=observed_raw.get("notes") or "",
    )
    result = reconcile_interchange_evidence(descriptor, observed)
    assert result.ok
