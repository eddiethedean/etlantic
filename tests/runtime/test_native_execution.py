"""Implementation-side checks of native work draining and cancellation."""

from __future__ import annotations

import threading
from typing import Any

import anyio
import pytest
from anyio.to_thread import current_default_thread_limiter, run_sync

from etlantic.runtime.native_execution import NativeExecution


@pytest.mark.parametrize("abandon_after", [None, 0.5])
def test_cancelled_native_work_drains_before_return(
    abandon_after: float | None,
) -> None:
    async def exercise() -> None:
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        obligations: list[dict[str, Any]] = []
        work = NativeExecution("unit", "member", 1, abandon_after, obligations)

        def operation() -> str:
            started.set()
            try:
                assert release.wait(timeout=2.0)
                return "late result"
            finally:
                finished.set()

        async def cancel_and_release(scope: anyio.CancelScope) -> None:
            while not started.is_set():
                await anyio.sleep(0.005)
            scope.cancel()
            await anyio.sleep(0.05)
            release.set()

        returned = False
        try:
            async with anyio.create_task_group() as tasks:
                with anyio.CancelScope() as scope:
                    tasks.start_soon(cancel_and_release, scope)
                    await work.run(operation)
                    returned = True
                assert scope.cancel_called
                assert finished.is_set()
                assert not returned
                assert obligations == []
        finally:
            release.set()
            if started.is_set():
                assert await run_sync(finished.wait, 2.0)

    anyio.run(exercise)


def test_cancelled_queued_native_work_never_starts() -> None:
    async def exercise() -> None:
        limiter = current_default_thread_limiter()
        original_tokens = limiter.total_tokens
        borrower = object()
        effects: list[str] = []
        obligations: list[dict[str, Any]] = []
        work = NativeExecution("unit", "member", 1, 0.1, obligations)
        limiter.total_tokens = 1
        await limiter.acquire_on_behalf_of(borrower)
        try:
            with anyio.move_on_after(0.05) as scope:
                await work.run(lambda: effects.append("started"))
            assert scope.cancel_called
        finally:
            limiter.release_on_behalf_of(borrower)
            limiter.total_tokens = original_tokens
        await anyio.sleep(0.05)
        assert effects == []
        assert obligations == []

    anyio.run(exercise)


@pytest.mark.polars
@pytest.mark.pandas
def test_external_native_cancellation_retains_terminal_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import etlantic_polars.compiler as compiler_module
    from etlantic.exceptions import PipelineCancelledError
    from etlantic.runtime.request import CancellationPolicy, RunRequest
    from etlantic.runtime.scheduler import LocalScheduler
    from etlantic_polars.lowering.actions import apply_action
    from tests.runtime.physical.test_qualification_0_53 import Chain, setup

    original = apply_action
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def operation(*args: Any, **kwargs: Any) -> Any:
        started.set()
        try:
            release.wait(timeout=2.0)
            return original(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(compiler_module, "apply_action", operation)

    async def exercise() -> None:
        request = RunRequest(
            cancellation=CancellationPolicy(abandon_after_seconds=0.05)
        )
        runtime, _, plan = setup(Chain, ("polars",), request)
        runtime.memory.seed("rows", [{"id": 1}])
        reports: list[Any] = []

        async def cancel_when_started(scope: anyio.CancelScope) -> None:
            while not started.is_set():
                await anyio.sleep(0.005)
            scope.cancel()

        try:
            async with anyio.create_task_group() as tasks:
                with anyio.CancelScope() as scope:
                    tasks.start_soon(cancel_when_started, scope)
                    try:
                        await LocalScheduler().execute(
                            plan, request=request, runtime=runtime
                        )
                    except PipelineCancelledError as exc:
                        reports.append(exc.report)
                assert len(reports) == 1
                report = reports[0]
                assert report.status.value == "cancelled"
                assert not finished.is_set()
                obligation = report.metadata["etlantic.cleanup_obligations"][0]
                assert (
                    obligation["unit_id"]
                    == plan.physical_dag.logical_to_physical["first"]
                )
                assert obligation["member"] == "first"
                assert obligation["attempt"] == 1
                assert obligation["code"] == "PMADP523"
                assert runtime.memory.get("out") == []
        finally:
            release.set()
            if started.is_set():
                assert await run_sync(finished.wait, 2.0)

    anyio.run(exercise)


@pytest.mark.polars
@pytest.mark.pandas
def test_deadline_during_output_validation_fences_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time

    from etlantic.runtime.request import RunRequest, TimeoutPolicy
    from etlantic.runtime.scheduler import LocalScheduler
    from tests.runtime.physical.test_qualification_0_53 import Chain, setup

    async def exercise() -> None:
        request = RunRequest(timeout=TimeoutPolicy(step_seconds=0.1))
        runtime, _, plan = setup(Chain, ("polars",), request)
        plugin = runtime.dataframe_plugins["polars"]
        original = plugin.validate_frame
        entered: list[str] = []

        def validate(*args: Any, **kwargs: Any) -> Any:
            if (
                kwargs.get("boundary") == "output_validation"
                and kwargs["context"].step_name == "first"
            ):
                entered.append("validation")
                time.sleep(0.3)
            return original(*args, **kwargs)

        monkeypatch.setattr(plugin, "validate_frame", validate)
        runtime.memory.seed("rows", [{"id": 1}])
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert entered
        first = next(s for s in report.steps if s.step_name == "first")
        assert first.status.value == "timed_out"
        assert first.attempts == 1
        assert next(
            s for s in report.steps if s.step_name == "second"
        ).status.value == ("skipped")
        assert runtime.memory.get("out") == []
        assert not any(a.logical_output == "first.result" for a in report.artifacts)
        # Native work and validation finished; there is no unresolved worker.
        assert report.metadata["etlantic.cleanup_obligations"] == []

    anyio.run(exercise)
