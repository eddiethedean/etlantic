# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnusedFunction=false, reportUnusedImport=false
"""Prefect ExecutionScheduler plugin tests."""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

# Full-suite resource contention can make Prefect's temporary API server take
# longer than its default startup window. Keep this test deterministic without
# changing application/runtime configuration.
os.environ.setdefault("PREFECT_LOGGING_TO_API_ENABLED", "false")
os.environ.setdefault("PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS", "60")
os.environ.setdefault("PREFECT_LOGGING_LEVEL", "ERROR")
# Xdist workers must not run Prefect migrations against the same SQLite file.
_prefect_worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
os.environ["PREFECT_HOME"] = tempfile.mkdtemp(
    prefix=f"etlantic-prefect-tests-{_prefect_worker}-"
)

pytest.importorskip("prefect")
try:
    from prefect import flow as _prefect_flow  # noqa: F401
except ImportError:  # pragma: no cover - empty leftover namespace package
    pytest.skip("prefect package not installed", allow_module_level=True)

from etlantic import (  # noqa: E402
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    Transformation,
)
from etlantic.exceptions import ETLanticError, PipelineExecutionError  # noqa: E402
from etlantic.plan import plan_pipeline  # noqa: E402
from etlantic.plan.model import PipelinePlan  # noqa: E402
from etlantic.runtime.request import (  # noqa: E402
    CancellationPolicy,
    RetryPolicy,
    RunRequest,
    RunSelection,
    TimeoutPolicy,
)
from etlantic.runtime.scheduler import (  # noqa: E402
    SCHEDULER_PROTOCOL,
    SchedulingContext,
)
from etlantic.runtime.scheduler_discovery import (  # noqa: E402
    discover_scheduler_plugins,
    resolve_scheduler,
)
from etlantic.runtime.state import RunStatus  # noqa: E402
from etlantic_prefect import PrefectScheduler  # noqa: E402

pytestmark = pytest.mark.prefect


def test_prefect_scheduler_rejects_adaptive_plan_during_analysis() -> None:
    report = PrefectScheduler().analyze(
        SimpleNamespace(schema="etlantic.plan/2"),  # type: ignore[arg-type]
        request=RunRequest(),
        context=SchedulingContext(),
    )

    assert report.supported is False
    assert [finding.code for finding in report.findings] == ["PMADP500"]


@pytest.mark.parametrize(
    "cancellation",
    [
        CancellationPolicy(cooperative=False),
        CancellationPolicy(abandon_after_seconds=1.0),
    ],
)
def test_prefect_scheduler_rejects_unqualified_cancellation_policies(
    cancellation: CancellationPolicy,
) -> None:
    report = PrefectScheduler().analyze(
        plan_pipeline(
            _Tiny,
            profile=Profile(name="prefect-test", orchestrator="prefect"),
        ),
        request=RunRequest(cancellation=cancellation),
        context=SchedulingContext(),
    )

    assert report.supported is False
    assert [finding.code for finding in report.findings] == ["PMSCHED103"]


class _Raw(Data):
    customer_id: int
    first_name: str
    last_name: str


class _Out(Data):
    customer_id: int
    full_name: str


class _Normalize(Transformation):
    customers: Input[_Raw]
    result: Output[_Out]


@_Normalize.implementation("local")
def _normalize(customers: list[_Raw]) -> list[_Out]:
    return [
        _Out(
            customer_id=row.customer_id,
            full_name=f"{row.first_name} {row.last_name}",
        )
        for row in customers
    ]


class _Tiny(Pipeline):
    raw: Extract[_Raw] = Extract(asset="raw")
    normalized = _Normalize.step(customers=raw)
    out: Load[_Out] = Load(input=normalized.result, asset="out")


_concurrent_probe_barrier = threading.Barrier(2, timeout=10)


class _ConcurrentProbe(Transformation):
    rows: Input[_Raw]
    result: Output[_Raw]


