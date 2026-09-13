"""Executable local adaptive physical-DAG behavior for phase 0.53."""

from __future__ import annotations

import anyio
import pytest

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.exceptions import PipelineExecutionError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.planner import plan_pipeline
from etlantic.planning.adaptive import _handoff_contract
from etlantic.profile import PlacementTarget, Profile
from etlantic.registry import PlanningContext, PluginDescriptor
from etlantic.runtime.execute import arun_pipeline
from etlantic.runtime.request import InvalidationMode, RunRequest
from tests.plan.test_adaptive_planner_0_52 import Sample, adaptive_profile


class CrossRow(Data):
    id: int


class CrossStep(Transformation):
    source: Input[CrossRow]
    result: Output[CrossRow]


@CrossStep.portable
def cross_project(source):
    return source.select("id")


class CrossPipeline(Pipeline):
    raw: Extract[CrossRow] = Extract(asset="cross-rows")
    step = CrossStep.step(source=raw)
    out: Load[CrossRow] = Load(input=step.result, asset="cross-out")


def test_executable_adaptive_plan_captures_request_and_runs_physical_units() -> None:
    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}, {"id": 2}])
        request = RunRequest(metadata={"concurrency": 1})
        report = await arun_pipeline(
            Sample,
            profile=adaptive_profile(),
            request=request,
            runtime=runtime,
        )
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("out")] == [1, 2]
        trace = report.metadata["etlantic.physical_trace"]
        assert [item["kind"] for item in trace] == [
            "compute",
            "compute",
            "publication",
        ]

    anyio.run(run)


def test_adaptive_unsupported_invalidation_rejects_before_runtime_effects() -> None:
    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        with pytest.raises(PipelineExecutionError) as error:
            await arun_pipeline(
                Sample,
                profile=adaptive_profile(),
                request=RunRequest(invalidation=InvalidationMode.TARGET),
                runtime=runtime,
            )
        assert error.value.code == "PMADP522"
        assert runtime.memory.get("out") == []

    anyio.run(run)


def test_adaptive_admission_rejects_invalid_concurrency_before_storage_effects() -> (
    None
):
    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        with pytest.raises(PipelineExecutionError) as error:
            await arun_pipeline(
                Sample,
                profile=adaptive_profile(),
                request=RunRequest(metadata={"concurrency": True}),
                runtime=runtime,
            )
        assert error.value.code == "PMADP522"
        assert runtime.memory.get("out") == []

    anyio.run(run)


def test_default_adaptive_plan_uses_executable_lowering() -> None:
    planning = plan_pipeline(Sample, profile=adaptive_profile())
    executable = plan_pipeline(Sample, profile=adaptive_profile(), request=RunRequest())
    assert planning.metadata["etlantic.execution"] == "local-static-batch/1"
    assert executable.metadata["etlantic.execution"] == "local-static-batch/1"
    assert planning.fingerprint == executable.fingerprint


def test_adaptive_physical_execution_routes_portable_polars_to_pandas() -> None:
    """A qualified directional handoff executes through the stored transfer."""
    polars = pytest.importorskip("etlantic_polars")
    pandas = pytest.importorskip("etlantic_pandas")

    targets = {
        "producer": PlacementTarget(engine="polars"),
        "consumer": PlacementTarget(engine="pandas"),
    }
    profile = Profile(
        name="adaptive-cross-runtime",
        execution_strategy="adaptive",
        portable_transform_policy="require",
        placement_targets=targets,
        eligible_targets=("producer", "consumer"),
        implementation_overrides={
            "raw": "producer",
            "step": "consumer",
            "out": "consumer",
        },
    )

    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.register_dataframe_plugin("polars", polars.create_plugin())
        runtime.register_dataframe_plugin("pandas", pandas.create_plugin())
        context = PlanningContext.create(profile, registry=runtime.registry)
        edge = CrossPipeline.build_graph().edges[0]
        evidence = _handoff_contract(
            targets["producer"], targets["consumer"], edge, context
        )
        evidence["evidence_ref"] = "sha256:" + ("a" * 64)
        context.registry.register_plugin(
            PluginDescriptor(
                name="cross-runtime-handoff",
                kind="handoff",
                version="1",
                metadata={"handoff_evidence": [evidence]},
            )
        )
        runtime.memory.seed("cross-rows", [{"id": 1}, {"id": 2}])
        report = await arun_pipeline(
            CrossPipeline,
            profile=profile,
            context=context,
            request=RunRequest(metadata={"concurrency": 1}),
            runtime=runtime,
        )
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("cross-out")] == [1, 2]
        trace = report.metadata["etlantic.physical_trace"]
        assert [item["kind"] for item in trace] == [
            "compute",
            "transfer",
            "compute",
            "compute",
            "publication",
        ]

    anyio.run(run)
