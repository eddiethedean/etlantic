"""Pure planner: validated logical model + profile → PipelinePlan."""

from __future__ import annotations

from typing import Any

from pipelantic.capabilities import CapabilityDecision, negotiate_capabilities
from pipelantic.diagnostics import Diagnostic, Severity, ValidationReport
from pipelantic.exceptions import PipelineValidationError
from pipelantic.identity import implementation_id, published_contract_version
from pipelantic.model import LogicalGraph, NodeKind
from pipelantic.plan.artifacts import (
    ArtifactRef,
    ArtifactStrategy,
    artifact_identity,
    cache_identity,
)
from pipelantic.plan.model import (
    PLAN_SCHEMA,
    OutputResolution,
    PhysicalUnit,
    PipelinePlan,
)
from pipelantic.plan.regions import ExecutionRegion, MaterializationBoundary
from pipelantic.plan.serialize import plan_fingerprint
from pipelantic.plan.slicing import (
    dependency_closure,
    run_one_selection,
    run_until_selection,
    slice_graph,
)
from pipelantic.registry import (
    BindingDescriptor,
    ImplementationDescriptor,
    PlanningContext,
)
from pipelantic.transformation import Step


def plan_pipeline(
    pipeline_cls: type[Any],
    *,
    context: PlanningContext | None = None,
    profile: str | Any | None = None,
    selection: dict[str, Any] | None = None,
) -> PipelinePlan:
    """Plan a pipeline. Raises PipelineValidationError when invalid."""
    from pipelantic.validation import validate_pipeline

    ctx = context or PlanningContext.create(profile=profile)
    report = validate_pipeline(pipeline_cls, context=ctx)
    if report.has_errors:
        raise PipelineValidationError(
            f"Cannot plan invalid pipeline {pipeline_cls.__name__}.",
            report=report,
        )
    return _build_plan(pipeline_cls, ctx, selection=selection or ctx.selection)


def plan_pipeline_with_report(
    pipeline_cls: type[Any],
    *,
    context: PlanningContext | None = None,
    profile: str | Any | None = None,
    selection: dict[str, Any] | None = None,
) -> tuple[PipelinePlan | None, ValidationReport]:
    """Plan a pipeline, returning (plan, report). Plan is None when invalid."""
    from pipelantic.validation import validate_pipeline

    ctx = context or PlanningContext.create(profile=profile)
    report = validate_pipeline(pipeline_cls, context=ctx)
    if report.has_errors:
        return None, report
    try:
        return _build_plan(
            pipeline_cls, ctx, selection=selection or ctx.selection
        ), report
    except PipelineValidationError as exc:
        return None, exc.report if exc.report is not None else report


def _selection_error(message: str) -> PipelineValidationError:
    report = ValidationReport.from_diagnostics(
        [
            Diagnostic(
                code="PMPLAN501",
                severity=Severity.ERROR,
                message=message,
                path=("selection",),
                phase="structural",
            )
        ],
        phases=("structural",),
    )
    return PipelineValidationError(message, report=report)


