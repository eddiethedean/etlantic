"""Public run / arun helpers and debug session."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio

from pipelantic.exceptions import PipelineExecutionError
from pipelantic.lifecycle.runtime import PipelineRuntime
from pipelantic.plan.planner import plan_pipeline
from pipelantic.registry import PlanningContext
from pipelantic.reports.model import PipelineRunReport
from pipelantic.runtime.orchestrator import LocalOrchestrator
from pipelantic.runtime.request import (
    InvalidationMode,
    RunRequest,
    RunSelection,
)
from pipelantic.runtime.state import RunStatus


def _ensure_not_in_running_loop() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise PipelineExecutionError(
        "Pipeline.run() cannot be called from a running event loop; "
        "use `await Pipeline.arun(...)` instead.",
        code="PMEXEC100",
    )


async def arun_pipeline(
    pipeline_cls: type[Any],
    *,
    profile: str | Any = "development",
    request: RunRequest | None = None,
    runtime: PipelineRuntime | None = None,
    context: PlanningContext | None = None,
    workspace: str | Path | None = None,
) -> PipelineRunReport:
    """Validate, plan, and execute a pipeline asynchronously."""
    request = request or RunRequest()
    runtime = runtime or PipelineRuntime()
    graph = pipeline_cls.build_graph()
    selection = request.selection.to_plan_selection(graph)
    plan = plan_pipeline(
        pipeline_cls,
        context=context,
        profile=profile,
        selection=selection,
    )
    # Auto-register memory bindings for sources/sinks when missing.
    for node in plan.logical_graph.nodes:
        if node.binding and node.binding not in plan.bindings:
            from pipelantic.registry import BindingDescriptor

            # Mutating frozen plan is not allowed; register on runtime only.
            runtime.registry.register_binding(
                BindingDescriptor(binding=node.binding, provider="memory")
            )

    orch = LocalOrchestrator(
        runtime=runtime,
        plan=plan,
        request=request,
        pipeline_cls=pipeline_cls,
        workspace=Path(workspace) if workspace else None,
    )
    async with runtime.session():
        return await orch.execute()


def run_pipeline(
    pipeline_cls: type[Any],
    *,
    profile: str | Any = "development",
    request: RunRequest | None = None,
    runtime: PipelineRuntime | None = None,
    context: PlanningContext | None = None,
    workspace: str | Path | None = None,
) -> PipelineRunReport:
    """Validate, plan, and execute a pipeline synchronously."""
    _ensure_not_in_running_loop()

    async def _main() -> PipelineRunReport:
        return await arun_pipeline(
            pipeline_cls,
            profile=profile,
            request=request,
            runtime=runtime,
            context=context,
            workspace=workspace,
        )

    return anyio.run(_main)


@dataclass
class DebugSession:
    """Stateful local debug session above RunRequest."""

    pipeline_cls: type[Any]
    profile: str | Any = "development"
    runtime: PipelineRuntime = field(default_factory=PipelineRuntime)
    context: PlanningContext | None = None
    _parameter_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    _last_report: PipelineRunReport | None = None

    def __enter__(self) -> DebugSession:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def override(
        self,
        step: str,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        if parameters:
            self._parameter_overrides.setdefault(step, {}).update(parameters)

    def run_until(self, step: str) -> PipelineRunReport:
        request = RunRequest(
            selection=RunSelection.until(step),
            parameter_overrides=dict(self._parameter_overrides),
        )
        self._last_report = run_pipeline(
            self.pipeline_cls,
            profile=self.profile,
            request=request,
            runtime=self.runtime,
            context=self.context,
        )
        return self._last_report

    def run_one(self, step: str) -> PipelineRunReport:
        request = RunRequest(
            selection=RunSelection.only(step),
            parameter_overrides=dict(self._parameter_overrides),
        )
        self._last_report = run_pipeline(
            self.pipeline_cls,
            profile=self.profile,
            request=request,
            runtime=self.runtime,
            context=self.context,
        )
        return self._last_report

    def rerun(
        self,
        step: str,
        *,
        invalidate: str = "downstream",
    ) -> PipelineRunReport:
        mode = {
            "none": InvalidationMode.NONE,
            "target": InvalidationMode.TARGET,
            "downstream": InvalidationMode.DOWNSTREAM,
            "closure": InvalidationMode.CLOSURE,
        }.get(invalidate, InvalidationMode.DOWNSTREAM)
        request = RunRequest(
            selection=RunSelection.only(step),
            parameter_overrides=dict(self._parameter_overrides),
            invalidation=mode,
        )
        self._last_report = run_pipeline(
            self.pipeline_cls,
            profile=self.profile,
            request=request,
            runtime=self.runtime,
            context=self.context,
        )
        return self._last_report

    @property
    def last_report(self) -> PipelineRunReport | None:
        return self._last_report

    @property
    def succeeded(self) -> bool:
        return (
            self._last_report is not None
            and self._last_report.status is RunStatus.SUCCEEDED
        )
