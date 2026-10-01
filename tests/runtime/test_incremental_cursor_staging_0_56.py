"""Incremental cursor publication barrier regressions for phase 0.56."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import anyio

from etlantic import Data, Extract, Load, Pipeline, PipelineRuntime
from etlantic.plan.model import PipelinePlan
from etlantic.plan.serialize import plan_fingerprint
from etlantic.runtime.incremental import MemoryStateStore
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
    }
    changed = replace(plan, intents=intents, fingerprint="")
    return replace(changed, fingerprint=plan_fingerprint(changed))


async def _execute(
    *, fail_second: bool
) -> tuple[RunStatus, str | None, list[str | None]]:
    runtime = PipelineRuntime()
    runtime.memory.seed("source", [CursorRow(id=1)])
    state_store = MemoryStateStore()
    state_store.commit("subject", "cursor-1", reason="test seed")
    probe = PublicationProbeStorage(
        delegate=runtime.memory,
        state_store=state_store,
        fail_second=fail_second,
    )
    runtime.register_storage("memory", probe)
    request = RunRequest(
        intent=RunIntent.INCREMENTAL,
        metadata={"state_candidates": {"subject": "cursor-2"}},
    )
    orchestrator = LocalOrchestrator(
        runtime=runtime,
        plan=_incremental_plan(),
        request=request,
        pipeline_cls=TwoSinkPipeline,
        state_store=state_store,
    )
    report = await orchestrator.execute()
    cursor = state_store.get("subject")
    return (
        report.status,
        cursor.value if cursor is not None else None,
        probe.observed_cursors,
    )


def test_cursor_commits_only_after_both_selected_sinks_publish() -> None:
    status, cursor, observed = anyio.run(lambda: _execute(fail_second=False))

    assert status is RunStatus.SUCCEEDED
    assert observed == ["cursor-1", "cursor-1"]
    assert cursor == "cursor-2"


def test_partial_multi_sink_failure_preserves_committed_cursor() -> None:
    status, cursor, observed = anyio.run(lambda: _execute(fail_second=True))

    assert status is not RunStatus.SUCCEEDED
    assert observed == ["cursor-1", "cursor-1"]
    assert cursor == "cursor-1"