def _build_plan(
    pipeline_cls: type[Any],
    context: PlanningContext,
    *,
    selection: dict[str, Any] | None = None,
) -> PipelinePlan:
    # 1. Freeze logical model
    graph = pipeline_cls.build_graph()
    selected: tuple[str, ...] | None = None
    sel = selection or {}
    try:
        if "run_one" in sel:
            selected = run_one_selection(graph, str(sel["run_one"]))
            graph = slice_graph(graph, selected)
        elif "run_until" in sel:
            selected = run_until_selection(graph, str(sel["run_until"]))
            graph = slice_graph(graph, selected)
        elif "nodes" in sel:
            selected = dependency_closure(graph, list(sel["nodes"]))
            graph = slice_graph(graph, selected)
    except ValueError as exc:
        raise _selection_error(str(exc)) from exc

    if selected is not None and not selected:
        raise _selection_error("Selection produced an empty graph.")
    if selected is not None and not graph.nodes:
        raise _selection_error("Selection produced an empty graph.")

    profile = context.profile
    # Prefer SQL when profile.sql_engine is set; otherwise dataframe/local.
    default_engine = (
        profile.sql_engine
        if profile.sql_engine
        else (profile.dataframe_engine or "local")
    )
    security_domain = profile.security_domain

    # 4-5. Implementations + capabilities
    implementations = _select_implementations(
        pipeline_cls, graph, context, default_engine
    )
    _assert_dataframe_engines_available(context, implementations, default_engine)
    _assert_sql_engines_available(context, implementations, default_engine)
    _assert_sql_write_capabilities(context, implementations, default_engine)
    capability_decisions = _capability_records(context, default_engine)
    _assert_capabilities_supported(capability_decisions, context, default_engine)

    # 6. Regions by resolved engine (never merge across engines/security domains)
    regions = _form_regions(graph, implementations, default_engine, security_domain)

    # 7. Physical units + mappings
    physical_units: list[PhysicalUnit] = []
    logical_to_physical: dict[str, str] = {}
    for region in regions:
        caps = context.registry.engines.get(region.engine)
        unit_id = f"unit:{region.identity}"
        physical_units.append(
            PhysicalUnit(
                identity=unit_id,
                region_id=region.identity,
                logical_nodes=region.node_names,
                engine=region.engine,
                metadata={
                    "plugin_version": next(
                        (
                            p.version
                            for p in context.registry.plugins.values()
                            if p.engine == region.engine
                        ),
                        None,
                    ),
                    "capabilities": caps.to_dict() if caps is not None else None,
                    "ownership": "copied" if region.engine == "pandas" else "shared",
                },
            )
        )
        for name in region.node_names:
            logical_to_physical[name] = unit_id

    # 7b. Materialization + collection boundaries
    boundaries = _materialization_boundaries(
        graph, implementations, default_engine, security_domain
    )
    boundaries.extend(
        _collection_boundaries(
            graph,
            implementations,
            default_engine,
            security_domain,
            regions,
            context.registry.engines,
        )
    )

    # 8. Output resolutions
    provisional_fp = "provisional"
    outputs = _resolve_outputs(
        graph,
        regions,
        boundaries,
        implementations,
        default_engine,
        security_domain,
        provisional_fp,
    )

    # 9. Bindings / resource refs (secret-free; only referenced secrets)
    bindings = _resolve_bindings(graph, context)
    resource_refs: dict[str, dict[str, Any]] = {
        name: {"binding": desc.binding, "provider": desc.provider}
        for name, desc in bindings.items()
    }
    referenced_secret_keys: set[str] = set(profile.resources) | set(
        profile.secret_providers
    )
    for desc in bindings.values():
        if desc.binding in profile.secrets:
            referenced_secret_keys.add(desc.binding)
        if desc.secret_ref is not None:
            resource_refs[f"secret:{desc.binding}"] = desc.secret_ref.to_dict()
    for key in referenced_secret_keys:
        secret = profile.secrets.get(key)
        if secret is not None:
            resource_refs[f"secret:{key}"] = secret.to_dict()

    contract_versions: dict[str, str] = {}
    for node in graph.nodes:
        if node.contract_type is not None:
            version = published_contract_version(node.contract_type)
            if version and node.contract_id:
                contract_versions[node.contract_id] = version
        for port in (*node.inputs, *node.outputs):
            if port.contract_type is not None and port.contract_id:
                version = published_contract_version(port.contract_type)
                if version:
                    contract_versions[port.contract_id] = version

    plugin_versions = {
        name: plugin.version for name, plugin in context.registry.plugins.items()
    }

    profile_snapshot = profile.to_dict()
    execution_settings = {
        "orchestrator": profile.orchestrator,
        "concurrency": profile.concurrency,
        "timeout_seconds": profile.timeout_seconds,
        "retry_max_attempts": profile.retry_max_attempts,
        "dataframe_engine": profile.dataframe_engine,
        "sql_engine": profile.sql_engine,
        "allow_trusted_sql": profile.allow_trusted_sql,
    }
    intents: dict[str, Any] = {}
    if profile.retry_max_attempts is not None:
        intents["retry"] = {"max_attempts": profile.retry_max_attempts}
    if profile.timeout_seconds is not None:
        intents["timeout"] = {"seconds": profile.timeout_seconds}

    plan = PipelinePlan(
        schema=PLAN_SCHEMA,
        plan_id="",
        pipeline_id=graph.pipeline_id,
        pipeline_name=graph.pipeline_name,
        profile_name=profile.name,
        fingerprint="",
        logical_graph=graph,
        regions=tuple(regions),
        physical_units=tuple(physical_units),
        logical_to_physical=logical_to_physical,
        implementations=implementations,
        bindings=bindings,
        resource_refs=resource_refs,
        materialization_boundaries=tuple(boundaries),
        output_resolutions=tuple(outputs),
        capability_decisions=tuple(capability_decisions),
        selected_nodes=selected,
        security_domain=security_domain,
        contract_versions=contract_versions,
        plugin_versions=plugin_versions,
        intents=intents,
        profile_snapshot=profile_snapshot,
        execution_settings=execution_settings,
        metadata={
            "planner": "pipelantic.plan.planner",
            "planner_version": "0.6.0",
            "dataframe_protocol": "pipelantic.dataframe/1",
            "sql_protocol": "pipelantic.sql/1",
            "sql_fusion": [
                {
                    "region": r.identity,
                    "engine": r.engine,
                    "nodes": list(r.node_names),
                    "strategy": "temp_relation" if r.engine == "sql" else None,
                }
                for r in regions
                if r.engine == "sql"
            ],
            "collection_points": [
                {
                    "identity": b.identity,
                    "producer_node": b.producer_node,
                    "producer_port": b.producer_port,
                    "reason": b.reason,
                }
                for b in boundaries
                if b.reason
                in {
                    "collection_point",
                    "sink_publication",
                    "cross_engine",
                    "validation_boundary",
                }
            ],
            "conversion_boundaries": [
                {
                    "identity": b.identity,
                    "producer_node": b.producer_node,
                    "producer_port": b.producer_port,
                    "reason": b.reason,
                }
                for b in boundaries
                if b.reason == "cross_engine"
            ],
            "validation_policy": {
                "input_outcome": "fail",
                "output_outcome": "fail",
            },
        },
    )
    fingerprint = plan_fingerprint(plan)
    outputs = _resolve_outputs(
        graph,
        regions,
        boundaries,
        implementations,
        default_engine,
        security_domain,
        fingerprint,
    )
    return PipelinePlan(
        schema=plan.schema,
        plan_id=f"plan:{fingerprint[:16]}",
        pipeline_id=plan.pipeline_id,
        pipeline_name=plan.pipeline_name,
        profile_name=plan.profile_name,
        fingerprint=fingerprint,
        logical_graph=plan.logical_graph,
        regions=plan.regions,
        physical_units=plan.physical_units,
        logical_to_physical=plan.logical_to_physical,
        implementations=plan.implementations,
        bindings=plan.bindings,
        resource_refs=plan.resource_refs,
        materialization_boundaries=plan.materialization_boundaries,
        output_resolutions=tuple(outputs),
        capability_decisions=plan.capability_decisions,
        selected_nodes=plan.selected_nodes,
        security_domain=plan.security_domain,
        contract_versions=plan.contract_versions,
        plugin_versions=plan.plugin_versions,
        intents=plan.intents,
        profile_snapshot=plan.profile_snapshot,
        execution_settings=plan.execution_settings,
        metadata=plan.metadata,
    )


