"""Additional 0.23 resilience correctness fixes."""

from __future__ import annotations

from datetime import UTC, datetime

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
from etlantic.io_policy import SafeIoPolicy
from etlantic.reports.file_store import FileReportStore
from etlantic.reports.model import PipelineRunReport, RunSummary
from etlantic.runtime.faults import (
    FaultBoundary,
    FaultSpec,
    active_faults,
    fault_injection_enabled,
    maybe_inject,
)
from etlantic.runtime.orchestrator import LocalOrchestrator
from etlantic.runtime.request import (
    CancellationPolicy,
    RetryPolicy,
    RunIntent,
    RunRequest,
)
from etlantic.runtime.state import RunStatus, StepStatus
from etlantic.testing.faults import with_faults


class Row(Data):
    id: int


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("local")
def identity_local(rows: list[Row]) -> list[Row]:
    return list(rows)


class SimplePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")


def test_active_faults_without_env_does_not_fire(monkeypatch) -> None:
    monkeypatch.delenv("ETLANTIC_FAULT_INJECTION", raising=False)
    assert not fault_injection_enabled()
    with active_faults(FaultSpec(boundary=FaultBoundary.EXTRACT, message="nope")):
        assert not fault_injection_enabled()
        maybe_inject(FaultBoundary.EXTRACT)  # no-op without env arming


def test_file_report_store_durable_fail_keeps_memory_clean(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ETLANTIC_FAULT_INJECTION", "1")
    store = FileReportStore(tmp_path, policy=SafeIoPolicy.for_root(tmp_path))
    report = PipelineRunReport(
        pipeline_id="p",
        plan_id="plan",
        run_id="run-durable-fail",
        intent=RunIntent.STANDARD,
        profile="development",
        status=RunStatus.SUCCEEDED,
        started_at=datetime.now(UTC),
        summary=RunSummary(),
    )
    with (
        with_faults(
            FaultSpec(boundary=FaultBoundary.REPORT_PERSIST, message="disk-full")
        ),
        pytest.raises(RuntimeError, match="disk-full"),
    ):
        store.put(report)
    assert store.get("run-durable-fail") is None
    assert not (tmp_path / "run-durable-fail.json").exists()


def test_cleanup_fault_still_writes_terminal_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ETLANTIC_FAULT_INJECTION", "1")
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    store = FileReportStore(tmp_path)
    runtime.reports = store  # type: ignore[assignment]
    plan = SimplePipeline.plan(profile="development")
    request = RunRequest(intent=RunIntent.STANDARD)

    async def _run() -> None:
        with with_faults(
            FaultSpec(boundary=FaultBoundary.CLEANUP, message="cleanup-boom")
        ):
            orch = LocalOrchestrator(
                runtime=runtime,
                plan=plan,
                request=request,
                pipeline_cls=SimplePipeline,
            )
            with pytest.raises(PipelineExecutionError) as exc_info:
                await orch.execute()
            assert exc_info.value.code == "PMEXEC412"
            assert orch._persistence.terminal_reports_written >= 1

    anyio.run(_run)
    reports = store.list()
    assert len(reports) == 1
    assert reports[0].status == RunStatus.FAILED


def test_attempt_cleanup_failure_does_not_retry_success(monkeypatch) -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    plan = SimplePipeline.plan(profile="development")
    request = RunRequest(
        intent=RunIntent.STANDARD,
        retry=RetryPolicy(max_attempts=3),
    )

    async def _run() -> None:
        orch = LocalOrchestrator(
            runtime=runtime,
            plan=plan,
            request=request,
            pipeline_cls=SimplePipeline,
        )
        real_cleanup = runtime.resources.cleanup_scope

        async def cleanup_scope(scope: str, scope_key: str = "") -> None:
            if scope == "attempt":
                raise RuntimeError("attempt-cleanup-boom")
            await real_cleanup(scope, scope_key)

        monkeypatch.setattr(runtime.resources, "cleanup_scope", cleanup_scope)
        report = await orch.execute()
        assert report.status == RunStatus.SUCCEEDED
        step = next(s for s in report.steps if s.step_name == "step")
        assert step.status == StepStatus.SUCCEEDED
        assert step.attempts == 1
        assert any(d.code == "PMEXEC414" for d in report.diagnostics)

    anyio.run(_run)


def test_cancellation_policy_abandon_after_fails_closed() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    plan = SimplePipeline.plan(profile="development")
    request = RunRequest(
        intent=RunIntent.STANDARD,
        cancellation=CancellationPolicy(abandon_after_seconds=1.0),
    )
    orch = LocalOrchestrator(
        runtime=runtime,
        plan=plan,
        request=request,
        pipeline_cls=SimplePipeline,
    )

    async def _run() -> None:
        with pytest.raises(PipelineExecutionError) as exc_info:
            await orch.execute()
        assert exc_info.value.code == "PMEXEC411"

    anyio.run(_run)


def test_safe_io_policy_rejects_invalid_enums() -> None:
    with pytest.raises(ValueError, match="symlink_policy"):
        SafeIoPolicy.from_dict({"symlink_policy": "allow_everything"})
    with pytest.raises(ValueError, match="overwrite_policy"):
        SafeIoPolicy.from_dict({"overwrite_policy": "clobber"})