@_ConcurrentProbe.implementation("local")
async def _concurrent_probe(rows: list[_Raw]) -> list[_Raw]:
    await asyncio.to_thread(_concurrent_probe_barrier.wait)
    if rows[0].customer_id == 202:
        raise RuntimeError("intentional concurrent run failure")
    return list(rows)


class _ConcurrentPipeline(Pipeline):
    raw: Extract[_Raw] = Extract(asset="raw")
    copied = _ConcurrentProbe.step(rows=raw)
    out: Load[_Raw] = Load(input=copied.result, asset="out")


class _SlowCopy(Transformation):
    rows: Input[_Raw]
    result: Output[_Raw]


@_SlowCopy.implementation("local")
async def _slow_copy(rows: list[_Raw]) -> list[_Raw]:
    await asyncio.sleep(0.2)
    return list(rows)


class _SlowPipeline(Pipeline):
    raw: Extract[_Raw] = Extract(asset="raw")
    copied = _SlowCopy.step(rows=raw)
    out: Load[_Raw] = Load(input=copied.result, asset="out")


_retry_probe_calls = 0


class _RetryProbe(Transformation):
    rows: Input[_Raw]
    result: Output[_Raw]


@_RetryProbe.implementation("local")
async def _retry_probe(rows: list[_Raw]) -> list[_Raw]:
    global _retry_probe_calls
    _retry_probe_calls += 1
    if _retry_probe_calls == 1:
        raise RuntimeError("retry this transformation once")
    return list(rows)


class _RetryPipeline(Pipeline):
    raw: Extract[_Raw] = Extract(asset="raw")
    copied = _RetryProbe.step(rows=raw)
    out: Load[_Raw] = Load(input=copied.result, asset="out")


class _BranchProbe(Transformation):
    rows: Input[_Raw]
    result: Output[_Raw]


@_BranchProbe.implementation("local")
async def _branch_probe(rows: list[_Raw]) -> list[_Raw]:
    await asyncio.sleep(0.02)
    return list(rows)


class _BoundedBranchesPipeline(Pipeline):
    raw: Extract[_Raw] = Extract(asset="raw")
    left = _BranchProbe.step(rows=raw)
    middle = _BranchProbe.step(rows=raw)
    right = _BranchProbe.step(rows=raw)
    left_out: Load[_Raw] = Load(input=left.result, asset="left_out")
    middle_out: Load[_Raw] = Load(input=middle.result, asset="middle_out")
    right_out: Load[_Raw] = Load(input=right.result, asset="right_out")


_cancel_probe_started: asyncio.Event | None = None


class _CancellableCopy(Transformation):
    rows: Input[_Raw]
    result: Output[_Raw]


@_CancellableCopy.implementation("local")
async def _cancellable_copy(rows: list[_Raw]) -> list[_Raw]:
    if _cancel_probe_started is None:
        raise RuntimeError("cancellation probe is not initialized")
    _cancel_probe_started.set()
    await asyncio.sleep(30)
    return list(rows)


class _CancellablePipeline(Pipeline):
    raw: Extract[_Raw] = Extract(asset="raw")
    copied = _CancellableCopy.step(rows=raw)
    out: Load[_Raw] = Load(input=copied.result, asset="out")


def test_prefect_discovered() -> None:
    found = discover_scheduler_plugins()
    assert "prefect" in found
    assert found["prefect"].info.name == "prefect"
    assert found["prefect"].info.direct_execution is True
    assert found["prefect"].info.external_compilation is False


def test_resolve_prefect_scheduler() -> None:
    scheduler = resolve_scheduler("prefect")
    assert scheduler.info.name == "prefect"


def test_airflow_not_a_scheduler() -> None:
    with pytest.raises(ETLanticError, match="compile target"):
        resolve_scheduler("airflow")


def test_prefect_conformance_suite() -> None:
    from etlantic.testing import run_scheduler_conformance_suite
    from etlantic_prefect import PrefectScheduler

    result = run_scheduler_conformance_suite(PrefectScheduler())
    assert result["scheduler"] == "prefect"
    assert result["status"] == "succeeded"