def _select_implementations(
    pipeline_cls: type[Any],
    graph: LogicalGraph,
    context: PlanningContext,
    default_engine: str,
) -> dict[str, ImplementationDescriptor]:
    selected: dict[str, ImplementationDescriptor] = {}
    members = pipeline_cls.__pipeline_members__
    for node in graph.nodes:
        if node.kind is not NodeKind.STEP:
            continue
        engine = context.profile.implementation_overrides.get(node.name, default_engine)
        member = members.get(node.name)
        transform = member.transformation if isinstance(member, Step) else None
        transform_id = node.transformation_id or "unknown"
        is_async = False
        identity = implementation_id(transform_id, engine)
        explicit_override = node.name in context.profile.implementation_overrides

        # Registry fallback: transform_id::engine
        registry_key = f"{transform_id}::{engine}"
        if registry_key in context.registry.implementations:
            selected[node.name] = context.registry.implementations[registry_key]
            continue

        if transform is not None:
            impls = transform.implementations()
            if engine in impls:
                record = impls[engine]
                identity = record.identity
                is_async = record.is_async
            elif len(impls) == 1 and not explicit_override:
                record = next(iter(impls.values()))
                identity = record.identity
                is_async = record.is_async
                engine = record.engine
            elif len(impls) > 1 and engine not in impls:
                raise PipelineValidationError(
                    f'Step "{node.name}" has ambiguous implementations '
                    f"{sorted(impls)}; select one via profile override.",
                    report=ValidationReport.from_diagnostics(
                        [
                            Diagnostic(
                                code="PMPLAN302",
                                severity=Severity.ERROR,
                                message=(
                                    f'Step "{node.name}" has ambiguous '
                                    f"implementations {sorted(impls)}; "
                                    f"select one via profile override."
                                ),
                                path=("pipeline", node.name),
                                phase="policy",
                            )
                        ],
                        phases=("policy",),
                    ),
                )
        selected[node.name] = ImplementationDescriptor(
            transformation_id=transform_id,
            engine=engine,
            identity=identity,
            is_async=is_async,
        )
    return selected


