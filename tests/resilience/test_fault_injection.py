"""WP3: deterministic failure injection at runtime boundaries."""

from __future__ import annotations

import pytest

from etlantic.runtime.faults import (
    FaultBoundary,
    FaultSpec,
    FaultTrigger,
    active_faults,
    fault_injection_enabled,
    maybe_inject,
    maybe_inject_async,
    reset_fault_counts,
)
from etlantic.testing.faults import with_faults

pl = pytest.importorskip("polars", reason="polars optional for dataframe fault test")
pytest.importorskip("etlantic_polars", reason="etlantic-polars optional")

from etlantic import (  # noqa: E402
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Transformation,
)
from etlantic.profile import Profile  # noqa: E402
from etlantic.runtime.orchestrator import LocalOrchestrator  # noqa: E402
from etlantic.runtime.request import RunIntent, RunRequest  # noqa: E402


class MaterializeRow(Data):
    id: int


class _PolarsIdentity(Transformation):
    rows: Input[MaterializeRow]
    result: Output[MaterializeRow]


@_PolarsIdentity.implementation("polars")
def _polars_identity(rows):  # type: ignore[no-untyped-def]
    return rows


class _MaterializePipeline(Pipeline):
    raw: Extract[MaterializeRow] = Extract(asset="rows")
    step = _PolarsIdentity.step(rows=raw)
    out: Load[MaterializeRow] = Load(input=step.result, asset="out")


@pytest.fixture(autouse=True)
def _enable_fault_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ETLANTIC_FAULT_INJECTION", "1")


def test_fault_injection_disabled_without_flag_or_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ETLANTIC_FAULT_INJECTION", raising=False)
    assert not fault_injection_enabled()
    maybe_inject(FaultBoundary.EXTRACT)  # no-op


def test_on_call_raises() -> None:
    with (
        with_faults(
            FaultSpec(boundary=FaultBoundary.EXTRACT, message="boom", error=ValueError)
        ),
        pytest.raises(ValueError, match="boom"),
    ):
        maybe_inject(FaultBoundary.EXTRACT)


@pytest.mark.parametrize(
    "boundary",
    [
        FaultBoundary.EXTRACT,
        FaultBoundary.CONVERT,
        FaultBoundary.TRANSFORM,
        FaultBoundary.VALIDATE,
        FaultBoundary.MATERIALIZE,
        FaultBoundary.LOAD,
        FaultBoundary.REPORT_PERSIST,
        FaultBoundary.CLEANUP,
        FaultBoundary.CALLBACK,
        FaultBoundary.OUTBOUND,
    ],
)
def test_each_boundary_can_fire(boundary: FaultBoundary) -> None:
    with (
        with_faults(FaultSpec(boundary=boundary, message=f"{boundary}-fail")),
        pytest.raises(RuntimeError, match=f"{boundary}-fail"),
    ):
        maybe_inject(boundary)


def test_after_n_calls_trigger() -> None:
    with active_faults(
        FaultSpec(
            boundary=FaultBoundary.LOAD,
            trigger=FaultTrigger.AFTER_N_CALLS,
            after_n=2,
            message="third-load",
        )
    ):
        reset_fault_counts()
        maybe_inject(FaultBoundary.LOAD)
        maybe_inject(FaultBoundary.LOAD)
        with pytest.raises(RuntimeError, match="third-load"):
            maybe_inject(FaultBoundary.LOAD)


def test_on_step_filter() -> None:
    with with_faults(
        FaultSpec(
            boundary=FaultBoundary.TRANSFORM,
            trigger=FaultTrigger.ON_STEP,
            step_name="Normalize",
            message="step-hit",
        )
    ):
        maybe_inject(FaultBoundary.TRANSFORM, step_name="Extract")
        with pytest.raises(RuntimeError, match="step-hit"):
            maybe_inject(FaultBoundary.TRANSFORM, step_name="Normalize")


def test_file_report_store_honors_report_persist_fault(tmp_path) -> None:
    from datetime import UTC, datetime

    from etlantic.io_policy import SafeIoPolicy
    from etlantic.reports.file_store import FileReportStore
    from etlantic.reports.model import PipelineRunReport, RunSummary
    from etlantic.runtime.request import RunIntent
    from etlantic.runtime.state import RunStatus

    store = FileReportStore(tmp_path, policy=SafeIoPolicy.for_root(tmp_path))
    report = PipelineRunReport(
        pipeline_id="p",
        plan_id="pl",
        run_id="run-1",
        intent=RunIntent.STANDARD,
        profile="development",
        status=RunStatus.SUCCEEDED,
        started_at=datetime.now(UTC),
        summary=RunSummary(total_steps=1),
    )
    with (
        with_faults(
            FaultSpec(boundary=FaultBoundary.REPORT_PERSIST, message="persist-fail")
        ),
        pytest.raises(RuntimeError, match="persist-fail"),
    ):
        store.put(report)
    # In-memory index may still hold report from partial put depending on order;
    # durable write must not succeed when fault fires before write.
    assert not (tmp_path / "run-1.json").exists()


@pytest.mark.polars
def test_materialize_fault_fires_during_dataframe_step() -> None:
    import anyio

    profile = Profile(name="polars-fault", dataframe_engine="polars")
    runtime = PipelineRuntime()
    runtime.ensure_plugins_for_profile(profile)
    runtime.memory.seed("rows", [MaterializeRow(id=1)])
    plan = _MaterializePipeline.plan(profile=profile)
    request = RunRequest(intent=RunIntent.STANDARD)

    async def _run() -> None:
        with with_faults(
            FaultSpec(
                boundary=FaultBoundary.MATERIALIZE,
                trigger=FaultTrigger.ON_STEP,
                step_name="step",
                message="materialize-boom",
            )
        ):
            orch = LocalOrchestrator(
                runtime=runtime,
                plan=plan,
                request=request,
                pipeline_cls=_MaterializePipeline,
            )
            report = await orch.execute()
            step = next(s for s in report.steps if s.step_name == "step")
            assert step.status.value == "failed"
            assert "materialize-boom" in (step.error or "")

    anyio.run(_run)


def test_delay_fault_does_not_block_event_loop() -> None:
    import anyio

    started = anyio.Event()
    done = anyio.Event()

    async def worker() -> None:
        started.set()
        await anyio.sleep(0.05)
        done.set()

    async def _run() -> None:
        async with anyio.create_task_group() as tg:
            tg.start_soon(worker)
            await started.wait()
            with (
                active_faults(
                    FaultSpec(
                        boundary=FaultBoundary.EXTRACT,
                        delay_seconds=0.05,
                        message="delayed-boom",
                    )
                ),
                pytest.raises(RuntimeError, match="delayed-boom"),
            ):
                await maybe_inject_async(FaultBoundary.EXTRACT)
            with anyio.fail_after(0.2):
                await done.wait()

    anyio.run(_run)


def test_after_n_calls_under_concurrency() -> None:
    import anyio

    async def _run() -> None:
        with active_faults(
            FaultSpec(
                boundary=FaultBoundary.LOAD,
                trigger=FaultTrigger.AFTER_N_CALLS,
                after_n=3,
                message="fourth-load",
            )
        ):
            reset_fault_counts()

            async def one() -> None:
                await maybe_inject_async(FaultBoundary.LOAD)

            async with anyio.create_task_group() as tg:
                for _ in range(4):
                    tg.start_soon(one)

    with pytest.raises(BaseException) as excinfo:
        anyio.run(_run)
    err = excinfo.value
    if hasattr(err, "exceptions"):
        assert any("fourth-load" in str(e) for e in err.exceptions)
    else:
        assert "fourth-load" in str(err)
