# pyright: reportAttributeAccessIssue=false, reportMissingImports=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Implementation-side checks of native work draining and cancellation."""

from __future__ import annotations

import threading
from pathlib import Path
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


@pytest.mark.polars
@pytest.mark.pandas
@pytest.mark.parametrize("member", ["raw", "first", "out"])
def test_complete_member_timeout_discards_private_outputs(member: str) -> None:
    import time

    from etlantic.runtime.artifacts import ArtifactStore
    from etlantic.runtime.request import RunRequest, TimeoutPolicy
    from etlantic.runtime.scheduler import LocalScheduler
    from tests.runtime.physical.test_qualification_0_53 import Chain, setup

    async def exercise() -> None:
        request = RunRequest(timeout=TimeoutPolicy(step_seconds=0.2))
        runtime, _, plan = setup(Chain, ("polars",), request)
        runtime.memory.seed("rows", [{"id": 1}])
        artifacts = ArtifactStore()
        entered: list[str] = []

        async def finish(context: Any, call_next: Any) -> None:
            await call_next()
            if context.step_name == member:
                entered.append(member)
                assert not artifacts.has(f"{member}.result")
                time.sleep(0.4)

        runtime.step_middleware.add(finish)
        report = await LocalScheduler().execute(
            plan, request=request, runtime=runtime, artifact_store=artifacts
        )
        assert entered == [member]
        step = next(s for s in report.steps if s.step_name == member)
        assert step.status.value == "timed_out"
        assert step.attempts == 1
        assert not artifacts.has(f"{member}.result")
        assert not any(a.logical_output == f"{member}.result" for a in report.artifacts)
        assert runtime.memory.get("out") == []
        assert report.status.value != "succeeded"
        assert report.metadata["etlantic.cleanup_obligations"] == []

    anyio.run(exercise)


@pytest.mark.polars
@pytest.mark.pandas
def test_external_cancellation_after_member_body_discards_output() -> None:
    from etlantic.exceptions import PipelineCancelledError
    from etlantic.runtime.artifacts import ArtifactStore
    from etlantic.runtime.request import RunRequest
    from etlantic.runtime.scheduler import LocalScheduler
    from tests.runtime.physical.test_qualification_0_53 import Chain, setup

    async def exercise() -> None:
        request = RunRequest()
        runtime, _, plan = setup(Chain, ("local",), request)
        runtime.memory.seed("rows", [{"id": 1}])
        artifacts = ArtifactStore()
        with anyio.CancelScope() as scope:

            async def cancel(context: Any, call_next: Any) -> None:
                await call_next()
                if context.step_name == "first":
                    assert not artifacts.has("first.result")
                    scope.cancel()

            runtime.step_middleware.add(cancel)
            with pytest.raises(PipelineCancelledError) as error:
                await LocalScheduler().execute(
                    plan, request=request, runtime=runtime, artifact_store=artifacts
                )
            assert error.value.report.status.value == "cancelled"
            assert not artifacts.has("first.result")
            assert runtime.memory.get("out") == []
        assert scope.cancel_called

    anyio.run(exercise)


def test_durable_attempt_deadline_restores_files_and_exposes_no_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    import etlantic.runtime.artifacts as artifact_module
    from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
    from etlantic.runtime.artifacts import ArtifactStore, AttemptArtifactStore

    original = artifact_module.write_json_safe
    existing = tmp_path / "existing.json"
    existing.write_bytes(b'[{"id": 99}]\r\n')
    old_bytes = existing.read_bytes()

    def persist(path: Path, *args: Any, **kwargs: Any) -> Any:
        result = original(path, *args, **kwargs)
        if path.name == "new.json":
            time.sleep(0.2)
        return result

    monkeypatch.setattr(artifact_module, "write_json_safe", persist)

    async def exercise() -> None:
        parent = ArtifactStore(workspace=tmp_path)
        attempt = AttemptArtifactStore(parent)
        for name in ("existing", "new"):
            attempt.put(
                ArtifactRef(name, f"member.{name}", ArtifactStrategy.DURABLE),
                [{"id": 1}],
                durable=True,
            )
        assert existing.read_bytes() == old_bytes
        assert not (tmp_path / "new.json").exists()
        with pytest.raises(TimeoutError), anyio.fail_after(0.1):
            await attempt.commit()
        assert parent.list_refs() == ()
        assert not parent.has("member.existing")
        assert not parent.has("member.new")
        assert existing.read_bytes() == old_bytes
        assert not (tmp_path / "new.json").exists()
        assert not attempt.cleanup_failed

    anyio.run(exercise)


