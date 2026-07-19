"""Public run / arun helpers and debug session."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import anyio

from etlantic.exceptions import PipelineExecutionError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.model import PipelinePlan
from etlantic.plan.planner import plan_pipeline
from etlantic.registry import PlanningContext
from etlantic.reliability_runtime import invalidation_targets
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.artifacts import ArtifactStore
from etlantic.runtime.orchestrator import LocalOrchestrator
from etlantic.runtime.request import (
    InvalidationMode,
    RunRequest,
    RunSelection,
)
from etlantic.runtime.state import RunStatus


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


def _merge_plan_policies(request: RunRequest, plan: PipelinePlan) -> RunRequest:
    """Fill request retry/timeout defaults from plan execution_settings/intents."""
    settings = dict(plan.execution_settings or {})
    intents = dict(plan.intents or {})
    retry = request.retry
    timeout = request.timeout

    plan_attempts = settings.get("retry_max_attempts")
    if plan_attempts is None:
        plan_attempts = intents.get("retry_max_attempts")
    if retry.max_attempts == 1 and plan_attempts is not None:
        retry = replace(retry, max_attempts=max(1, int(plan_attempts)))

    plan_backoff = settings.get("retry_backoff_seconds") or intents.get(
        "retry_backoff_seconds"
    )
    if retry.backoff_seconds == 0.0 and plan_backoff is not None:
        retry = replace(retry, backoff_seconds=float(plan_backoff))

    plan_run_timeout = settings.get("timeout_seconds")
    if plan_run_timeout is None:
        plan_run_timeout = intents.get("timeout_seconds")
    if timeout.run_seconds is None and plan_run_timeout is not None:
        timeout = replace(timeout, run_seconds=float(plan_run_timeout))

    plan_step_timeout = settings.get("step_timeout_seconds") or intents.get(
        "step_timeout_seconds"
    )
    if timeout.step_seconds is None and plan_step_timeout is not None:
        timeout = replace(timeout, step_seconds=float(plan_step_timeout))

    if retry is request.retry and timeout is request.timeout:
        return request
    return RunRequest(
        selection=request.selection,
        intent=request.intent,
        materialization=request.materialization,
        retry=retry,
        timeout=timeout,
        cancellation=request.cancellation,
        parameter_overrides=dict(request.parameter_overrides),
        asset_overrides=dict(request.binding_overrides),
        implementation_overrides=dict(request.implementation_overrides),
        invalidation=request.invalidation,
        no_write=request.no_write,
        metadata=dict(request.metadata),
    )


async def arun_pipeline(
    pipeline_cls: type[Any],
    *,
    profile: str | Any = "development",
    request: RunRequest | None = None,
    runtime: PipelineRuntime | None = None,
    context: PlanningContext | None = None,
    workspace: str | Path | None = None,
    artifact_store: ArtifactStore | None = None,
) -> PipelineRunReport:
    """Validate, plan, and execute a pipeline asynchronously."""
    from etlantic.diagnostics import Severity
    from etlantic.exceptions import ETLanticError
    from etlantic.profile import resolve_profile

    request = request or RunRequest()
    runtime = runtime or PipelineRuntime()
    # Fail closed on production plugin trust before planning/execution.
    resolved = resolve_profile(profile)
    trust_diags = runtime.apply_plugin_allowlist(resolved)
    errors = [d for d in trust_diags if getattr(d, "severity", None) is Severity.ERROR]
    if errors:
        raise ETLanticError("; ".join(d.message for d in errors))
    graph = pipeline_cls.build_graph()
    selection = request.selection.to_plan_selection(graph)
    if context is None:
        context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(
        pipeline_cls,
        context=context,
        profile=profile,
        selection=selection,
    )
    request = _merge_plan_policies(request, plan)

    store = artifact_store or getattr(runtime, "_artifact_store", None)
    if store is None:
        store = ArtifactStore(workspace=Path(workspace) if workspace else None)
        runtime._artifact_store = store  # type: ignore[attr-defined]
    elif workspace is not None and store.workspace is None:
        store.workspace = Path(workspace)

    if request.invalidation is not InvalidationMode.NONE:
        consumers: dict[str, set[str]] = {
            n.name: set() for n in plan.logical_graph.nodes
        }
        for edge in plan.logical_graph.edges:
            consumers.setdefault(edge.producer_node, set()).add(edge.consumer_node)
        targets = set()
        selected = list(
            plan.selected_nodes or [n.name for n in plan.logical_graph.nodes]
        )
        for name in selected:
            targets |= invalidation_targets(
                graph_nodes=[n.name for n in plan.logical_graph.nodes],
                target=name,
                mode=request.invalidation,
                downstream=consumers,
            )
        # Invalidate logical outputs for affected nodes.
        keys = set()
        for node in plan.logical_graph.nodes:
            if node.name in targets:
                for port in node.outputs or ():
                    keys.add(f"{node.name}.{port.name}")
                keys.add(node.name)
        store.invalidate(keys)
        # Also clear memory bindings for sinks/sources on invalidated nodes.
        for node in plan.logical_graph.nodes:
            if node.name in targets and node.binding:
                runtime.memory._store.pop(node.binding, None)

    orch = LocalOrchestrator(
        runtime=runtime,
        plan=plan,
        request=request,
        pipeline_cls=pipeline_cls,
        workspace=Path(workspace) if workspace else store.workspace,
        artifacts=store,
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
    artifact_store: ArtifactStore | None = None,
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
            artifact_store=artifact_store,
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
    _artifacts: ArtifactStore = field(default_factory=ArtifactStore)

    def __enter__(self) -> DebugSession:
        self.runtime._artifact_store = self._artifacts  # type: ignore[attr-defined]
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
            artifact_store=self._artifacts,
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
            artifact_store=self._artifacts,
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
            artifact_store=self._artifacts,
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