def _capability_records(context: PlanningContext, engine: str) -> list[dict[str, Any]]:
    available = context.registry.engines.get(engine)
    if available is None:
        return []
    fallback = (
        context.registry.engines.get(context.fallback_engine)
        if context.fallback_engine
        else None
    )
    return [
        item.to_dict()
        for item in negotiate_capabilities(
            requirements=context.required_capabilities,
            available=available,
            fallback=fallback,
            allow_fallback=context.allow_capability_fallback,
        )
    ]


def _assert_dataframe_engines_available(
    context: PlanningContext,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
) -> None:
    from pipelantic.dataframe.protocol import DATAFRAME_ENGINES

    engines = {default_engine} | {impl.engine for impl in implementations.values()}
    missing = sorted(
        engine
        for engine in engines
        if engine in DATAFRAME_ENGINES and engine not in context.registry.engines
    )
    if not missing:
        return
    diagnostics = [
        Diagnostic(
            code="PMPLAN410",
            severity=Severity.ERROR,
            message=(
                f"Dataframe engine {engine!r} is not registered. Install "
                f"pipelantic-{engine} and ensure it is discoverable."
            ),
            path=("capability", engine),
            phase="capability",
        )
        for engine in missing
    ]
    raise PipelineValidationError(
        "Missing dataframe engine plugin(s).",
        report=ValidationReport.from_diagnostics(diagnostics, phases=("capability",)),
    )


def _assert_sql_engines_available(
    context: PlanningContext,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
) -> None:
    from pipelantic.sql.protocol import SQL_ENGINES

    engines = {default_engine} | {impl.engine for impl in implementations.values()}
    missing = sorted(
        engine
        for engine in engines
        if engine in SQL_ENGINES and engine not in context.registry.engines
    )
    if not missing:
        return
    diagnostics = [
        Diagnostic(
            code="PMPLAN412",
            severity=Severity.ERROR,
            message=(
                f"SQL engine {engine!r} is not registered. Install "
                "pipelantic-sql and ensure it is discoverable."
            ),
            path=("capability", engine),
            phase="capability",
        )
        for engine in missing
    ]
    raise PipelineValidationError(
        "Missing SQL engine plugin(s).",
        report=ValidationReport.from_diagnostics(diagnostics, phases=("capability",)),
    )