def test_successful_attempt_publishes_all_ports_and_retains_borrowed_inputs(
    tmp_path: Path,
) -> None:
    import json

    from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
    from etlantic.runtime.artifacts import ArtifactStore, AttemptArtifactStore

    async def exercise() -> None:
        parent = ArtifactStore(workspace=tmp_path)
        borrowed = [{"id": 1}]
        parent.put(
            ArtifactRef("input", "source.result", ArtifactStrategy.IN_MEMORY),
            borrowed,
            ownership="shared",
        )
        attempt = AttemptArtifactStore(parent)
        assert attempt.get_raw("source.result") is borrowed
        assert attempt.ownership("source.result") == "shared"
        for name in ("left", "right"):
            attempt.put(
                ArtifactRef(name, f"member.{name}", ArtifactStrategy.DURABLE),
                borrowed,
                durable=True,
                ownership="borrowed",
            )
        assert len(parent.list_refs()) == 1
        await attempt.commit()
        attempt.clear()
        for name in ("left", "right"):
            assert parent.get_raw(f"member.{name}") is borrowed
            assert parent.ownership(f"member.{name}") == "borrowed"
            assert json.loads((tmp_path / f"{name}.json").read_text()) == borrowed
        assert parent.get_raw("source.result") is borrowed

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


@pytest.mark.polars
@pytest.mark.pandas
def test_run_deadline_fences_synchronous_physical_transfer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A delayed handoff cannot register a route or start its consumer."""
    import time

    from etlantic.runtime.request import RunRequest, TimeoutPolicy
    from etlantic.runtime.scheduler import LocalScheduler
    from tests.runtime.physical.test_qualification_0_53 import Chain, setup

    async def exercise() -> None:
        request = RunRequest(timeout=TimeoutPolicy(run_seconds=0.15))
        runtime, _, plan = setup(Chain, ("polars", "pandas"), request)
        runtime.memory.seed("rows", [{"id": 1}])
        plugin = runtime.dataframe_plugins["pandas"]
        original = plugin.materialize_input

        def delayed_handoff(*args: Any, **kwargs: Any) -> Any:
            converted = original(*args, **kwargs)
            if kwargs["context"].interchange is not None:
                time.sleep(0.3)
            return converted

        monkeypatch.setattr(plugin, "materialize_input", delayed_handoff)
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)

        assert report.status.value != "succeeded"
        assert runtime.memory.get("out") == []
        assert not any(a.logical_output == "second.source" for a in report.artifacts)
        assert next(
            s for s in report.steps if s.step_name == "second"
        ).status.value == ("skipped")
        assert any(d.code == "PMEXEC408" for d in report.diagnostics)

    anyio.run(exercise)


@pytest.mark.parametrize("subsequent_writer", [False, True])
def test_staged_checkpoint_deadline_restores_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, subsequent_writer: bool
) -> None:
    """Named boundary files roll back along with their unavailable refs."""
    import time

    import etlantic.runtime.artifacts as artifact_module
    from etlantic.io_policy import SafeIoPolicy
    from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
    from etlantic.runtime.artifacts import ArtifactStore, AttemptArtifactStore

    existing = tmp_path / "checkpoint-existing.json"
    existing.write_bytes(b'{"records": [{"id": 99}]}\r\n')
    old_bytes = existing.read_bytes()
    new = tmp_path / "checkpoint-new.json"
    original = artifact_module.write_text_safe
    deadline_scope: anyio.CancelScope

    def persist(path: Path, *args: Any, **kwargs: Any) -> Any:
        result = original(path, *args, **kwargs)
        if path == new:
            if subsequent_writer:
                original(existing, '{"records": [{"id": 2}]}', args[1])

            def expire_after_preparation() -> None:
                deadline_scope.deadline = anyio.current_time() + 0.1

            # Arm the deadline at the operation under test. Thread startup and
            # the first safe write must not consume the injected I/O budget.
            anyio.from_thread.run_sync(expire_after_preparation)
            time.sleep(0.2)
        return result

    monkeypatch.setattr(artifact_module, "write_text_safe", persist)

    async def exercise() -> None:
        nonlocal deadline_scope
        parent = ArtifactStore(workspace=tmp_path)
        borrowed = [{"id": 99}]
        parent.put(
            ArtifactRef("prior", "producer.result", ArtifactStrategy.IN_MEMORY),
            borrowed,
            ownership="borrowed",
        )
        pending = AttemptArtifactStore(parent)
        policy = SafeIoPolicy.for_root(tmp_path)
        for path in (existing, new):
            pending.stage_text(path, '{"records": [{"id": 1}]}', policy, run_id="run")
        pending.put(
            ArtifactRef(
                "checkpoint:run", "producer.result", ArtifactStrategy.IN_MEMORY
            ),
            [{"id": 1}],
            ownership="copied",
        )
        assert existing.read_bytes() == old_bytes
        assert not new.exists()
        with pytest.raises(TimeoutError), anyio.fail_after(5) as deadline_scope:
            await pending.commit()
        expected = b'{"records": [{"id": 2}]}' if subsequent_writer else old_bytes
        assert existing.read_bytes() == expected
        assert not new.exists()
        assert parent.get_raw("producer.result") is borrowed
        assert not parent.has("checkpoint:run")
        assert not pending.cleanup_failed

    anyio.run(exercise)
