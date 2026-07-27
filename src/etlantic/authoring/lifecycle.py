"""Lifecycle operations that accept PipelineDefinition without originating classes."""

from __future__ import annotations

from typing import Any

from etlantic.authoring.definition import PipelineDefinition
from etlantic.authoring.normalize import logical_graph_from_definition
from etlantic.authoring.resolve import callable_registry, resolve_definition
from etlantic.authoring.types import (
    PipelineLike,
    is_pipeline_class,
    pipeline_display_name,
)
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.exceptions import PipelineValidationError
from etlantic.model import LogicalGraph, NodeKind
from etlantic.plan.model import PipelinePlan
from etlantic.registry import PlanningContext


def build_graph(pipeline: PipelineLike) -> LogicalGraph:
    """Return the logical graph for a class or definition."""
    if is_pipeline_class(pipeline):
        return pipeline.build_graph()
    assert isinstance(pipeline, PipelineDefinition)
    return logical_graph_from_definition(pipeline)


def validate_pipeline_like(
    pipeline: PipelineLike,
    *,
    context: PlanningContext | None = None,
    profile: str | Any | None = None,
    policy: str | Any | None = None,
) -> ValidationReport:
    """Validate a pipeline class or PipelineDefinition."""
    from etlantic.validation import validate_pipeline

    if is_pipeline_class(pipeline):
        return validate_pipeline(
            pipeline, context=context, profile=profile, policy=policy
        )
    assert isinstance(pipeline, PipelineDefinition)
    return _validate_definition(
        pipeline, context=context, profile=profile, policy=policy
    )


def _tag_phase(diagnostics: list[Diagnostic], phase: str) -> list[Diagnostic]:
    tagged: list[Diagnostic] = []
    for diagnostic in diagnostics:
        if diagnostic.phase == phase:
            tagged.append(diagnostic)
            continue
        tagged.append(
            Diagnostic(
                code=diagnostic.code,
                severity=diagnostic.severity,
                message=diagnostic.message,
                path=diagnostic.path,
                help=diagnostic.help,
                related=diagnostic.related,
                source=diagnostic.source,
                metadata=diagnostic.metadata,
                phase=phase,
                actions=diagnostic.actions,
            )
        )
    return tagged


def _validate_definition(
    defn: PipelineDefinition,
    *,
    context: PlanningContext | None = None,
    profile: str | Any | None = None,
    policy: str | Any | None = None,
) -> ValidationReport:
    from etlantic.policy import resolve_validation_policy
    from etlantic.validation import VALIDATION_PHASES
    from etlantic.validation.phases.capability import phase_capability
    from etlantic.validation.phases.plugin_trust import phase_plugin_trust

    defn, ctx, resolve_report = resolve_definition(
        defn, context=context, profile=profile
    )
    resolved_policy = resolve_validation_policy(
        policy or ctx.profile.validation_policy
    )
    diagnostics: list[Diagnostic] = list(resolve_report.diagnostics)
    graph = logical_graph_from_definition(defn)
    diagnostics.extend(_tag_phase(_validate_definition_graph(defn, graph), "structural"))
    diagnostics.extend(
        _tag_phase(
            _validate_definition_references(defn, graph, ctx, resolved_policy),
            "reference",
        )
    )
    diagnostics.extend(_tag_phase(_validate_definition_semantic(graph), "semantic"))
    diagnostics.extend(
        _tag_phase(
            _validate_definition_policy(defn, graph, ctx, resolved_policy), "policy"
        )
    )
    diagnostics.extend(
        _tag_phase(phase_capability(None, ctx, resolved_policy), "capability")
    )
    diagnostics.extend(_tag_phase(phase_plugin_trust(ctx), "plugin_trust"))
    return ValidationReport.from_diagnostics(diagnostics, phases=VALIDATION_PHASES)


def _validate_definition_graph(
    defn: PipelineDefinition, graph: LogicalGraph
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    names = [n.name for n in graph.nodes]
    seen: set[str] = set()
    for name in names:
        if name in seen:
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE110",
                    severity=Severity.ERROR,
                    message=f'Duplicate node identity "{name}".',
                    path=("pipeline", name),
                )
            )
        seen.add(name)
    node_names = set(names)
    for edge in graph.edges:
        if edge.producer_node not in node_names or edge.consumer_node not in node_names:
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE201",
                    severity=Severity.ERROR,
                    message=(
                        f'Unknown edge endpoint '
                        f'"{edge.producer_node}" -> "{edge.consumer_node}".'
                    ),
                    path=("pipeline", edge.consumer_node, edge.consumer_port),
                )
            )
    edge_keys = {(e.consumer_node, e.consumer_port) for e in graph.edges}
    for node in defn.nodes:
        if node.kind == "step":
            for port in node.inputs:
                if port.required and (node.name, port.name) not in edge_keys:
                    diagnostics.append(
                        Diagnostic(
                            code="PMPIPE201",
                            severity=Severity.ERROR,
                            message=(
                                f'Missing required input "{port.name}" on step '
                                f'"{node.name}".'
                            ),
                            path=("nodes", node.name, "inputs", port.name),
                        )
                    )
        if node.kind == "sink" and (node.name, "input") not in edge_keys:
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE201",
                    severity=Severity.ERROR,
                    message=f'Could not resolve input for load "{node.name}".',
                    path=("nodes", node.name, "inputs", "input"),
                )
            )
    return diagnostics