def _assert_sql_write_capabilities(
    context: PlanningContext,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
) -> None:
    """Fail closed when profile requires unsupported SQL write semantics."""
    from pipelantic.sql.protocol import SQL_ENGINES

    engines = {default_engine} | {impl.engine for impl in implementations.values()}
    if not any(e in SQL_ENGINES for e in engines):
        return
    required = list(context.profile.required_sql_capabilities)
    if not required:
        return
    for engine in engines:
        if engine not in SQL_ENGINES:
            continue
        available = context.registry.engines.get(engine)
        if available is None:
            continue
        unsupported = [req for req in required if not available.supports(req)]
        if not unsupported:
            continue
        diagnostics = [
            Diagnostic(
                code="PMPLAN413",
                severity=Severity.ERROR,
                message=(
                    f"SQL capability {req!r} unsupported by {engine!r}; "
                    "failing before target mutation."
                ),
                path=("capability", req),
                phase="capability",
            )
            for req in unsupported
        ]
        raise PipelineValidationError(
            "Unsupported SQL write/publication capabilities.",
            report=ValidationReport.from_diagnostics(
                diagnostics, phases=("capability",)
            ),
        )


def _assert_capabilities_supported(
    capability_decisions: list[dict[str, Any]],
    context: PlanningContext,
    engine: str,
) -> None:
    unsupported = [
        item
        for item in capability_decisions
        if item.get("decision") == CapabilityDecision.UNSUPPORTED.value
    ]
    # Pandas must fail planning when lazy is required.
    available = context.registry.engines.get(engine)
    if (
        available is not None
        and engine == "pandas"
        and "lazy" in context.required_capabilities
        and not available.supports("lazy")
    ):
        unsupported.append(
            {
                "requirement": "lazy",
                "engine": engine,
                "decision": CapabilityDecision.UNSUPPORTED.value,
                "message": "Pandas plugin does not support lazy execution.",
            }
        )
    if not unsupported:
        return
    diagnostics = [
        Diagnostic(
            code="PMPLAN411",
            severity=Severity.ERROR,
            message=str(
                item.get("message")
                or f"Unsupported capability {item.get('requirement')!r} "
                f"for engine {engine!r}."
            ),
            path=("capability", str(item.get("requirement"))),
            phase="capability",
        )
        for item in unsupported
    ]
    raise PipelineValidationError(
        "Unsupported dataframe capabilities.",
        report=ValidationReport.from_diagnostics(diagnostics, phases=("capability",)),
    )


def _collection_boundaries(
    graph: LogicalGraph,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
    security_domain: str,
    regions: list[ExecutionRegion],
    engines: dict[str, Any] | None = None,
) -> list[MaterializationBoundary]:
    """Declare explicit collection points for lazy dataframe engines."""
    from pipelantic.dataframe.protocol import DATAFRAME_ENGINES

    engines = engines or {}
    region_engine = {r.identity: r.engine for r in regions}
    node_region = {
        name: region.identity for region in regions for name in region.node_names
    }
    boundaries: list[MaterializationBoundary] = []
    for node in graph.nodes:
        if node.kind is not NodeKind.STEP:
            continue
        engine = _node_engine(node.name, implementations, default_engine)
        if engine not in DATAFRAME_ENGINES:
            continue
        caps = engines.get(engine)
        # Collection required before sink / cross-engine / durable boundaries.
        for edge in graph.edges_from(node.name):
            cons = next((n for n in graph.nodes if n.name == edge.consumer_node), None)
            reason = None
            if (cons is not None and cons.kind is NodeKind.SINK) or _node_engine(
                edge.consumer_node, implementations, default_engine
            ) != engine:
                reason = "collection_point"
            if reason is None:
                continue
            boundaries.append(
                MaterializationBoundary(
                    identity=(f"boundary:collect:{node.name}.{edge.producer_port}"),
                    producer_node=node.name,
                    producer_port=edge.producer_port,
                    reason=reason,
                    security_domain=security_domain,
                    metadata={
                        "engine": engine,
                        "lazy_supported": bool(
                            caps.supports("lazy") if caps is not None else False
                        ),
                        "region": node_region.get(node.name),
                        "region_engine": region_engine.get(
                            node_region.get(node.name, ""), engine
                        ),
                    },
                )
            )
    seen: set[str] = set()
    unique: list[MaterializationBoundary] = []
    for boundary in boundaries:
        if boundary.identity in seen:
            continue
        seen.add(boundary.identity)
        unique.append(boundary)
    return unique


