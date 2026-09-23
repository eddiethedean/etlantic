# pyright: reportAttributeAccessIssue=false, reportMissingImports=false, reportMissingParameterType=false, reportMissingTypeStubs=false, reportPossiblyUnboundVariable=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Native panic and deadline lifecycle regressions without unsafe source inputs."""

# ruff: noqa: E402

from __future__ import annotations

import asyncio
import json
import threading
from contextlib import contextmanager

import anyio
import pytest

pl = pytest.importorskip("polars")
pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

from tests.runtime.physical.test_fusion_0_54 import _seed, setup

from etlantic.exceptions import PipelineCancelledError
from etlantic.io_policy import SafeIoPolicy
from etlantic.plan.adaptive_model import AdaptivePipelinePlan
from etlantic.runtime.artifacts import ArtifactStore
from etlantic.runtime.events import LifecycleEvent
from etlantic.runtime.request import RunRequest, TimeoutPolicy
from etlantic.runtime.scheduler import LocalScheduler
from etlantic_polars import create_parquet_storage, create_transform_compiler
from etlantic_polars.compiler import PolarsTransformCompiler

pytestmark = [pytest.mark.polars, pytest.mark.pandas]


@pytest.mark.parametrize(
    "error_class", [SystemExit, KeyboardInterrupt, asyncio.CancelledError]
)
def test_fused_boundary_never_translates_control_flow(
    tmp_path, monkeypatch, error_class
):
    from etlantic.runtime.fused_execution import execute_fused_scan
    from etlantic.transform.fusion import FusionDescriptor

    _seed(tmp_path)
    _, _, _, plan = setup(tmp_path)
    assert isinstance(plan, AdaptivePipelinePlan)
    unit = next(u for u in plan.physical_dag.units if u.metadata.get("etlantic.fusion"))
    descriptor = FusionDescriptor.from_dict(unit.metadata["etlantic.fusion"])

    class InlineNative:
        async def run(self, operation):
            return operation()

    def stop(*args, **kwargs):
        raise error_class("control-flow-canary")

    monkeypatch.setattr(PolarsTransformCompiler, "compile_fusion", stop)

    async def exercise():
        with pytest.raises(error_class):
            await execute_fused_scan(
                descriptor,
                compiler=create_transform_compiler(),
                source=create_parquet_storage(),
                context={"safe_io": SafeIoPolicy.for_root(tmp_path)},
                pipeline_id=plan.pipeline_id,
                plan_id=plan.plan_id,
                profile_name=plan.profile_name,
                run_id="control-flow",
                native=InlineNative(),
            )

    anyio.run(exercise)


@pytest.mark.parametrize("deadline", ["step", "run"])
def test_caller_cancellation_before_deadline_remains_cancelled_after_drain(
    tmp_path, monkeypatch, deadline
):
    _seed(tmp_path)
    entered, release, drained = threading.Event(), threading.Event(), threading.Event()
    original_collect = pl.LazyFrame.collect
    original_timeout = anyio.fail_after
    scopes = []

    @contextmanager
    def synchronized_timeout(seconds, *, shield=False):
        with original_timeout(seconds, shield=shield) as scope:
            if seconds == 1.0:
                scopes.append(scope)
            yield scope

    def collect(self, *args, **kwargs):
        entered.set()
        try:
            assert release.wait(10), "release owned worker"
            return original_collect(self, *args, **kwargs)
        finally:
            drained.set()

    monkeypatch.setattr(anyio, "fail_after", synchronized_timeout)
    monkeypatch.setattr(pl.LazyFrame, "collect", collect)

    async def exercise():
        request = RunRequest(timeout=TimeoutPolicy(**{f"{deadline}_seconds": 1.0}))
        runtime, _, _, plan = setup(tmp_path, request)
        artifacts = ArtifactStore()
        task = asyncio.create_task(
            LocalScheduler().execute(
                plan,
                request=request,
                runtime=runtime,
                workspace=tmp_path,
                artifact_store=artifacts,
            )
        )
        try:
            with original_timeout(10):
                while not entered.is_set():
                    await anyio.sleep(0.001)
            assert len(scopes) == 1
            assert anyio.current_time() < scopes[0].deadline
            task.cancel()
            await anyio.sleep_until(scopes[0].deadline + 0.03)
        finally:
            release.set()
        with pytest.raises(PipelineCancelledError) as caught:
            await task
        assert caught.value.code == "PMEXEC409"
        assert drained.is_set()
        report = caught.value.report
        assert runtime.reports.get(report.run_id) is report
        assert report.status.value == "cancelled"
        for name in ("raw", "filtered", "projected"):
            state = next(s for s in report.steps if s.step_name == name)
            assert state.status.value == "cancelled"
            terminal = [
                e
                for e in runtime.events.events
                if isinstance(e, LifecycleEvent)
                and e.step_name == name
                and e.kind == "step_failed"
            ]
            assert len(terminal) == 1 and terminal[0].status == "cancelled"
        assert not artifacts.has("projected.result")
        assert runtime.memory.get("out") == []

    anyio.run(exercise)