def test_pipeline_run_with_prefect_profile() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "raw",
        [_Raw(customer_id=1, first_name="Ada", last_name="Lovelace")],
    )
    report = _Tiny.run(
        profile=Profile(name="prefect-test", orchestrator="prefect"),
        runtime=runtime,
    )
    assert report.status is RunStatus.SUCCEEDED
    assert report.metadata.get("etlantic.scheduler") == "prefect"
    assert report.metadata.get("etlantic.scheduler_protocol") == SCHEDULER_PROTOCOL
    assert report.metadata.get("etlantic.prefect.run_id")
    assert report.run_id == report.metadata["etlantic.prefect.run_id"]
    correlation = report.metadata.get("etlantic.prefect.task_correlation") or {}
    assert set(correlation) >= {"raw", "normalized", "out"}
    observed = set(report.metadata["etlantic.prefect.task_correlation_observed_ids"])
    assert observed >= {"raw", "normalized", "out"}
    assert all(UUID(correlation[name]) for name in observed)
    assert runtime.memory.get("out")


def test_concurrent_runs_isolate_prefect_flow_and_task_state() -> None:
    global _concurrent_probe_barrier
    _concurrent_probe_barrier = threading.Barrier(2, timeout=10)

    profile = Profile(name="prefect-concurrency-test", orchestrator="prefect")
    plan = plan_pipeline(_ConcurrentPipeline, profile=profile)
    scheduler = PrefectScheduler()
    runtime_a = PipelineRuntime()
    runtime_b = PipelineRuntime()
    runtime_a.memory.seed(
        "raw", [_Raw(customer_id=101, first_name="Ada", last_name="One")]
    )
    runtime_b.memory.seed(
        "raw", [_Raw(customer_id=202, first_name="Grace", last_name="Two")]
    )

    async def execute(runtime: PipelineRuntime, run_id: str):
        async with runtime.session():
            return await scheduler.execute(
                plan,
                request=RunRequest(),
                runtime=runtime,
                pipeline_cls=_ConcurrentPipeline,
                context=SchedulingContext(
                    run_id=run_id,
                    pipeline_id=plan.pipeline_id,
                    plan_id=plan.plan_id,
                    profile_name=plan.profile_name,
                ),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        from prefect.testing.utilities import prefect_test_harness

        with prefect_test_harness():
            context_a = copy_context()
            context_b = copy_context()
            future_a = executor.submit(
                context_a.run,
                asyncio.run,
                execute(runtime_a, "prefect-concurrent-a"),
            )
            future_b = executor.submit(
                context_b.run,
                asyncio.run,
                execute(runtime_b, "prefect-concurrent-b"),
            )
            report_a = future_a.result(timeout=30)
            with pytest.raises(PipelineExecutionError) as failure:
                future_b.result(timeout=30)
    report_b = failure.value.report
    assert report_a.status is RunStatus.SUCCEEDED
    assert report_b is not None
    assert report_b.status is not RunStatus.SUCCEEDED
    assert report_a.run_id == "prefect-concurrent-a"
    assert report_b.run_id == "prefect-concurrent-b"
    assert (
        report_a.metadata["etlantic.prefect.flow_run_id"]
        != report_b.metadata["etlantic.prefect.flow_run_id"]
    )
    correlation_a = report_a.metadata["etlantic.prefect.task_correlation"]
    correlation_b = report_b.metadata["etlantic.prefect.task_correlation"]
    assert set(correlation_a) >= {"raw", "copied", "out"}
    assert set(correlation_b) >= {"raw", "copied"}
    assert set(correlation_a.values()).isdisjoint(correlation_b.values())
    assert set(report_a.metadata["etlantic.prefect.task_correlation_observed_ids"]) >= {
        "raw",
        "copied",
        "out",
    }
    assert set(report_b.metadata["etlantic.prefect.task_correlation_observed_ids"]) >= {
        "raw",
        "copied",
    }
    assert all(UUID(correlation_a[name]) for name in correlation_a)
    assert all(UUID(correlation_b[name]) for name in correlation_b)
    assert not _concurrent_probe_barrier.broken
    assert runtime_a.memory.get("out") == [
        _Raw(customer_id=101, first_name="Ada", last_name="One")
    ]
    assert not runtime_b.memory.get("out")


def test_prefect_ready_branches_respect_resolved_concurrency_limit() -> None:
    profile = Profile(
        name="prefect-branch-concurrency-test",
        orchestrator="prefect",
        concurrency=2,
    )
    plan = plan_pipeline(_BoundedBranchesPipeline, profile=profile)
    runtime = PipelineRuntime()
    rows = [_Raw(customer_id=707, first_name="Ada", last_name="Lovelace")]
    runtime.memory.seed("raw", rows)
    active = 0
    peak = 0
    lock = threading.Lock()

    async def observe_concurrency(
        _context: object,
        call_next: Callable[[], Awaitable[object]],
    ) -> object:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            return await call_next()
        finally:
            with lock:
                active -= 1

    runtime.step_middleware.add(observe_concurrency)

    async def execute():
        async with runtime.session():
            return await PrefectScheduler().execute(
                plan,
                request=RunRequest(metadata={"concurrency": 3}),
                runtime=runtime,
                pipeline_cls=_BoundedBranchesPipeline,
                context=SchedulingContext(
                    run_id="prefect-branch-concurrency-test",
                    pipeline_id=plan.pipeline_id,
                    plan_id=plan.plan_id,
                    profile_name=plan.profile_name,
                ),
            )

    from prefect.testing.utilities import prefect_test_harness

    with prefect_test_harness():
        report = asyncio.run(execute())

    assert report.status is RunStatus.SUCCEEDED
    assert peak == 2
    assert all(
        runtime.memory.get(asset) for asset in ("left_out", "middle_out", "right_out")
    )


@pytest.mark.parametrize(
    "timeout_policy",
    [TimeoutPolicy(run_seconds=0.02), TimeoutPolicy(step_seconds=0.02)],
)
def test_prefect_timeout_is_reported_as_an_unsuccessful_run(
    timeout_policy: TimeoutPolicy,
) -> None:
    profile = Profile(name="prefect-timeout-test", orchestrator="prefect")
    plan = plan_pipeline(_SlowPipeline, profile=profile)
    scheduler = PrefectScheduler()
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "raw", [_Raw(customer_id=303, first_name="Grace", last_name="Hopper")]
    )

    async def execute():
        async with runtime.session():
            return await scheduler.execute(
                plan,
                request=RunRequest(timeout=timeout_policy),
                runtime=runtime,
                pipeline_cls=_SlowPipeline,
                context=SchedulingContext(
                    run_id="prefect-timeout-test",
                    pipeline_id=plan.pipeline_id,
                    plan_id=plan.plan_id,
                    profile_name=plan.profile_name,
                ),
            )

    with pytest.raises(PipelineExecutionError) as failure:
        asyncio.run(execute())
    assert failure.value.report is not None
    assert failure.value.report.status is not RunStatus.SUCCEEDED


