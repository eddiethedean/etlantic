"""Portable plan → backend-agnostic task graph mapping."""

from __future__ import annotations

from etlantic.orchestration.artifacts import (
    ArtifactTransportPolicy,
    validate_artifact_for_transport,
)
from etlantic.orchestration.protocol import (
    CompilationContext,
    CompilationDiagnostic,
    CompiledTask,
    ExecutionIntent,
    ScheduleIntent,
)
from etlantic.orchestration.reliability import apply_reliability_to_task
from etlantic.plan.model import PipelinePlan
from etlantic.profile import Profile


def schedule_from_profile(profile: Profile) -> ScheduleIntent:
    """Extract portable schedule intent from profile fields/metadata."""
    raw = profile.schedule or profile.metadata.get("schedule")
    if isinstance(raw, dict):
        return ScheduleIntent.from_mapping(raw)
    return ScheduleIntent()


def execution_from_profile(profile: Profile) -> ExecutionIntent:
    """Extract portable execution intent from profile fields/metadata."""
    raw = profile.execution or profile.metadata.get("execution")
    base = ExecutionIntent.from_mapping(raw if isinstance(raw, dict) else None)
    retries = base.retries
    if profile.retry_max_attempts is not None:
        retries = max(retries, max(0, int(profile.retry_max_attempts) - 1))
    timeout = base.timeout_seconds
    if profile.timeout_seconds is not None and timeout is None:
        timeout = float(profile.timeout_seconds)
    return ExecutionIntent(
        retries=retries,
        retry_delay_seconds=base.retry_delay_seconds,
        timeout_seconds=timeout,
        max_active_runs=base.max_active_runs,
        metadata=dict(base.metadata),
    )


def context_from_profile(
    profile: Profile,
    *,
    target: str,
    max_inline_bytes: int = 65_536,
) -> CompilationContext:
    """Build a compilation context from a profile."""
    required = tuple(
        str(x)
        for x in (
            profile.required_orchestrator_capabilities
            or profile.metadata.get("required_orchestrator_capabilities")
            or profile.metadata.get("required_capabilities")
            or ()
        )
    )
    return CompilationContext(
        target=target,
        schedule=schedule_from_profile(profile),
        execution=execution_from_profile(profile),
        required_capabilities=required,
        max_inline_bytes=max_inline_bytes,
        metadata={
            "etlantic.profile": profile.name,
            "etlantic.orchestrator": profile.orchestrator,
        },
    )


def dag_id_for_plan(plan: PipelinePlan) -> str:
    """Deterministic DAG / workflow id from plan identity."""
    raw = plan.pipeline_name or plan.pipeline_id
    # Airflow dag_id: letters, numbers, dashes, dots, underscores.
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in raw)
    cleaned = cleaned.strip("_") or "etlantic_pipeline"
    if cleaned[0].isdigit():
        cleaned = f"p_{cleaned}"
    return cleaned.lower()


def map_plan_to_tasks(
    plan: PipelinePlan,
    *,
    context: CompilationContext,
) -> tuple[
    tuple[CompiledTask, ...], dict[str, tuple[str, ...]], list[CompilationDiagnostic]
]:
    """Map logical graph nodes/edges to a compiled task graph."""
    diagnostics: list[CompilationDiagnostic] = []
    policy = ArtifactTransportPolicy(max_inline_bytes=context.max_inline_bytes)

    node_names = [n.name for n in plan.logical_graph.nodes]
    selected = set(plan.selected_nodes) if plan.selected_nodes is not None else None
    if selected is not None:
        node_names = [n for n in node_names if n in selected]

    # Upstream deps from edges.
    deps: dict[str, list[str]] = {name: [] for name in node_names}
    for edge in plan.logical_graph.edges:
        if (
            edge.consumer_node in deps
            and edge.producer_node in deps
            and edge.producer_node not in deps[edge.consumer_node]
        ):
            deps[edge.consumer_node].append(edge.producer_node)

    # Artifact outputs by node.
    artifacts_by_node: dict[str, list] = {name: [] for name in node_names}
    for resolution in plan.output_resolutions:
        if resolution.node_name not in artifacts_by_node:
            continue
        art = resolution.artifact
        # Secret-free check for every strategy before external orchestration.
        diagnostics.extend(validate_artifact_for_transport(art, policy=policy))
        artifacts_by_node[resolution.node_name].append(art)

    tasks: list[CompiledTask] = []
    for node in plan.logical_graph.nodes:
        if node.name not in deps:
            continue
        task = CompiledTask(
            task_id=node.name,
            node_name=node.name,
            node_kind=node.kind.value,
            dependencies=tuple(deps[node.name]),
            artifact_outputs=tuple(artifacts_by_node.get(node.name) or ()),
            metadata={
                "identity": node.identity,
                "binding": node.binding,
                "transformation_id": node.transformation_id,
            },
        )
        task, rel_diags = apply_reliability_to_task(
            task, plan=plan, execution=context.execution
        )
        diagnostics.extend(rel_diags)
        tasks.append(task)

    dep_map = {t.task_id: t.dependencies for t in tasks}
    return tuple(tasks), dep_map, diagnostics
