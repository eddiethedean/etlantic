"""WP4: timeout produces one terminal report."""

from __future__ import annotations

import anyio
import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Transformation,
)
from etlantic.exceptions import PipelineExecutionError, PipelineTimeoutError
from etlantic.reports.file_store import FileReportStore
from etlantic.runtime.orchestrator import LocalOrchestrator
from etlantic.runtime.request import RunIntent, RunRequest, TimeoutPolicy
from etlantic.runtime.state import RunStatus


class Row(Data):
    id: int


class Slow(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Slow.implementation("local")
async def slow_local(rows: list[Row]) -> list[Row]:
    await anyio.sleep(10)
    return rows


class TimeoutPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Slow.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")


def test_timed_out_run_emits_one_terminal_report(tmp_path) -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    store = FileReportStore(tmp_path)
    runtime.reports = store  # type: ignore[assignment]

    plan = TimeoutPipeline.plan(profile="development")
    request = RunRequest(
        intent=RunIntent.STANDARD,
        timeout=TimeoutPolicy(run_seconds=0.2),
    )
    orch = LocalOrchestrator(
        runtime=runtime,
        plan=plan,
        request=request,
        pipeline_cls=TimeoutPipeline,
    )

    async def _run() -> None:
        with pytest.raises((PipelineTimeoutError, PipelineExecutionError)):
            await orch.execute()

    anyio.run(_run)

    reports = store.list()
    assert len(reports) == 1
    assert reports[0].status == RunStatus.TIMED_OUT
    assert orch._persistence.terminal_reports_written == 1
