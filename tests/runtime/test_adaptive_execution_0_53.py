"""Executable local adaptive physical-DAG behavior for phase 0.53."""

from __future__ import annotations

import anyio
import pytest

from etlantic.exceptions import PipelineExecutionError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.planner import plan_pipeline
from etlantic.runtime.execute import arun_pipeline
from etlantic.runtime.request import RunRequest
from tests.plan.test_adaptive_planner_0_52 import Sample, adaptive_profile


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


def test_executable_adaptive_plan_is_distinct_from_planning_only_variant() -> None:
    planning = plan_pipeline(Sample, profile=adaptive_profile())
    executable = plan_pipeline(Sample, profile=adaptive_profile(), request=RunRequest())
    assert planning.metadata["etlantic.execution"] == "planning-only"
    assert executable.metadata["etlantic.execution"] == "local-static-batch/1"
    assert planning.fingerprint != executable.fingerprint