@pytest.mark.parametrize("boundary", ["compile", "collect"])
def test_known_native_panic_delivers_sanitized_terminal_report(
    tmp_path, monkeypatch, capsys, boundary
):
    _seed(tmp_path)
    assert not issubclass(pl.exceptions.PanicException, Exception)

    def panic(*args, **kwargs):
        # Construct the actual native exception class, without triggering Rust
        # panic hooks that would print source/provider data to stderr.
        raise pl.exceptions.PanicException("native-private-payload-canary")

    monkeypatch.setattr(
        PolarsTransformCompiler if boundary == "compile" else pl.LazyFrame,
        "compile_fusion" if boundary == "compile" else "collect",
        panic,
    )

    async def exercise():
        runtime, _, _, plan = setup(tmp_path)
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
        )
        assert report.status.value == "failed"
        assert runtime.reports.get(report.run_id) is report
        assert any(e.kind == "run_failed" for e in runtime.events.events)
        statuses = {s.step_name: s.status.value for s in report.steps}
        assert statuses["filtered" if boundary == "compile" else "raw"] == "failed"
        assert statuses["projected"] == statuses["out"] == "skipped"
        assert all(s.status.value not in {"running", "pending"} for s in report.steps)
        assert "canary" not in json.dumps(report.to_dict())
        assert "canary" not in json.dumps([e.to_dict() for e in runtime.events.events])
        assert runtime.memory.get("out") == []
        assert not list(tmp_path.glob("etlantic-parquet-*"))

    anyio.run(exercise)
    assert "canary" not in capsys.readouterr().err


def test_native_timeout_is_not_sanitized_into_source_failure(tmp_path, monkeypatch):
    _seed(tmp_path)

    def timeout(*args, **kwargs):
        raise TimeoutError("private-timeout-canary")

    monkeypatch.setattr(pl.LazyFrame, "collect", timeout)

    async def exercise():
        runtime, _, _, plan = setup(tmp_path)
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
        )
        assert report.status.value == "failed"
        assert all(
            s.status.value == "timed_out"
            for s in report.steps
            if s.step_name in {"raw", "filtered", "projected"}
        ), [(s.step_name, s.status.value) for s in report.steps]
        assert "canary" not in json.dumps(report.to_dict())
        assert runtime.memory.get("out") == []

    anyio.run(exercise)


@pytest.mark.parametrize("deadline", ["step", "run"])
def test_fused_deadline_all_active_members_timed_out_and_no_late_publication(
    tmp_path, monkeypatch, deadline
):
    _seed(tmp_path)
    entered, release, drained = threading.Event(), threading.Event(), threading.Event()
    original_collect = pl.LazyFrame.collect
    original_timeout = anyio.fail_after
    scopes = []

    @contextmanager
    def synchronized_timeout(seconds, *, shield=False):
        with original_timeout(seconds, shield=shield) as scope:
            if seconds == 0.5:
                scopes.append(scope)
            yield scope

    def collect(self, *args, **kwargs):
        entered.set()
        try:
            assert release.wait(10), "release owned worker"
            return original_collect(self, *args, **kwargs)
        finally:
            drained.set()

    monkeypatch.setattr(anyio, "fail_after", synchronized_timeout)
    monkeypatch.setattr(pl.LazyFrame, "collect", collect)

    async def exercise():
        request = RunRequest(timeout=TimeoutPolicy(**{f"{deadline}_seconds": 0.5}))
        runtime, _, _, plan = setup(tmp_path, request)
        artifacts = ArtifactStore()

        async def expire_and_release():
            try:
                with original_timeout(10):
                    while not entered.is_set():
                        await anyio.sleep(0.001)
                assert len(scopes) == 1
                await anyio.sleep_until(scopes[0].deadline + 0.03)
            finally:
                release.set()

        async with anyio.create_task_group() as tasks:
            tasks.start_soon(expire_and_release)
            report = await LocalScheduler().execute(
                plan,
                request=request,
                runtime=runtime,
                workspace=tmp_path,
                artifact_store=artifacts,
            )
        assert drained.is_set()
        assert report.status.value == "failed"
        statuses = {s.step_name: s.status.value for s in report.steps}
        for name in ("raw", "filtered", "projected"):
            assert statuses[name] == "timed_out"
            terminal = [
                e
                for e in runtime.events.events
                if isinstance(e, LifecycleEvent)
                and e.step_name == name
                and e.kind == "step_failed"
            ]
            assert len(terminal) == 1 and terminal[0].status == "timed_out"
        assert all(s.status.value not in {"running", "pending"} for s in report.steps)
        assert not artifacts.has("projected.result")
        assert runtime.memory.get("out") == []
        assert not list(tmp_path.glob("etlantic-parquet-*"))

    anyio.run(exercise)
