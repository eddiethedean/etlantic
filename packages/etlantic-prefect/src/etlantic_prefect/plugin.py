# pyright: reportUnknownMemberType=false, reportAttributeAccessIssue=false
"""Prefect ExecutionScheduler for ETLantic (etlantic.scheduler/1)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from threading import Event
from typing import Any, cast

import anyio
from anyio.abc import TaskGroup

from etlantic.exceptions import PipelineExecutionError
from etlantic.plan.model import PipelinePlan
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.request import RunRequest
from etlantic.runtime.scheduler import (
    SCHEDULER_PROTOCOL,
    SchedulerInfo,
    SchedulerSupportFinding,
    SchedulerSupportReport,
    SchedulingContext,
)
from etlantic.runtime.state import RunStatus

__version__ = "0.58.0"


def _prefect_future_id(fut: Any, *, run_id: str, name: str) -> tuple[str, bool]:
    """Return a task-run identity and whether Prefect supplied the identity."""
    task_run_id = getattr(fut, "task_run_id", None)
    if task_run_id is not None:
        return str(task_run_id), True
    state = getattr(fut, "state", None)
    state_task_run_id = (
        getattr(state, "task_run_id", None) if state is not None else None
    )
    if state_task_run_id is not None:
        return str(state_task_run_id), True
    return f"prefect-task:{run_id}:{name}", False


class PrefectScheduler:
    """Optional Prefect direct-execution scheduler (local MVP, no deploy/serve)."""

    def __init__(self) -> None:
        self._info = SchedulerInfo(
            name="prefect",
            version=__version__,
            scheduler_protocol=SCHEDULER_PROTOCOL,
            direct_execution=True,
            external_compilation=False,
            metadata={"prefect_major": 3, "deployment": False},
        )

    @property
    def info(self) -> SchedulerInfo:
        return self._info

    def analyze(
        self,
        plan: PipelinePlan,
        *,
        request: RunRequest,
        context: SchedulingContext,
    ) -> SchedulerSupportReport:
        from etlantic.plan.adaptive_model import ADAPTIVE_PLAN_SCHEMA

        if getattr(plan, "schema", None) == ADAPTIVE_PLAN_SCHEMA:
            return SchedulerSupportReport(
                supported=False,
                findings=(
                    SchedulerSupportFinding(
                        code="PMADP500",
                        requirement="etlantic.plan/2",
                        reason=(
                            "PrefectScheduler does not advertise adaptive "
                            "physical-unit execution"
                        ),
                    ),
                ),
            )
        findings: list[SchedulerSupportFinding] = []
        if not plan.logical_graph.nodes:
            findings.append(
                SchedulerSupportFinding(
                    code="PMSCHED101",
                    requirement="logical_graph",
                    reason="Plan has no logical nodes to schedule",
                )
            )
        settings = plan.execution_settings or {}
        if settings.get("concurrency") is not None:
            concurrency = settings["concurrency"]
        elif request.metadata.get("concurrency") is not None:
            concurrency = request.metadata["concurrency"]
        else:
            concurrency = 4
        try:
            concurrency_i = int(concurrency)
        except (TypeError, ValueError):
            findings.append(
                SchedulerSupportFinding(
                    code="PMSCHED102",
                    requirement="concurrency",
                    reason="Concurrency must be an integer",
                )
            )
        else:
            if concurrency_i < 1:
                findings.append(
                    SchedulerSupportFinding(
                        code="PMSCHED102",
                        requirement="concurrency",
                        reason="Concurrency must be >= 1",
                    )
                )
        cancellation = request.cancellation
        if (
            cancellation.cooperative is False
            or cancellation.abandon_after_seconds is not None
        ):
            findings.append(
                SchedulerSupportFinding(
                    code="PMSCHED103",
                    requirement="cancellation_policy",
                    reason=(
                        "Prefect direct execution supports only cooperative "
                        "cancellation without bounded abandonment"
                    ),
                )
            )
        # This direct scheduler path does not provision durable deployments.
        if request.metadata.get("require_deployment") or settings.get(
            "require_deployment"
        ):
            findings.append(
                SchedulerSupportFinding(
                    code="PMSCHED201",
                    requirement="deployment",
                    reason=(
                        "Prefect deployment provisioning is separate from direct "
                        "local invocation; use the managed deployment API"
                    ),
                )
            )
        return SchedulerSupportReport(supported=not findings, findings=tuple(findings))

    def _make_wave_runner(
        self,
        *,
        run_id: str,
        correlation: dict[str, str],
        observed_ids: set[str],
        cancellation_event: Event,
    ) -> Any:
        from prefect.cache_policies import NO_CACHE
        from prefect.tasks import task

        async def wave_runner(ready: list[str], run_one: Any) -> None:
            @task(
                name="etlantic-node",
                retries=0,
                persist_result=False,
                cache_policy=NO_CACHE,
            )
            async def bound_node_task(node_name: str) -> str:
                node_completed = anyio.Event()

                async def execute_node() -> None:
                    await run_one(node_name)
                    node_completed.set()

                async def observe_cancellation(
                    task_group: TaskGroup,
                ) -> None:
                    while not node_completed.is_set():
                        if cancellation_event.is_set():
                            task_group.cancel_scope.cancel()
                            return
                        await anyio.sleep(0.02)

                async with anyio.create_task_group() as node_group:
                    node_group.start_soon(execute_node)
                    node_group.start_soon(observe_cancellation, node_group)
                return node_name

            futures = [
                bound_node_task.with_options(name=f"etlantic:{name}").submit(name)
                for name in ready
            ]
            for name, fut in zip(ready, futures, strict=True):
                task_id, observed = _prefect_future_id(fut, run_id=run_id, name=name)
                correlation[name] = task_id
                if observed:
                    observed_ids.add(name)

            async def _wait(fut: Any) -> None:
                result_async = cast(
                    Callable[[], Awaitable[Any]] | None,
                    getattr(fut, "result_async", None),
                )
                if callable(result_async):
                    await result_async()
                    return
                await anyio.to_thread.run_sync(cast(Callable[[], Any], fut.result))

            completed = anyio.Event()
            remaining = len(futures)
            wait_failures: list[BaseException] = []

            async def _wait_and_track(fut: Any) -> None:
                nonlocal remaining
                try:
                    await _wait(fut)
                except BaseException as exc:
                    if not isinstance(exc, anyio.get_cancelled_exc_class()):
                        wait_failures.append(exc)
                    raise
                remaining -= 1
                if remaining == 0:
                    completed.set()

            async with anyio.create_task_group() as tg:
                for fut in futures:
                    tg.start_soon(_wait_and_track, fut)
                try:
                    await completed.wait()
                except BaseException as exc:
                    if (
                        isinstance(exc, anyio.get_cancelled_exc_class())
                        and not wait_failures
                    ):
                        cancellation_event.set()
                    raise

        return wave_runner

    async def execute(
        self,
        plan: PipelinePlan,
        *,
        request: RunRequest,
        runtime: Any,
        pipeline_cls: type[Any] | None = None,
        workspace: Any = None,
        artifact_store: Any = None,
        context: SchedulingContext | None = None,
    ) -> PipelineRunReport:
        ctx = context or SchedulingContext(
            pipeline_id=plan.pipeline_id,
            plan_id=plan.plan_id,
            profile_name=plan.profile_name,
        )
        report = self.analyze(plan, request=request, context=ctx)
        if not report.supported:
            detail = "; ".join(f"{f.code}: {f.reason}" for f in report.findings)
            code = report.findings[0].code if report.findings else None
            raise PipelineExecutionError(
                f"PrefectScheduler rejected plan: {detail}",
                code=code,
                stage="admission",
            )

        from prefect.flows import flow

        from etlantic.runtime.orchestrator import LocalOrchestrator

        run_key = ctx.run_id or plan.plan_id or "run"
        cancellation_event = Event()
        correlation: dict[str, str] = {}
        observed_task_ids: set[str] = set()
        result_holder: dict[str, PipelineRunReport] = {}
        flow_run_id: list[str] = []

        @flow(
            name=f"etlantic:{plan.pipeline_id}",
            retries=0,
            persist_result=False,
        )
        async def pipeline_flow() -> PipelineRunReport:
            from prefect.runtime import flow_run

            current_flow_run_id = getattr(flow_run, "id", None)
            if current_flow_run_id is not None:
                flow_run_id.append(str(current_flow_run_id))
            host = LocalOrchestrator(
                runtime=runtime,
                plan=plan,
                request=request,
                pipeline_cls=pipeline_cls,
                workspace=workspace,
                artifacts=artifact_store,
                wave_runner=self._make_wave_runner(
                    run_id=str(run_key),
                    correlation=correlation,
                    observed_ids=observed_task_ids,
                    cancellation_event=cancellation_event,
                ),
                cancellation_event=cancellation_event,
                run_id=str(run_key),
            )
            run_report = await host.execute()
            result_holder["report"] = run_report
            if run_report.status is not RunStatus.SUCCEEDED:
                raise PipelineExecutionError(
                    "Prefect flow completed with an unsuccessful ETLantic report",
                    run_id=run_report.run_id,
                    report=run_report,
                    stage="execution",
                )
            return run_report

        flow_error: PipelineExecutionError | None = None
        try:
            result = pipeline_flow()
            if hasattr(result, "__await__"):
                result = await cast(Awaitable[PipelineRunReport], result)
        except PipelineExecutionError as exc:
            flow_error = exc
            result = exc.report
        if not isinstance(result, PipelineRunReport):
            result = result_holder.get("report")
        if not isinstance(result, PipelineRunReport):
            raise PipelineExecutionError(
                "Prefect flow finished without an ETLantic run report",
                run_id=str(run_key),
                stage="publication",
            )
        result.metadata.setdefault("etlantic.scheduler", self.info.name)
        result.metadata.setdefault("etlantic.scheduler_protocol", SCHEDULER_PROTOCOL)
        result.metadata.setdefault(
            "etlantic.prefect.task_correlation", dict(correlation)
        )
        result.metadata.setdefault(
            "etlantic.prefect.task_correlation_observed_ids",
            sorted(observed_task_ids),
        )
        result.metadata.setdefault("etlantic.prefect.run_id", str(run_key))
        if flow_run_id:
            result.metadata.setdefault("etlantic.prefect.flow_run_id", flow_run_id[0])
        if flow_error is not None:
            raise PipelineExecutionError(
                str(flow_error),
                run_id=result.run_id,
                report=result,
                code=flow_error.code,
                stage=flow_error.stage,
            ) from flow_error
        return result


def create_plugin() -> PrefectScheduler:
    """Entry-point factory for ``etlantic.scheduler_plugins``."""
    return PrefectScheduler()
