"""Incremental cursor publication barrier regressions for phase 0.56."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import anyio
import pytest

from etlantic import Data, Extract, Load, Pipeline, PipelineRuntime, io_policy
from etlantic.io_policy import SafeIoPolicy, SafeIoResult
from etlantic.plan.model import PipelinePlan
from etlantic.plan.serialize import plan_fingerprint
from etlantic.runtime.incremental import FileStateStore, MemoryStateStore
from etlantic.runtime.orchestrator import LocalOrchestrator
from etlantic.runtime.request import RunIntent, RunRequest
from etlantic.runtime.state import RunStatus
from etlantic.storage.protocol import StorageBinding


class CursorRow(Data):
    id: int


class TwoSinkPipeline(Pipeline):
    source: Extract[CursorRow] = Extract(asset="source")
    first: Load[CursorRow] = Load(input=source, asset="memory://first")
    second: Load[CursorRow] = Load(input=source, asset="memory://second")


class PublicationProbeStorage:
    """Observe whether a cursor moves before both selected sinks finish."""

    name = "memory"

    def __init__(
        self,
        *,
        delegate: StorageBinding,
        state_store: MemoryStateStore,
        fail_second: bool,
    ) -> None:
        self._delegate = delegate
        self._state_store = state_store
        self._fail_second = fail_second
        self._first_written = anyio.Event()
        self.observed_cursors: list[str | None] = []

    async def read(
        self,
        *,
        binding: str,
        location: str | None,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> Any:
        return await self._delegate.read(
            binding=binding,
            location=location,
            contract_type=contract_type,
            context=context,
        )

    async def write(
        self,
        *,
        binding: str,
        location: str | None,
        data: Any,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        target = location or binding
        is_first = target.endswith("first")
        is_second = target.endswith("second")
        if is_second:
            await self._first_written.wait()

        cursor = self._state_store.get("subject")
        self.observed_cursors.append(cursor.value if cursor is not None else None)
        if is_second and self._fail_second:
            raise RuntimeError("second sink publication failed")

        result = await self._delegate.write(
            binding=binding,
            location=location,
            data=data,
            contract_type=contract_type,
            context=context,
        )
        if is_first:
            self._first_written.set()
        return result


def _incremental_plan() -> PipelinePlan:
    plan = TwoSinkPipeline.plan(profile="development")
    assert isinstance(plan, PipelinePlan)
    intents = dict(plan.intents)
    intents["incremental_strategies"] = {
        "subject": {"kind": "cursor"},
        "subject-2": {"kind": "cursor"},
    }
    changed = replace(plan, intents=intents, fingerprint="")
    return replace(changed, fingerprint=plan_fingerprint(changed))


async def _execute(
    *, fail_second: bool
) -> tuple[
    RunStatus,
    dict[str, str | None],
    dict[str, bool],
    list[str | None],
]:
    runtime = PipelineRuntime()
    runtime.memory.seed("source", [CursorRow(id=1)])
    state_store = MemoryStateStore()
    state_store.commit("subject", "cursor-1", reason="test seed")
    state_store.commit("subject-2", "cursor-1b", reason="test seed")
    probe = PublicationProbeStorage(
        delegate=runtime.memory,
        state_store=state_store,
        fail_second=fail_second,
    )
    runtime.register_storage("memory", probe)
    request = RunRequest(
        intent=RunIntent.INCREMENTAL,
        metadata={
            "state_candidates": {
                "subject": "cursor-2",
                "subject-2": "cursor-2b",
            }
        },
    )
    orchestrator = LocalOrchestrator(
        runtime=runtime,
        plan=_incremental_plan(),
        request=request,
        pipeline_cls=TwoSinkPipeline,
        state_store=state_store,
    )
    report = await orchestrator.execute()
    cursors = {
        subject: (
            item.value if (item := state_store.get(subject)) is not None else None
        )
        for subject in ("subject", "subject-2")
    }
    published_sinks = {
        sink: bool(runtime.memory.get(f"memory://{sink}"))
        for sink in ("first", "second")
    }
    return (
        report.status,
        cursors,
        published_sinks,
        probe.observed_cursors,
    )


def test_cursor_commits_only_after_both_selected_sinks_publish() -> None:
    status, cursors, published, observed = anyio.run(
        lambda: _execute(fail_second=False)
    )

    assert status is RunStatus.SUCCEEDED
    assert observed == ["cursor-1", "cursor-1"]
    assert cursors == {"subject": "cursor-2", "subject-2": "cursor-2b"}
    assert published == {"first": True, "second": True}


def test_partial_multi_sink_failure_preserves_committed_cursor() -> None:
    status, cursors, published, observed = anyio.run(lambda: _execute(fail_second=True))

    assert status is not RunStatus.SUCCEEDED
    assert observed == ["cursor-1", "cursor-1"]
    assert cursors == {"subject": "cursor-1", "subject-2": "cursor-1b"}
    assert published == {"first": True, "second": False}


def test_memory_state_store_validates_the_full_batch_before_commit() -> None:
    state = MemoryStateStore()
    state.commit_many({"first": ("first-1", None), "second": ("second-1", None)})

    try:
        state.commit_many(
            {
                "first": ("first-2", None),
                "second": cast(Any, ("second-2",)),
            }
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid cursor batch was accepted")

    first = state.get("first")
    second = state.get("second")
    assert first is not None and first.value == "first-1"
    assert second is not None and second.value == "second-1"


def test_file_state_store_persists_a_cursor_batch_with_one_atomic_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_count = 0

    def counted_write(
        path: str | Path,
        policy: SafeIoPolicy,
        modifier: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        run_id: str = "io",
    ) -> SafeIoResult:
        nonlocal write_count
        write_count += 1
        return original_write(path, policy, modifier, run_id=run_id)

    original_write = io_policy.read_modify_write_json_safe
    monkeypatch.setattr(io_policy, "read_modify_write_json_safe", counted_write)
    store = FileStateStore(tmp_path / "state.json")
    write_count = 0
    transitions = store.commit_many(
        {"first": ("first-2", "published"), "second": ("second-2", "published")}
    )

    assert write_count == 1
    assert [item.subject for item in transitions] == ["first", "second"]
    reopened = FileStateStore(tmp_path / "state.json")
    first = reopened.get("first")
    second = reopened.get("second")
    assert first is not None and first.value == "first-2"
    assert second is not None and second.value == "second-2"
