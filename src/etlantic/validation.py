"""Multi-phase validation for ETLantic pipelines (0.3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from etlantic.contracts import is_data_contract_type
from etlantic.diagnostics import (
    Diagnostic,
    DiagnosticAction,
    Severity,
    SourceLocation,
    ValidationReport,
)
from etlantic.identity import contract_id, published_contract_id
from etlantic.model import LogicalGraph
from etlantic.policy import ValidationPolicy, resolve_validation_policy
from etlantic.symbols import node_symbol, pipeline_symbol, port_symbol
from etlantic.transformation import Step, Transformation

if TYPE_CHECKING:
    from etlantic.pipeline import Pipeline
    from etlantic.registry import PlanningContext


VALIDATION_PHASES = (
    "structural",
    "reference",
    "semantic",
    "policy",
    "capability",
    "plugin_trust",
)


def validate_pipeline(
    pipeline_cls: type[Pipeline],
    *,
    context: PlanningContext | None = None,
    profile: str | Any | None = None,
    policy: str | ValidationPolicy | None = None,
) -> ValidationReport:
    """Validate a pipeline through structural → capability phases."""
    from etlantic.registry import PlanningContext

    if context is None:
        context = PlanningContext.create(profile=profile)
    resolved_policy = resolve_validation_policy(
        policy or context.profile.validation_policy
    )

    diagnostics: list[Diagnostic] = []

    # Phase 1: structural
    structural = _phase_structural(pipeline_cls, context, resolved_policy)
    diagnostics.extend(_tag_phase(structural, "structural"))

    graph = pipeline_cls.build_graph()

    # Phase 2: reference
    reference = _phase_reference(graph, pipeline_cls, context, resolved_policy)
    diagnostics.extend(_tag_phase(reference, "reference"))

    # Phase 3: semantic
    semantic = _phase_semantic(graph, pipeline_cls)
    diagnostics.extend(_tag_phase(semantic, "semantic"))

    # Phase 4: policy
    policy_diags = _phase_policy(graph, pipeline_cls, context, resolved_policy)
    diagnostics.extend(_tag_phase(policy_diags, "policy"))

    # Phase 5: capability
    capability = _phase_capability(pipeline_cls, context, resolved_policy)
    diagnostics.extend(_tag_phase(capability, "capability"))

    # Phase 6: plugin trust (production allowlist fail-closed)
    trust = _phase_plugin_trust(context)
    diagnostics.extend(_tag_phase(trust, "plugin_trust"))

    if resolved_policy.warnings_as_errors:
        diagnostics = [
            Diagnostic(
                code=d.code,
                severity=Severity.ERROR
                if d.severity is Severity.WARNING
                else d.severity,
                message=d.message,
                path=d.path,
                help=d.help,
                related=d.related,
                source=d.source,
                metadata=d.metadata,
                phase=d.phase,
                actions=d.actions,
            )
            if d.severity is Severity.WARNING
            else d
            for d in diagnostics
        ]

    return ValidationReport.from_diagnostics(diagnostics, phases=VALIDATION_PHASES)


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


def _phase_structural(
    pipeline_cls: type[Pipeline],
    context: PlanningContext,
    policy: ValidationPolicy,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_validate_member_definitions(pipeline_cls))
    diagnostics.extend(
        _validate_nested_subpipelines(pipeline_cls, context=context, policy=policy)
    )
    graph = pipeline_cls.build_graph()
    build_error = getattr(pipeline_cls, "_graph_build_error", None)
    if build_error:
        sym = pipeline_symbol(pipeline_cls)
        diagnostics.append(
            Diagnostic(
                code="PMPIPE302",
                severity=Severity.ERROR,
                message=build_error,
                path=("pipeline",),
                source=SourceLocation(
                    object_ref=sym.as_object_ref(), symbol=sym.identity
                ),
            )
        )
    diagnostics.extend(_validate_graph(graph, pipeline_cls))
    return diagnostics


def _phase_reference(
    graph: LogicalGraph,
    pipeline_cls: type[Pipeline],
    context: PlanningContext,
    policy: ValidationPolicy,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    pid = graph.pipeline_id
    for node in graph.nodes:
        if node.binding and policy.require_bindings:
            resolved = (
                node.binding in context.registry.bindings
                or node.binding in context.profile.bindings
            )
            if not resolved:
                sym = node_symbol(pid, node.name, kind=node.kind.value)
                role = (
                    "Extract"
                    if node.kind.value == "source"
                    else "Load"
                    if node.kind.value == "sink"
                    else "Node"
                )
                diagnostics.append(
                    Diagnostic(
                        code="PMPLAN201",
                        severity=Severity.ERROR,
                        message=(
                            f"{role} '{node.name}' has no asset resolution for "
                            f"'{node.binding}' in profile '{context.profile.name}'."
                        ),
                        path=("pipeline", node.name, "asset"),
                        source=SourceLocation(
                            object_ref=sym.as_object_ref(),
                            symbol=sym.identity,
                        ),
                        actions=(
                            DiagnosticAction(
                                kind="add_binding",
                                title=f'Add asset "{node.binding}" to the profile',
                                edit_suggestion=(
                                    f'profile.assets["{node.binding}"] = "..."'
                                ),
                                arguments={
                                    "binding": node.binding,
                                    "asset": node.binding,
                                },
                            ),
                        ),
                    )
                )
        if (
            policy.require_published_contract_ids
            and node.contract_type is not None
            and published_contract_id(node.contract_type) is None
        ):
            diagnostics.append(
                Diagnostic(
                    code="PMPLAN202",
                    severity=Severity.WARNING,
                    message=(f'Node "{node.name}" contract lacks a published ODCS id.'),
                    path=("pipeline", node.name),
                )
            )
    return diagnostics


def _phase_semantic(
    graph: LogicalGraph, pipeline_cls: type[Pipeline]
) -> list[Diagnostic]:
    diagnostics = _validate_port_compatibility(graph, pipeline_cls)
    # Valid/invalid output roles: invalid outputs must not feed required inputs
    nodes = graph.node_map()
    for edge in graph.edges:
        producer = nodes.get(edge.producer_node)
        if producer is None:
            continue
        producer_port = next(
            (p for p in producer.outputs if p.name == edge.producer_port), None
        )
        if producer_port is None:
            continue
        if producer_port.role == "invalid":
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE220",
                    severity=Severity.ERROR,
                    message=(
                        f'Invalid-output port "{edge.producer_node}.'
                        f'{edge.producer_port}" cannot feed '
                        f'"{edge.consumer_node}.{edge.consumer_port}".'
                    ),
                    path=("pipeline", edge.consumer_node, edge.consumer_port),
                    related=(("pipeline", edge.producer_node, edge.producer_port),),
                    help="Wire invalid outputs only to dedicated invalid sinks.",
                    source=SourceLocation(
                        object_ref=port_symbol(
                            graph.pipeline_id,
                            edge.producer_node,
                            edge.producer_port,
                        ).as_object_ref()
                    ),
                )
            )
    return diagnostics


def _phase_policy(
    graph: LogicalGraph,
    pipeline_cls: type[Pipeline],
    context: PlanningContext,
    policy: ValidationPolicy,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not policy.require_implementations:
        return diagnostics
    portable_policy = (
        getattr(context.profile, "portable_transform_policy", "prefer") or "prefer"
    )
    for node in graph.nodes:
        if node.kind.value != "step" or not node.transformation_id:
            continue
        engine = context.profile.implementation_overrides.get(node.name)
        if engine is None:
            engine = context.profile.dataframe_engine or "local"
        transform_cls = None
        member = pipeline_cls.__pipeline_members__.get(node.name)
        if isinstance(member, Step):
            transform_cls = member.transformation
        if transform_cls is None:
            continue
        impls = transform_cls.implementations()
        has_portable = (
            hasattr(transform_cls, "portable_definition")
            and transform_cls.portable_definition() is not None
        )
        # Portable-capable steps may satisfy prefer/require without a native
        # callable when a transform compiler exists for the engine.
        if (
            has_portable
            and portable_policy in {"prefer", "require"}
            and engine != "local"
        ):
            from etlantic.transform.compiler import TransformPlanningContext
            from etlantic.transform.discovery import load_transform_compiler

            compiler = load_transform_compiler(engine)
            if compiler is not None:
                if portable_policy == "prefer":
                    # Prefer: compiler presence is enough at validate-time;
                    # unsupported IR falls back at plan-time.
                    continue
                # Require: fail closed unless analyze() accepts the plan.
                portable_def = transform_cls.portable_definition()
                assert portable_def is not None
                report = compiler.analyze(
                    portable_def.plan,
                    context=TransformPlanningContext(
                        pipeline_id=graph.pipeline_id,
                        step_name=node.name,
                        profile_name=context.profile.name,
                        engine=engine,
                    ),
                    requirements=portable_def.requirements,
                )
                if report.supported:
                    continue
                for finding in report.findings:
                    diagnostics.append(
                        Diagnostic(
                            code=finding.code or "PMXFORM301",
                            severity=Severity.ERROR,
                            message=(
                                f'Step "{node.name}": {finding.requirement} — '
                                f"{finding.reason}"
                            ),
                            path=("pipeline", node.name),
                        )
                    )
                continue
            if portable_policy == "prefer" and engine in impls:
                continue
            if portable_policy == "require":
                diagnostics.append(
                    Diagnostic(
                        code="PMXFORM302",
                        severity=Severity.ERROR,
                        message=(
                            f'Step "{node.name}" requires portable compilation '
                            f"but no transform compiler is registered for "
                            f"engine {engine!r}."
                        ),
                        path=("pipeline", node.name),
                    )
                )
                continue
        # Strict policy requires a registered transformation implementation;
        # registry engine presence alone is not sufficient.
        if engine not in impls:
            diagnostics.append(
                Diagnostic(
                    code="PMPLAN301",
                    severity=Severity.ERROR,
                    message=(
                        f'Step "{node.name}" has no implementation for engine '
                        f"{engine!r}."
                    ),
                    path=("pipeline", node.name),
                    actions=(
                        DiagnosticAction(
                            kind="register_implementation",
                            title=f'Register an implementation for "{engine}"',
                            arguments={"engine": engine, "step": node.name},
                        ),
                    ),
                )
            )
    return diagnostics


def _phase_capability(
    pipeline_cls: type[Pipeline],
    context: PlanningContext,
    policy: ValidationPolicy,
) -> list[Diagnostic]:
    from etlantic.capabilities import CapabilityDecision, negotiate_capabilities

    diagnostics: list[Diagnostic] = []
    engine_name = (
        context.profile.spark_engine
        if context.profile.spark_engine
        else (
            context.profile.sql_engine
            if context.profile.sql_engine
            else (context.profile.dataframe_engine or "local")
        )
    )
    available = context.registry.engines.get(engine_name)
    if available is None:
        if context.profile.spark_engine:
            engine_field = "spark_engine"
        elif context.profile.sql_engine:
            engine_field = "sql_engine"
        else:
            engine_field = "dataframe_engine"
        diagnostics.append(
            Diagnostic(
                code="PMPLAN401",
                severity=Severity.ERROR,
                message=f"No plugin capabilities registered for engine {engine_name!r}.",
                path=("profile", context.profile.name, engine_field),
            )
        )
        return diagnostics

    fallback = None
    if context.fallback_engine:
        fallback = context.registry.engines.get(context.fallback_engine)
    allow_fallback = context.allow_capability_fallback or bool(
        policy.allowed_capability_fallbacks
    )
    negotiations = negotiate_capabilities(
        requirements=context.required_capabilities,
        available=available,
        fallback=fallback,
        allow_fallback=allow_fallback,
    )
    for item in negotiations:
        if item.decision is CapabilityDecision.UNSUPPORTED:
            diagnostics.append(
                Diagnostic(
                    code="PMPLAN402",
                    severity=Severity.ERROR,
                    message=item.message
                    or f"Unsupported capability {item.requirement!r}.",
                    path=("capability", item.requirement),
                    metadata=item.to_dict(),
                )
            )
        elif item.decision is CapabilityDecision.FALLBACK:
            diagnostics.append(
                Diagnostic(
                    code="PMPLAN403",
                    severity=Severity.WARNING,
                    message=item.message
                    or f"Using fallback for capability {item.requirement!r}.",
                    path=("capability", item.requirement),
                    metadata=item.to_dict(),
                )
            )
    return diagnostics


def _phase_plugin_trust(context: PlanningContext) -> list[Diagnostic]:
    """Enforce production plugin_allowlist fail-closed (empty list is an error).

    Checks plugins selected by the profile engines (and their transform
    compilers). Built-in ``local``/``null`` stubs are included only when those
    engines are selected so unrelated installed plugins do not spuriously fail
    local production templates.
    """
    from etlantic.plugin_trust import filter_plugins_by_allowlist
    from etlantic.transform.discovery import discover_transform_compilers

    profile = context.profile
    selected: dict[str, object] = {}
    selected_engines = {
        eng
        for eng in (
            profile.dataframe_engine,
            profile.sql_engine,
            profile.spark_engine,
            profile.orchestrator,
        )
        if eng
    }
    for name, descriptor in context.registry.plugins.items():
        engine = getattr(descriptor, "engine", None)
        if name in selected_engines or engine in selected_engines:
            selected[name] = descriptor

    for engine, compiler in discover_transform_compilers().items():
        if engine in selected_engines:
            selected[f"transform_compiler:{engine}"] = compiler

    _kept, diagnostics = filter_plugins_by_allowlist(selected, profile)
    return list(diagnostics)


def _validate_nested_subpipelines(
    pipeline_cls: type[Pipeline],
    *,
    context: PlanningContext,
    policy: ValidationPolicy,
) -> list[Diagnostic]:
    """Recursively validate embedded subpipeline definitions with parent context."""
    from etlantic.pipeline import SubpipelineInstance

    diagnostics: list[Diagnostic] = []
    for name, member in pipeline_cls.__pipeline_members__.items():
        if not isinstance(member, SubpipelineInstance):
            continue
        child_report = validate_pipeline(
            member.pipeline_cls, context=context, policy=policy
        )
        for diagnostic in child_report.diagnostics:
            diagnostics.append(
                Diagnostic(
                    code=diagnostic.code,
                    severity=diagnostic.severity,
                    message=diagnostic.message,
                    path=("pipeline", name, *diagnostic.path),
                    help=diagnostic.help,
                    related=diagnostic.related,
                    source=diagnostic.source,
                    metadata={**diagnostic.metadata, "subpipeline": name},
                    phase=diagnostic.phase,
                    actions=diagnostic.actions,
                )
            )
    return diagnostics


def _validate_member_definitions(pipeline_cls: type[Pipeline]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    members = pipeline_cls.__pipeline_members__

    for name, member in members.items():
        if isinstance(member, Step):
            transform = member.transformation
            for problem in transform.validate_definition():
                diagnostics.append(
                    Diagnostic(
                        code="PMTRN001",
                        severity=Severity.ERROR,
                        message=problem,
                        path=("pipeline", name),
                    )
                )
            for port in transform.inputs():
                if port.name not in member.bindings:
                    diagnostics.append(
                        Diagnostic(
                            code="PMTRN101",
                            severity=Severity.ERROR,
                            message=(
                                f'Step "{name}" is missing required input '
                                f'"{port.name}".'
                            ),
                            path=("pipeline", name, port.name),
                            help=(
                                "Pass the input when calling Transformation.step(...)."
                            ),
                        )
                    )
                else:
                    diagnostics.extend(
                        _validate_binding_present(
                            member.bindings[port.name],
                            consumer=("pipeline", name, port.name),
                        )
                    )
                if port.contract_type is not None and not is_data_contract_type(
                    port.contract_type
                ):
                    diagnostics.append(
                        Diagnostic(
                            code="PMDATA101",
                            severity=Severity.ERROR,
                            message=(
                                f'Input "{port.name}" on {transform.__name__} '
                                f"does not reference a ContractModel type."
                            ),
                            path=("transformation", transform.__name__, port.name),
                        )
                    )
            for port in transform.outputs():
                if port.contract_type is not None and not is_data_contract_type(
                    port.contract_type
                ):
                    diagnostics.append(
                        Diagnostic(
                            code="PMDATA102",
                            severity=Severity.ERROR,
                            message=(
                                f'Output "{port.name}" on {transform.__name__} '
                                f"does not reference a ContractModel type."
                            ),
                            path=("transformation", transform.__name__, port.name),
                        )
                    )
            for port in transform.parameters():
                if not port.has_default and port.name not in member.parameters:
                    diagnostics.append(
                        Diagnostic(
                            code="PMTRN102",
                            severity=Severity.ERROR,
                            message=(
                                f'Step "{name}" is missing required parameter '
                                f'"{port.name}".'
                            ),
                            path=("pipeline", name, port.name),
                        )
                    )

        elif hasattr(member, "contract_type"):
            ctype = member.contract_type
            if ctype is not None and not is_data_contract_type(ctype):
                diagnostics.append(
                    Diagnostic(
                        code="PMDATA103",
                        severity=Severity.ERROR,
                        message=(
                            f'Node "{name}" contract type is not a ContractModel '
                            f"subclass."
                        ),
                        path=("pipeline", name),
                    )
                )

    return diagnostics


def _validate_binding_present(
    value: Any, *, consumer: tuple[str, ...]
) -> list[Diagnostic]:
    if value is None:
        return [
            Diagnostic(
                code="PMPIPE201",
                severity=Severity.ERROR,
                message="Input binding is missing.",
                path=consumer,
            )
        ]
    return []


def _validate_graph(
    graph: LogicalGraph, pipeline_cls: type[Pipeline]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    names = [node.name for node in graph.nodes]
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
        if edge.producer_node not in node_names:
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE201",
                    severity=Severity.ERROR,
                    message=(
                        f'Unknown producer "{edge.producer_node}" wired to '
                        f'"{edge.consumer_node}.{edge.consumer_port}".'
                    ),
                    path=("pipeline", edge.consumer_node, edge.consumer_port),
                    related=(("pipeline", edge.producer_node),),
                )
            )
        if edge.consumer_node not in node_names:
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE201",
                    severity=Severity.ERROR,
                    message=f'Unknown consumer "{edge.consumer_node}".',
                    path=("pipeline", edge.consumer_node),
                )
            )

    # Missing edge for required step inputs already covered; also detect
    # unresolved refs where binding existed but no edge was created.
    members = pipeline_cls.__pipeline_members__
    edge_keys = {(e.consumer_node, e.consumer_port) for e in graph.edges}
    for name, member in members.items():
        if isinstance(member, Step):
            for port in member.transformation.inputs():
                if port.name in member.bindings and (name, port.name) not in edge_keys:
                    diagnostics.append(
                        Diagnostic(
                            code="PMPIPE201",
                            severity=Severity.ERROR,
                            message=(
                                f'Could not resolve input "{port.name}" on step '
                                f'"{name}".'
                            ),
                            path=("pipeline", name, port.name),
                            help="Bind a Source, Step output, or OutputRef.",
                        )
                    )
        from etlantic.pipeline import Load, SubpipelineInstance

        if isinstance(member, Load) and (name, "input") not in edge_keys:
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE201",
                    severity=Severity.ERROR,
                    message=f'Could not resolve input for load "{name}".',
                    path=("pipeline", name, "input"),
                )
            )
        if isinstance(member, SubpipelineInstance):
            node = graph.node_map().get(name)
            public_inputs = {p.name for p in node.inputs} if node else set()
            for port_name in member.bindings:
                if port_name not in public_inputs:
                    diagnostics.append(
                        Diagnostic(
                            code="PMPIPE201",
                            severity=Severity.ERROR,
                            message=(
                                f'Unknown subpipeline input "{port_name}" on "{name}".'
                            ),
                            path=("pipeline", name, port_name),
                            help=(
                                "Bind only public source ports exposed by the "
                                "child pipeline."
                            ),
                        )
                    )
                elif (name, port_name) not in edge_keys:
                    diagnostics.append(
                        Diagnostic(
                            code="PMPIPE201",
                            severity=Severity.ERROR,
                            message=(
                                f'Could not resolve subpipeline input "{port_name}" '
                                f'on "{name}".'
                            ),
                            path=("pipeline", name, port_name),
                        )
                    )

    diagnostics.extend(_detect_cycles(graph))
    return diagnostics


def _detect_cycles(graph: LogicalGraph) -> list[Diagnostic]:
    """Detect directed cycles using DFS."""
    adjacency: dict[str, list[str]] = {n.name: [] for n in graph.nodes}
    for edge in graph.edges:
        adjacency.setdefault(edge.producer_node, []).append(edge.consumer_node)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in adjacency}
    diagnostics: list[Diagnostic] = []
    stack: list[str] = []

    def visit(node: str) -> None:
        color[node] = GRAY
        stack.append(node)
        for nxt in adjacency.get(node, []):
            if color.get(nxt, WHITE) == GRAY:
                cycle_start = stack.index(nxt)
                cycle = [*stack[cycle_start:], nxt]
                diagnostics.append(
                    Diagnostic(
                        code="PMPIPE301",
                        severity=Severity.ERROR,
                        message=f"Pipeline contains a cycle: {' -> '.join(cycle)}.",
                        path=("pipeline",),
                        metadata={"cycle": cycle},
                    )
                )
            elif color.get(nxt, WHITE) == WHITE:
                visit(nxt)
        stack.pop()
        color[node] = BLACK

    for name in adjacency:
        if color[name] == WHITE:
            visit(name)

    return diagnostics


def _validate_port_compatibility(
    graph: LogicalGraph, pipeline_cls: type[Pipeline]
) -> list[Diagnostic]:
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
        if producer_port is None:
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE201",
                    severity=Severity.ERROR,
                    message=(
                        f'Unknown producer port "{edge.producer_port}" on '
                        f'"{edge.producer_node}" wired to '
                        f'"{edge.consumer_node}.{edge.consumer_port}".'
                    ),
                    path=("pipeline", edge.consumer_node, edge.consumer_port),
                    related=(("pipeline", edge.producer_node, edge.producer_port),),
                )
            )
            continue
        if consumer_port is None:
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE201",
                    severity=Severity.ERROR,
                    message=(
                        f'Unknown consumer port "{edge.consumer_port}" on '
                        f'"{edge.consumer_node}".'
                    ),
                    path=("pipeline", edge.consumer_node, edge.consumer_port),
                )
            )
            continue

        prod_type = producer_port.contract_type
        cons_type = consumer_port.contract_type
        if prod_type is None or cons_type is None:
            continue

        if not _contracts_compatible(prod_type, cons_type):
            diagnostics.append(
                Diagnostic(
                    code="PMPIPE210",
                    severity=Severity.ERROR,
                    message=(
                        f'The step "{edge.consumer_node}" expects '
                        f"{getattr(cons_type, '__name__', cons_type)} on "
                        f'"{edge.consumer_port}", but received '
                        f"{getattr(prod_type, '__name__', prod_type)} from "
                        f'"{edge.producer_node}.{edge.producer_port}".'
                    ),
                    path=("pipeline", edge.consumer_node, edge.consumer_port),
                    related=(("pipeline", edge.producer_node, edge.producer_port),),
                    help=(
                        "Connect a compatible output or change the consumer contract."
                    ),
                    metadata={
                        "producer_contract": contract_id(prod_type),
                        "consumer_contract": contract_id(cons_type),
                        "producer_published_id": published_contract_id(prod_type),
                        "consumer_published_id": published_contract_id(cons_type),
                    },
                )
            )

    return diagnostics


def _contracts_compatible(producer: type[Any], consumer: type[Any]) -> bool:
    """Return True when producer/consumer contracts are the same logical type.

    Exact Python identity remains the primary check. Distinct classes that share
    the same published ODCS/CCM identity (common after ODCS load) are also
    treated as compatible.
    """
    if producer is consumer:
        return True
    left = published_contract_id(producer)
    right = published_contract_id(consumer)
    return bool(left and right and left == right)


def validate_transformation(transform: type[Transformation]) -> ValidationReport:
    """Validate a transformation class definition in isolation."""
    diagnostics: list[Diagnostic] = []
    for problem in transform.validate_definition():
        diagnostics.append(
            Diagnostic(
                code="PMTRN001",
                severity=Severity.ERROR,
                message=problem,
                path=("transformation", transform.__name__),
            )
        )
    for port in list(transform.inputs()) + list(transform.outputs()):
        if port.contract_type is not None and not is_data_contract_type(
            port.contract_type
        ):
            diagnostics.append(
                Diagnostic(
                    code="PMDATA101",
                    severity=Severity.ERROR,
                    message=(
                        f'Port "{port.name}" does not reference a ContractModel type.'
                    ),
                    path=("transformation", transform.__name__, port.name),
                )
            )
    return ValidationReport.from_diagnostics(diagnostics)