def test_prefect_selection_keeps_dependency_closure_and_excludes_downstream() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "raw", [_Raw(customer_id=404, first_name="Katherine", last_name="Johnson")]
    )
    report = _Tiny.run(
        profile=Profile(name="prefect-selection-test", orchestrator="prefect"),
        request=RunRequest(selection=RunSelection.only("normalized")),
        runtime=runtime,
    )

    assert report.status is RunStatus.SUCCEEDED
    step_names = {step.step_name for step in report.steps}
    assert {"raw", "normalized"} <= step_names
    assert "out" not in step_names
    assert not runtime.memory.get("out")


def test_prefect_uses_etlantic_retry_policy_without_prefect_task_retries() -> None:
    global _retry_probe_calls
    _retry_probe_calls = 0
    runtime = PipelineRuntime()
    expected = _Raw(customer_id=505, first_name="Dorothy", last_name="Vaughan")
    runtime.memory.seed("raw", [expected])
    report = _RetryPipeline.run(
        profile=Profile(name="prefect-retry-test", orchestrator="prefect"),
        request=RunRequest(
            retry=RetryPolicy(max_attempts=2, retry_on=("RuntimeError",)),
            metadata={
                "retry_safety": {
                    "copied": {"safe": True, "max_attempts": 2},
                }
            },
        ),
        runtime=runtime,
    )

    assert report.status is RunStatus.SUCCEEDED
    copied = next(step for step in report.steps if step.step_name == "copied")
    assert copied.attempts == 2
    assert _retry_probe_calls == 2
    assert runtime.memory.get("out") == [expected]