def _validate_definition_references(
    defn: PipelineDefinition,
    graph: LogicalGraph,
    context: PlanningContext,
    policy: Any,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for node in graph.nodes:
        if node.binding and getattr(policy, "require_bindings", False):
            resolved = (
                node.binding in context.registry.bindings
                or node.binding in context.profile.bindings
            )
            if not resolved:
                diagnostics.append(
                    Diagnostic(
                        code="PMPLAN201",
                        severity=Severity.ERROR,
                        message=(
                            f"Node '{node.name}' has no asset resolution for "
                            f"'{node.binding}' in profile '{context.profile.name}'."
                        ),
                        path=("nodes", node.name, "asset"),
                    )
                )
    known_transforms = {t.identity for t in defn.transformations}
    for node in defn.nodes:
        if node.kind == "step" and node.transformation_id not in known_transforms:
            diagnostics.append(
                Diagnostic(
                    code="PMAUTH201",
                    severity=Severity.ERROR,
                    message=(
                        f"Step '{node.name}' references unknown transformation "
                        f"{node.transformation_id!r}."
                    ),
                    path=("nodes", node.name, "transformation_id"),
                )
            )
    return diagnostics


def _validate_definition_semantic(graph: LogicalGraph) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    nodes = graph.node_map()
    for edge in graph.edges:
        producer = nodes.get(edge.producer_node)
        consumer = nodes.get(edge.consumer_node)
        if producer is None or consumer is None:
            continue
        producer_port = next(
            (p for p in producer.outputs if p.name == edge.producer_port), None
        )
        consumer_port = next(
            (p for p in consumer.inputs if p.name == edge.consumer_port), None
        )
        if producer_port and producer_port.role == "invalid":
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE220",
                    severity=Severity.ERROR,
                    message=(
                        f'Invalid-output port "{edge.producer_node}.'
                        f'{edge.producer_port}" cannot feed '
                        f'"{edge.consumer_node}.{edge.consumer_port}".'
                    ),
                    path=("nodes", edge.consumer_node, "inputs", edge.consumer_port),
                )
            )
        if (
            producer_port
            and consumer_port
            and producer_port.contract_id
            and consumer_port.contract_id
            and producer_port.contract_id != consumer_port.contract_id
        ):
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE210",
                    severity=Severity.ERROR,
                    message=(
                        f'Contract mismatch: {edge.producer_node}.{edge.producer_port} '
                        f'({producer_port.contract_id}) -> '
                        f'{edge.consumer_node}.{edge.consumer_port} '
                        f'({consumer_port.contract_id}).'
                    ),
                    path=("nodes", edge.consumer_node, "inputs", edge.consumer_port),
                )
            )
    return diagnostics


def _validate_definition_policy(
    defn: PipelineDefinition,
    graph: LogicalGraph,
    context: PlanningContext,
    policy: Any,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not getattr(policy, "require_implementations", False):
        return diagnostics
    xf_by_id = {t.identity: t for t in defn.transformations}
    registry = callable_registry()
    for node in graph.nodes:
        if node.kind is not NodeKind.STEP or not node.transformation_id:
            continue
        xf = xf_by_id.get(node.transformation_id)
        if xf is None:
            continue
        engine = context.profile.implementation_overrides.get(node.name)
        if engine is None:
            engine = context.profile.dataframe_engine or "local"
        has_ref = any(r.engine == engine for r in xf.implementation_refs)
        has_live = registry.get(node.transformation_id, engine) is not None
        has_portable = xf.portable_plan is not None
        if not (has_ref or has_live or has_portable):
            diagnostics.append(
                Diagnostic(
                    code="PMPLAN301",
                    severity=Severity.ERROR,
                    message=(
                        f"No implementation for step '{node.name}' "
                        f"(transformation {node.transformation_id}, engine {engine!r})."
                    ),
                    path=("nodes", node.name, "implementation"),
                )
            )
    return diagnostics


def plan_pipeline_like(
    pipeline: PipelineLike,
    *,
    context: PlanningContext | None = None,
    profile: str | Any | None = None,
    selection: dict[str, Any] | None = None,
) -> PipelinePlan:
    """Plan a pipeline class or PipelineDefinition."""
    from etlantic.plan.planner import plan_pipeline

    if is_pipeline_class(pipeline):
        return plan_pipeline(
            pipeline, context=context, profile=profile, selection=selection
        )
    assert isinstance(pipeline, PipelineDefinition)
    return _plan_definition(
        pipeline, context=context, profile=profile, selection=selection
    )


def _plan_definition(
    defn: PipelineDefinition,
    *,
    context: PlanningContext | None = None,
    profile: str | Any | None = None,
    selection: dict[str, Any] | None = None,
) -> PipelinePlan:
    from etlantic.plan import planner as planner_mod

    defn, ctx, _resolve_report = resolve_definition(
        defn, context=context, profile=profile
    )
    report = _validate_definition(defn, context=ctx)
    if report.has_errors:
        raise PipelineValidationError(
            f"Cannot plan invalid pipeline {pipeline_display_name(defn)}.",
            report=report,
        )
    return planner_mod._build_plan_from_definition(
        defn, ctx, selection=selection or ctx.selection
    )


def inspect_pipeline_like(pipeline: PipelineLike) -> LogicalGraph:
    return build_graph(pipeline)