def _node_engine(
    node_name: str,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
) -> str:
    impl = implementations.get(node_name)
    return impl.engine if impl is not None else default_engine


def _form_regions(
    graph: LogicalGraph,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
    security_domain: str,
) -> list[ExecutionRegion]:
    """Form one region per (security_domain, engine); never merge across engines."""
    by_engine: dict[str, list[str]] = {}
    for node in graph.nodes:
        engine = _node_engine(node.name, implementations, default_engine)
        # Sources/sinks follow the engine of their adjacent step when possible
        if node.kind is NodeKind.SOURCE:
            consumers = [e.consumer_node for e in graph.edges_from(node.name)]
            if consumers:
                engine = _node_engine(consumers[0], implementations, default_engine)
        elif node.kind is NodeKind.SINK:
            producers = [e.producer_node for e in graph.edges_to(node.name)]
            if producers:
                engine = _node_engine(producers[0], implementations, default_engine)
        by_engine.setdefault(engine, []).append(node.name)

    regions: list[ExecutionRegion] = []
    for engine, names in sorted(by_engine.items()):
        regions.append(
            ExecutionRegion(
                identity=f"region:{security_domain}:{engine}",
                engine=engine,
                node_names=tuple(names),
                security_domain=security_domain,
            )
        )
    return regions


def _materialization_boundaries(
    graph: LogicalGraph,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
    security_domain: str,
) -> list[MaterializationBoundary]:
    boundaries: list[MaterializationBoundary] = []
    fanout: dict[tuple[str, str], int] = {}
    for edge in graph.edges:
        key = (edge.producer_node, edge.producer_port)
        fanout[key] = fanout.get(key, 0) + 1
        prod_engine = _node_engine(edge.producer_node, implementations, default_engine)
        cons_engine = _node_engine(edge.consumer_node, implementations, default_engine)
        if prod_engine != cons_engine:
            boundaries.append(
                MaterializationBoundary(
                    identity=(
                        f"boundary:engine:{edge.producer_node}.{edge.producer_port}"
                    ),
                    producer_node=edge.producer_node,
                    producer_port=edge.producer_port,
                    reason="cross_engine",
                    security_domain=security_domain,
                )
            )
    for (node_name, port_name), count in fanout.items():
        if count > 1:
            boundaries.append(
                MaterializationBoundary(
                    identity=f"boundary:{node_name}.{port_name}",
                    producer_node=node_name,
                    producer_port=port_name,
                    reason="fan_out_reuse",
                    security_domain=security_domain,
                )
            )
    for node in graph.nodes:
        if node.kind is NodeKind.SINK:
            for edge in graph.edges_to(node.name):
                boundaries.append(
                    MaterializationBoundary(
                        identity=f"boundary:sink:{node.name}",
                        producer_node=edge.producer_node,
                        producer_port=edge.producer_port,
                        reason="sink_publication",
                        security_domain=security_domain,
                    )
                )
    seen: set[str] = set()
    unique: list[MaterializationBoundary] = []
    for boundary in boundaries:
        if boundary.identity in seen:
            continue
        seen.add(boundary.identity)
        unique.append(boundary)
    return unique