def test_prefect_execution_ignores_ambient_retry_cache_and_persistence_defaults() -> (
    None
):
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
    from prefect.settings import (
        PREFECT_FLOWS_DEFAULT_RETRIES,
        PREFECT_RESULTS_PERSIST_BY_DEFAULT,
        PREFECT_TASKS_DEFAULT_NO_CACHE,
        PREFECT_TASKS_DEFAULT_PERSIST_RESULT,
        PREFECT_TASKS_DEFAULT_RETRIES,
        PREFECT_TASKS_DISABLE_CACHING,
        temporary_settings,
    )
    from prefect.testing.utilities import prefect_test_harness

    global _retry_probe_calls
    _retry_probe_calls = 0
    profile = Profile(name="prefect-ambient-defaults-test", orchestrator="prefect")
    plan = plan_pipeline(_RetryPipeline, profile=profile)
    runtime = PipelineRuntime()
    expected = _Raw(customer_id=506, first_name="Katherine", last_name="Johnson")
    runtime.memory.seed("raw", [expected])
    scheduler = PrefectScheduler()
    request = RunRequest(
        retry=RetryPolicy(max_attempts=2, retry_on=("RuntimeError",)),
        metadata={
            "retry_safety": {
                "copied": {"safe": True, "max_attempts": 2},
            }
        },
    )

    async def execute(run_id: str):
        async with runtime.session():
            return await scheduler.execute(
                plan,
                request=request,
                runtime=runtime,
                pipeline_cls=_RetryPipeline,
                context=SchedulingContext(
                    run_id=run_id,
                    pipeline_id=plan.pipeline_id,
                    plan_id=plan.plan_id,
                    profile_name=plan.profile_name,
                ),
            )

    async def read_prefect_results(flow_run_id: UUID):
        async with get_client() as client:
            flow_run = await client.read_flow_run(flow_run_id)
            task_runs = await client.read_task_runs(
                flow_run_filter=FlowRunFilter(
                    id=FlowRunFilterId(any_=[flow_run_id]),
                ),
                limit=20,
            )
            return flow_run, task_runs

    with (
        prefect_test_harness(),
        temporary_settings(
            {
                PREFECT_FLOWS_DEFAULT_RETRIES: 3,
                PREFECT_RESULTS_PERSIST_BY_DEFAULT: True,
                PREFECT_TASKS_DEFAULT_NO_CACHE: False,
                PREFECT_TASKS_DEFAULT_PERSIST_RESULT: True,
                PREFECT_TASKS_DEFAULT_RETRIES: 3,
                PREFECT_TASKS_DISABLE_CACHING: False,
            }
        ),
    ):
        first = asyncio.run(execute("prefect-ambient-defaults-first"))
        assert _retry_probe_calls == 2
        second = asyncio.run(execute("prefect-ambient-defaults-second"))
        assert _retry_probe_calls == 3

        first_flow, first_tasks = asyncio.run(
            read_prefect_results(UUID(first.metadata["etlantic.prefect.flow_run_id"]))
        )
        second_flow, second_tasks = asyncio.run(
            read_prefect_results(UUID(second.metadata["etlantic.prefect.flow_run_id"]))
        )

    assert first.status is RunStatus.SUCCEEDED
    assert second.status is RunStatus.SUCCEEDED
    assert first_flow.state is not None
    assert second_flow.state is not None
    assert first_flow.state.data is None
    assert second_flow.state.data is None
    assert first_tasks and second_tasks
    assert all(
        task.state is not None
        and task.state.data is None
        and task.state.state_details.cache_key is None
        for task in [*first_tasks, *second_tasks]
    )


