"""Public physical scheduler facade for qualified adaptive plans."""

from __future__ import annotations

from typing import Any

from etlantic.plan.model import PipelinePlan
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.request import RunRequest
from etlantic.runtime.scheduler import (
    SCHEDULER_PROTOCOL,
    LocalScheduler,
    SchedulerInfo,
    SchedulerSupportReport,
    SchedulingContext,
)


class PhysicalScheduler:
    """Route executable adaptive plans through the built-in physical host."""

    def __init__(self) -> None:
        from etlantic import __version__

        self._delegate = LocalScheduler()
        self._info = SchedulerInfo(
            name="local-physical",
            version=__version__,
            scheduler_protocol=SCHEDULER_PROTOCOL,
            direct_execution=True,
            external_compilation=False,
            metadata={"host": "LocalOrchestrator", "adaptive": True},
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
        return self._delegate.analyze(plan, request=request, context=context)

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
        return await self._delegate.execute(
            plan,
            request=request,
            runtime=runtime,
            pipeline_cls=pipeline_cls,
            workspace=workspace,
            artifact_store=artifact_store,
            context=context,
        )


__all__ = ["PhysicalScheduler"]
