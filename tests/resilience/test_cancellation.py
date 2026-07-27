"""WP4: cancellation produces one terminal report without duplicate writes."""

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
from etlantic.runtime.faults import FaultBoundary, FaultSpec
from etlantic.runtime.orchestrator import LocalOrchestrator
from etlantic.runtime.request import RunIntent, RunRequest, TimeoutPolicy
from etlantic.runtime.state import RunStatus
from etlantic.testing.faults import with_faults


class Row(Data):
    id: int


class Slow(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Slow.implementation("local")
async def slow_local(rows: list[Row]) -> list[Row]:
    await anyio.sleep(10)
    return rows


class CancelPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Slow.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")


def test_cancelled_run_emits_one_terminal_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ETLANTIC_FAULT_INJECTION", "1")
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    store = FileReportStore(tmp_path)
    runtime.reports = store  # type: ignore[assignment]

    plan = CancelPipeline.plan(profile="development")
    request = RunRequest(
        intent=RunIntent.STANDARD,
        timeout=TimeoutPolicy(run_seconds=0.2),
    )
    orch = LocalOrchestrator(
        runtime=runtime,
        plan=plan,
        request=request,
        pipeline_cls=CancelPipeline,
    )

    async def _run() -> None:
        with pytest.raises((PipelineTimeoutError, PipelineExecutionError)):
            await orch.execute()

    anyio.run(_run)

    reports = store.list()
    assert len(reports) == 1
    assert reports[0].status == RunStatus.TIMED_OUT
    incomplete = {"pending", "ready", "running", "retrying"}
    assert all(s.status.value not in incomplete for s in reports[0].steps)


def test_report_persist_fault_after_publication_marks_failed(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ETLANTIC_FAULT_INJECTION", "1")

    class Quick(Transformation):
        rows: Input[Row]
        result: Output[Row]

    @Quick.implementation("local")
    def quick(rows: list[Row]) -> list[Row]:
        return rows

    class P(Pipeline):
        raw: Extract[Row] = Extract(asset="rows")
        step = Quick.step(rows=raw)
        out: Load[Row] = Load(input=step.result, asset="out")

    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    store = FileReportStore(tmp_path)
    runtime.reports = store  # type: ignore[assignment]

    plan = P.plan(profile="development")
    request = RunRequest(intent=RunIntent.STANDARD)

    async def _run() -> None:
        with with_faults(
            FaultSpec(boundary=FaultBoundary.REPORT_PERSIST, message="persist-boom")
        ):
            orch = LocalOrchestrator(
                runtime=runtime, plan=plan, request=request, pipeline_cls=P
            )
            with pytest.raises(PipelineExecutionError) as exc_info:
                await orch.execute()
            assert exc_info.value.code == "PMEXEC410"

    anyio.run(_run)

    reports = store.list()
    assert len(reports) == 1
    assert reports[0].status == RunStatus.FAILED
    assert any(d.code == "PMEXEC410" for d in reports[0].diagnostics)