def test_prefect_cancellation_preserves_cancelled_etl_report() -> None:
    profile = Profile(name="prefect-cancel-test", orchestrator="prefect")
    plan = plan_pipeline(_CancellablePipeline, profile=profile)
    scheduler = PrefectScheduler()
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "raw", [_Raw(customer_id=606, first_name="Grace", last_name="Hopper")]
    )

    async def scenario():
        global _cancel_probe_started
        _cancel_probe_started = asyncio.Event()

        async def execute():
            async with runtime.session():
                return await scheduler.execute(
                    plan,
                    request=RunRequest(),
                    runtime=runtime,
                    pipeline_cls=_CancellablePipeline,
                    context=SchedulingContext(
                        run_id="prefect-cancel-test",
                        pipeline_id=plan.pipeline_id,
                        plan_id=plan.plan_id,
                        profile_name=plan.profile_name,
                    ),
                )

        task = asyncio.create_task(execute())
        await asyncio.wait_for(_cancel_probe_started.wait(), timeout=10)
        task.cancel()
        with pytest.raises(PipelineExecutionError) as failure:
            await asyncio.wait_for(task, timeout=5)
        return failure.value.report

    report = asyncio.run(scenario())
    assert report is not None
    assert report.status is RunStatus.CANCELLED
    assert report.run_id == "prefect-cancel-test"
    assert report.metadata["etlantic.prefect.flow_run_id"]


def test_prefect_cancellation_during_commit_preserves_effect_receipt() -> None:
    from etlantic.connectors.models import CommitReceipt, SinkPlan, WriteSession

    class _CommitBoundarySink:
        def __init__(self) -> None:
            self.commit_started = asyncio.Event()
            self.release_commit = asyncio.Event()
            self.staged: list[_Out] = []
            self.effects: list[_Out] = []
            self.commit_calls = 0
            self.abort_calls = 0
            self.reconcile_calls = 0

        async def plan_write(self, **_kwargs: object) -> SinkPlan:
            return SinkPlan(provider="memory", write_mode="replace")

        async def begin_write(self, **_kwargs: object) -> WriteSession:
            return WriteSession(
                session_id="prefect-direct-cancel-effect",
                provider="memory",
            )

        async def write_batch(
            self, _session: WriteSession, data: list[_Out], **_kwargs: object
        ) -> None:
            self.staged = list(data)

        async def prepare(self, _session: WriteSession, **_kwargs: object) -> None:
            return None

        async def commit(
            self, session: WriteSession, **_kwargs: object
        ) -> CommitReceipt:
            self.commit_calls += 1
            self.effects.extend(self.staged)
            self.commit_started.set()
            await self.release_commit.wait()
            return CommitReceipt(
                status="committed",
                session_id=session.session_id,
                provider=session.provider,
                publication_id="prefect-direct-cancel-effect-publication",
            )

        async def abort(
            self, session: WriteSession, **_kwargs: object
        ) -> CommitReceipt:
            self.abort_calls += 1
            return CommitReceipt(
                status="rolled_back",
                session_id=session.session_id,
                provider=session.provider,
            )

        async def reconcile(
            self, receipt: CommitReceipt, **_kwargs: object
        ) -> CommitReceipt:
            self.reconcile_calls += 1
            return CommitReceipt(
                status="committed",
                session_id=receipt.session_id,
                provider=receipt.provider,
                publication_id="prefect-direct-cancel-effect-publication",
            )

    profile = Profile(
        name="prefect-effect-boundary-cancel",
        orchestrator="prefect",
        assets={"out": "commit-boundary"},
    )
    plan = cast(PipelinePlan, plan_pipeline(_Tiny, profile=profile))
    scheduler = PrefectScheduler()
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "raw", [_Raw(customer_id=608, first_name="Grace", last_name="Hopper")]
    )
    sink = _CommitBoundarySink()
    runtime.register_sink_connector("commit-boundary", sink)
    runtime.ensure_plugins_for_profile(profile)

    async def scenario():
        async def execute():
            async with runtime.session():
                return await scheduler.execute(
                    plan,
                    request=RunRequest(),
                    runtime=runtime,
                    pipeline_cls=_Tiny,
                    context=SchedulingContext(
                        run_id="prefect-effect-boundary-cancel-test",
                        pipeline_id=plan.pipeline_id,
                        plan_id=plan.plan_id,
                        profile_name=plan.profile_name,
                    ),
                )

        task = asyncio.create_task(execute())
        await asyncio.wait_for(sink.commit_started.wait(), timeout=10)
        task.cancel()
        with pytest.raises(PipelineExecutionError) as failure:
            await asyncio.wait_for(task, timeout=5)
        return failure.value.report

    report = asyncio.run(scenario())
    assert report is not None
    assert report.status is RunStatus.CANCELLED
    assert report.run_id == "prefect-effect-boundary-cancel-test"
    assert len(sink.effects) == 1
    assert sink.commit_calls == 1
    assert sink.abort_calls == 0
    assert sink.reconcile_calls == 1
    receipts = report.metadata["etlantic.publication_receipts"]
    assert len(receipts) == 1
    assert receipts[0]["status"] == "committed"
    assert receipts[0]["publication_id"] == "prefect-direct-cancel-effect-publication"


