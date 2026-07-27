"""Publication committed but report persistence fails with PMEXEC410."""

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
from etlantic.exceptions import PipelineExecutionError
from etlantic.reports.file_store import FileReportStore
from etlantic.runtime.faults import FaultBoundary, FaultSpec
from etlantic.runtime.orchestrator import LocalOrchestrator
from etlantic.runtime.request import RunIntent, RunRequest
from etlantic.runtime.state import RunStatus
from etlantic.testing.faults import with_faults


class Row(Data):
    id: int


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("local")
def identity_local(rows: list[Row]) -> list[Row]:
    return list(rows)


class PubPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")


def test_success_path_report_persist_fault_pmexec410(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ETLANTIC_FAULT_INJECTION", "1")
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    store = FileReportStore(tmp_path)
    runtime.reports = store  # type: ignore[assignment]

    plan = PubPipeline.plan(profile="development")
    request = RunRequest(intent=RunIntent.STANDARD)

    async def _run() -> None:
        with with_faults(
            FaultSpec(boundary=FaultBoundary.REPORT_PERSIST, message="persist-boom")
        ):
            orch = LocalOrchestrator(
                runtime=runtime,
                plan=plan,
                request=request,
                pipeline_cls=PubPipeline,
            )
            with pytest.raises(PipelineExecutionError) as exc_info:
                await orch.execute()
            assert exc_info.value.code == "PMEXEC410"
            assert orch._persistence.publication_committed
            assert not orch._persistence.report_persisted

    anyio.run(_run)

    reports = store.list()
    assert len(reports) <= 1
    if reports:
        assert reports[0].status == RunStatus.FAILED
        assert any(d.code == "PMEXEC410" for d in reports[0].diagnostics)
