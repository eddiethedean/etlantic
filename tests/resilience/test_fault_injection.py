"""WP3: deterministic failure injection at runtime boundaries."""

from __future__ import annotations

import os

import pytest

from etlantic.runtime.faults import (
    FaultBoundary,
    FaultSpec,
    FaultTrigger,
    active_faults,
    fault_injection_enabled,
    maybe_inject,
    reset_fault_counts,
)
from etlantic.testing.faults import with_faults


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
    with with_faults(
        FaultSpec(boundary=FaultBoundary.EXTRACT, message="boom", error=ValueError)
    ):
        with pytest.raises(ValueError, match="boom"):
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
    with with_faults(FaultSpec(boundary=boundary, message=f"{boundary}-fail")):
        with pytest.raises(RuntimeError, match=f"{boundary}-fail"):
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
    with with_faults(
        FaultSpec(boundary=FaultBoundary.REPORT_PERSIST, message="persist-fail")
    ):
        with pytest.raises(RuntimeError, match="persist-fail"):
            store.put(report)
    # In-memory index may still hold report from partial put depending on order;
    # durable write must not succeed when fault fires before write.
    assert not (tmp_path / "run-1.json").exists()