def test_prefect_api_cancellation_preserves_cancelled_etl_report() -> None:
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import FlowFilter, FlowFilterName
    from prefect.client.schemas.objects import State, StateType
    from prefect.client.schemas.responses import SetStateStatus

    profile = Profile(name="prefect-api-cancel-test", orchestrator="prefect")
    plan = plan_pipeline(_CancellablePipeline, profile=profile)
    scheduler = PrefectScheduler()
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "raw", [_Raw(customer_id=607, first_name="Katherine", last_name="Johnson")]
    )

    async def scenario():
        global _cancel_probe_started
        _cancel_probe_started = asyncio.Event()

        async def execute():
            async with runtime.session():
                return await scheduler.execute(
                    plan,
                    request=RunRequest(),
                    runtime=runtime,
                    pipeline_cls=_CancellablePipeline,
                    context=SchedulingContext(
                        run_id="prefect-api-cancel-test",
                        pipeline_id=plan.pipeline_id,
                        plan_id=plan.plan_id,
                        profile_name=plan.profile_name,
                    ),
                )

        task = asyncio.create_task(execute())
        await asyncio.wait_for(_cancel_probe_started.wait(), timeout=10)
        async with get_client() as client:
            flow_runs = await client.read_flow_runs(
                flow_filter=FlowFilter(
                    name=FlowFilterName(any_=[f"etlantic:{plan.pipeline_id}"])
                ),
                limit=10,
            )
            active_run = next(
                run
                for run in flow_runs
                if run.state is not None and run.state.type is StateType.RUNNING
            )
            cancellation = await client.set_flow_run_state(
                active_run.id,
                State(
                    type=StateType.CANCELLING,
                    message="test requested cancellation through the Prefect API",
                ),
                force=False,
            )
        assert cancellation.status is SetStateStatus.ACCEPT
        with pytest.raises(PipelineExecutionError) as failure:
            await asyncio.wait_for(task, timeout=5)
        return failure.value.report

    report = asyncio.run(scenario())
    assert report is not None
    assert report.status is RunStatus.CANCELLED
    assert report.run_id == "prefect-api-cancel-test"
    assert report.metadata["etlantic.prefect.flow_run_id"]
