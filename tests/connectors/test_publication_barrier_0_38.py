"""PublicationBarrier multi-sink + unknown-hold regressions (0.38)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anyio
import pytest

from etlantic.connectors.models import CommitReceipt
from etlantic.connectors.session import PublicationBarrier
from etlantic.exceptions import NodeExecutionError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.model import LogicalGraph, Node, NodeKind
from etlantic.plan.model import PLAN_SCHEMA, PipelinePlan
from etlantic.runtime.orchestrator import LocalOrchestrator
from etlantic.runtime.request import RunIntent, RunRequest


def _committed(publication_id: str = "pub-1") -> CommitReceipt:
    return CommitReceipt(
        status="committed",
        session_id="s1",
        provider="memory",
        publication_id=publication_id,
    )


def _unknown() -> CommitReceipt:
    return CommitReceipt(
        status="unknown",
        session_id="s1",
        provider="memory",
        message="ambiguous",
    )


def _rolled_back() -> CommitReceipt:
    return CommitReceipt(
        status="rolled_back",
        session_id="s1",
        provider="memory",
        message="aborted",
    )


def test_barrier_finalize_duck_typed_not_isinstance() -> None:
    """finalize_source uses hasattr, not LocalFilesSourceConnector isinstance."""
    source = MagicMock()
    source.commit_ledger = AsyncMock()
    source.consume_after_commit = AsyncMock()
    # Not a LocalFilesSourceConnector subclass.
    barrier = PublicationBarrier(
        source_connector=source,
        source_binding={"binding": "in"},
        source_context={"run_id": "r1"},
        expected_sink_commits=2,
    )
    barrier.record(_committed("a"))
    barrier.record(_committed("b"))

    async def _run() -> None:
        await barrier.finalize_source()

    anyio.run(_run)
    source.commit_ledger.assert_awaited_once()
    source.consume_after_commit.assert_awaited_once()


def test_barrier_two_sinks_ledger_after_both() -> None:
    source = MagicMock()
    source.commit_ledger = AsyncMock()
    source.consume_after_commit = AsyncMock()
    source.discard_proposal = MagicMock()
    barrier = PublicationBarrier(
        source_connector=source,
        expected_sink_commits=2,
    )
    barrier.record(_committed("a"))

    async def _partial() -> None:
        # Not complete yet — finalize must not advance.
        assert not barrier.is_complete
        await barrier.finalize_source()

    anyio.run(_partial)
    source.commit_ledger.assert_not_awaited()

    barrier.record(_committed("b"))

    async def _complete() -> None:
        assert barrier.is_complete and barrier.all_committed
        await barrier.finalize_source()

    anyio.run(_complete)
    source.commit_ledger.assert_awaited_once()
    source.discard_proposal.assert_not_called()


def test_barrier_second_fail_does_not_advance() -> None:
    source = MagicMock()
    source.commit_ledger = AsyncMock()
    source.consume_after_commit = AsyncMock()
    source.discard_proposal = MagicMock()
    barrier = PublicationBarrier(
        source_connector=source,
        expected_sink_commits=2,
    )
    barrier.record(_committed("a"))
    barrier.record(_rolled_back())

    async def _run() -> None:
        await barrier.finalize_source()

    anyio.run(_run)
    source.commit_ledger.assert_not_awaited()
    source.discard_proposal.assert_called_once()


def test_barrier_unknown_holds_proposal() -> None:
    source = MagicMock()
    source.commit_ledger = AsyncMock()
    source.discard_proposal = MagicMock()
    barrier = PublicationBarrier(
        source_connector=source,
        expected_sink_commits=1,
    )
    barrier.record(_unknown())

    async def _run() -> None:
        await barrier.finalize_source()

    anyio.run(_run)
    source.commit_ledger.assert_not_awaited()
    source.discard_proposal.assert_not_called()


def _dual_sink_plan() -> PipelinePlan:
    src = Node(name="src", kind=NodeKind.SOURCE, identity="src", binding="in")
    a = Node(name="a", kind=NodeKind.SINK, identity="a", binding="out_a")
    b = Node(name="b", kind=NodeKind.SINK, identity="b", binding="out_b")
    graph = LogicalGraph(
        pipeline_id="pipe",
        pipeline_name="pipe",
        nodes=(src, a, b),
        edges=(),
    )
    return PipelinePlan(
        schema=PLAN_SCHEMA,
        plan_id="plan-barrier",
        pipeline_id="pipe",
        pipeline_name="pipe",
        profile_name="dev",
        fingerprint="0" * 64,
        logical_graph=graph,
        bindings={},
    )


def _orch_with_pending(
    *,
    source: Any,
    expected: int = 2,
) -> LocalOrchestrator:
    from etlantic.connectors.session import PublicationBarrier as Barrier

    runtime = PipelineRuntime()
    orch = LocalOrchestrator(
        runtime=runtime,
        plan=_dual_sink_plan(),
        request=RunRequest(intent=RunIntent.STANDARD),
    )
    orch._pending_source_connector = source
    orch._pending_source_binding = {"binding": "in"}
    orch._pending_source_context = {"run_id": "r1"}
    orch._expected_sink_commits = expected
    orch._sink_commit_receipts = []
    orch._publication_barrier = Barrier(
        source_connector=source,
        source_binding={"binding": "in"},
        source_context={"run_id": "r1"},
        expected_sink_commits=expected,
    )
    return orch


def test_orchestrator_two_sinks_finalize_once(monkeypatch: pytest.MonkeyPatch) -> None:
    source = MagicMock()
    source.commit_ledger = AsyncMock()
    source.consume_after_commit = AsyncMock()
    source.discard_proposal = MagicMock()
    orch = _orch_with_pending(source=source, expected=2)

    receipts = [_committed("a"), _committed("b")]

    async def _fake_write(*_a: Any, **_k: Any) -> CommitReceipt:
        return receipts.pop(0)

    monkeypatch.setattr(
        "etlantic.connectors.session.write_via_storage_session",
        _fake_write,
    )

    async def _run() -> None:
        sink_a = orch.plan.logical_graph.nodes[1]
        sink_b = orch.plan.logical_graph.nodes[2]
        await orch._write_sink(sink_a, [{"id": 1}], run_id="r1")
        source.commit_ledger.assert_not_awaited()
        await orch._write_sink(sink_b, [{"id": 1}], run_id="r1")
        source.commit_ledger.assert_awaited_once()

    anyio.run(_run)
    assert len(orch._sink_commit_receipts) == 2


def test_orchestrator_second_fail_no_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = MagicMock()
    source.commit_ledger = AsyncMock()
    source.discard_proposal = MagicMock()
    orch = _orch_with_pending(source=source, expected=2)

    calls = {"n": 0}

    async def _fake_write(*_a: Any, **_k: Any) -> CommitReceipt:
        calls["n"] += 1
        if calls["n"] == 1:
            return _committed("a")
        raise RuntimeError("second sink boom")

    monkeypatch.setattr(
        "etlantic.connectors.session.write_via_storage_session",
        _fake_write,
    )

    async def _run() -> None:
        sink_a = orch.plan.logical_graph.nodes[1]
        sink_b = orch.plan.logical_graph.nodes[2]
        await orch._write_sink(sink_a, [{"id": 1}], run_id="r1")
        with pytest.raises(NodeExecutionError):
            await orch._write_sink(sink_b, [{"id": 1}], run_id="r1")

    anyio.run(_run)
    source.commit_ledger.assert_not_awaited()
    source.discard_proposal.assert_called()


def test_orchestrator_unknown_keeps_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = MagicMock()
    source.commit_ledger = AsyncMock()
    source.discard_proposal = MagicMock()
    orch = _orch_with_pending(source=source, expected=1)

    async def _fake_write(*_a: Any, **_k: Any) -> CommitReceipt:
        return _unknown()

    async def _no_reconcile(receipt: Any, **_k: Any) -> Any:
        return receipt

    monkeypatch.setattr(
        "etlantic.connectors.session.write_via_storage_session",
        _fake_write,
    )
    monkeypatch.setattr(orch, "_reconcile_unknown_receipt", _no_reconcile)

    async def _run() -> None:
        sink = orch.plan.logical_graph.nodes[1]
        with pytest.raises(NodeExecutionError) as exc_info:
            await orch._write_sink(sink, [{"id": 1}], run_id="r1")
        assert exc_info.value.code == "PMEXEC433"

    anyio.run(_run)
    source.discard_proposal.assert_not_called()
    source.commit_ledger.assert_not_awaited()