def _resolve_outputs(
    graph: LogicalGraph,
    regions: list[ExecutionRegion],
    boundaries: list[MaterializationBoundary],
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
    security_domain: str,
    plan_fp: str,
) -> list[OutputResolution]:
    region_of = {
        name: region.identity for region in regions for name in region.node_names
    }
    # Only sink publication forces durable record materialization by default.
    # Fan-out / cross-engine / collection still require collect at runtime but
    # keep native frames in memory (ownership/copy), not durable JSON records.
    durable_reasons = {"sink_publication"}
    durable_ports = {
        (b.producer_node, b.producer_port)
        for b in boundaries
        if b.reason in durable_reasons
    }
    fanout_ports = {
        (b.producer_node, b.producer_port)
        for b in boundaries
        if b.reason == "fan_out_reuse"
    }
    resolutions: list[OutputResolution] = []
    for node in graph.nodes:
        for port in node.outputs:
            key = (node.name, port.name)
            consumers = [
                e.consumer_node
                for e in graph.edges_from(node.name)
                if e.producer_port == port.name
            ]
            if node.kind is NodeKind.SINK or key in durable_ports:
                strategy = ArtifactStrategy.DURABLE
            elif node.kind is NodeKind.SOURCE:
                strategy = ArtifactStrategy.EXTERNAL
            elif not consumers:
                # Unconsumed ports stay in-memory; never default to durable.
                strategy = ArtifactStrategy.IN_MEMORY
            else:
                prod_engine = _node_engine(node.name, implementations, default_engine)
                same_engine = all(
                    _node_engine(c, implementations, default_engine) == prod_engine
                    for c in consumers
                )
                same_region = all(
                    region_of.get(c) == region_of.get(node.name) for c in consumers
                )
                if key in fanout_ports:
                    strategy = ArtifactStrategy.IN_MEMORY
                elif same_engine and same_region:
                    strategy = ArtifactStrategy.LAZY
                elif same_engine:
                    strategy = ArtifactStrategy.IN_MEMORY
                else:
                    # Cross-engine handoff: keep in-memory until conversion.
                    strategy = ArtifactStrategy.IN_MEMORY
            art_id = artifact_identity(
                pipeline_id=graph.pipeline_id,
                node_name=node.name,
                port_name=port.name,
                security_domain=security_domain,
            )
            cache_key = cache_identity(
                pipeline_id=graph.pipeline_id,
                node_name=node.name,
                port_name=port.name,
                security_domain=security_domain,
                plan_fingerprint=plan_fp,
            )
            metadata: dict[str, Any] = {}
            if key in fanout_ports:
                metadata["ownership"] = "copied"
            resolutions.append(
                OutputResolution(
                    node_name=node.name,
                    port_name=port.name,
                    artifact=ArtifactRef(
                        identity=art_id,
                        logical_output=f"{node.name}.{port.name}",
                        strategy=strategy,
                        security_domain=security_domain,
                        cache_key=cache_key,
                        metadata=metadata,
                    ),
                )
            )
    return resolutions


def _resolve_bindings(
    graph: LogicalGraph, context: PlanningContext
) -> dict[str, BindingDescriptor]:
    resolved: dict[str, BindingDescriptor] = {}
    for node in graph.nodes:
        if not node.binding:
            continue
        if node.binding in context.registry.bindings:
            resolved[node.name] = context.registry.bindings[node.binding]
            continue
        provider = context.profile.bindings.get(node.binding, "memory")
        secret = context.profile.secrets.get(node.binding)
        resolved[node.name] = BindingDescriptor(
            binding=node.binding,
            provider=provider,
            kind="source" if node.kind is NodeKind.SOURCE else "sink",
            secret_ref=secret,
        )
    return resolved


__all__ = [
    "plan_pipeline",
    "plan_pipeline_with_report",
]
