"""Prefect ExecutionScheduler for ETLantic (etlantic.scheduler/1)."""

from __future__ import annotations

from typing import Any

import anyio

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

__version__ = "0.21.0"


def _prefect_future_id(fut: Any, *, run_id: str, name: str) -> str:
    """Best-effort Prefect task-run identity for ETLantic correlation metadata."""
    task_run_id = getattr(fut, "task_run_id", None)
    if task_run_id is not None:
        return str(task_run_id)
    state = getattr(fut, "state", None)
    state_task_run_id = (
        getattr(state, "task_run_id", None) if state is not None else None
    )
    if state_task_run_id is not None:
        return str(state_task_run_id)
    return f"prefect-task:{run_id}:{name}"


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
        self._task_correlation: dict[str, str] = {}

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
        findings: list[SchedulerSupportFinding] = []
        if plan.logical_graph is None or not plan.logical_graph.nodes:
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
        # Durable scheduling / deployment is explicitly out of the 0.16 MVP.
        if request.metadata.get("require_deployment") or settings.get(
            "require_deployment"
        ):
            findings.append(
                SchedulerSupportFinding(
                    code="PMSCHED201",
                    requirement="deployment",
                    reason=(
                        "Prefect deployment/serve is not part of the 0.16 MVP; "
                        "use local direct invocation only"
                    ),
                )
            )
        return SchedulerSupportReport(supported=not findings, findings=tuple(findings))

    def _make_wave_runner(self, *, run_id: str) -> Any:
        from prefect.tasks import task

        correlation = self._task_correlation

        async def wave_runner(ready: list[str], run_one: Any) -> None:
            @task(name="etlantic-node", retries=0, persist_result=False)
            async def bound_node_task(node_name: str) -> str:
                await run_one(node_name)
                return node_name

            futures = [
                bound_node_task.with_options(name=f"etlantic:{name}").submit(name)
                for name in ready
            ]
            for name, fut in zip(ready, futures, strict=True):
                correlation[name] = _prefect_future_id(fut, run_id=run_id, name=name)

            async def _wait(fut: Any) -> Any:
                result_async = getattr(fut, "result_async", None)
                if callable(result_async):
                    return await result_async()
                return await anyio.to_thread.run_sync(fut.result)

            async with anyio.create_task_group() as tg:
                for fut in futures:
                    tg.start_soon(_wait, fut)

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
            from etlantic.exceptions import ETLanticError

            detail = "; ".join(f"{f.code}: {f.reason}" for f in report.findings)
            raise ETLanticError(f"PrefectScheduler rejected plan: {detail}")

        from prefect.flows import flow

        from etlantic.runtime.orchestrator import LocalOrchestrator

        self._task_correlation = {}
        run_key = ctx.run_id or plan.plan_id or "run"

        @flow(name=f"etlantic:{plan.pipeline_id}", retries=0)
        async def pipeline_flow() -> PipelineRunReport:
            host = LocalOrchestrator(
                runtime=runtime,
                plan=plan,
                request=request,
                pipeline_cls=pipeline_cls,
                workspace=workspace,
                artifacts=artifact_store,
                wave_runner=self._make_wave_runner(run_id=str(run_key)),
                run_id=str(run_key),
            )
            return await host.execute()

        result = pipeline_flow()
        if hasattr(result, "__await__"):
            result = await result  # type: ignore[misc]
        result.metadata.setdefault("scheduler", self.info.name)
        result.metadata.setdefault("scheduler_protocol", SCHEDULER_PROTOCOL)
        result.metadata.setdefault(
            "prefect_task_correlation", dict(self._task_correlation)
        )
        result.metadata.setdefault("prefect_run_id", str(run_key))
        return result


def create_plugin() -> PrefectScheduler:
    """Entry-point factory for ``etlantic.scheduler_plugins``."""
    return PrefectScheduler()
