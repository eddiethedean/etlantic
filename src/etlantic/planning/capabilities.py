"""Planning capability checks via EngineRegistry."""

from __future__ import annotations

from typing import Any

from etlantic.capabilities import CapabilityDecision, PluginCapabilities
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.engines import get_engine_registry
from etlantic.exceptions import PipelineValidationError
from etlantic.registry import ImplementationDescriptor, PlanningContext


def is_dataframe_engine(
    engine: str,
    engines: dict[str, PluginCapabilities] | None = None,
) -> bool:
    return get_engine_registry().is_dataframe_engine(engine, engines)


def assert_dataframe_engines_available(
    context: PlanningContext,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
) -> None:
    engines = {default_engine} | {impl.engine for impl in implementations.values()}
    missing = sorted(
        engine
        for engine in engines
        if is_dataframe_engine(engine, context.registry.engines)
        and engine not in context.registry.engines
    )
    if not missing:
        return
    diagnostics = [
        Diagnostic(
            code="PMPLAN410",
            severity=Severity.ERROR,
            message=(
                f"Dataframe engine {engine!r} is not registered. Install "
                f"etlantic-{engine} and ensure it is discoverable."
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


def assert_sql_engines_available(
    context: PlanningContext,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
) -> None:
    registry = get_engine_registry()
    engines = {default_engine} | {impl.engine for impl in implementations.values()}
    missing = sorted(
        engine
        for engine in engines
        if registry.is_sql_engine(engine) and engine not in context.registry.engines
    )
    if not missing:
        return
    diagnostics = [
        Diagnostic(
            code="PMPLAN412",
            severity=Severity.ERROR,
            message=(
                f"SQL engine {engine!r} is not registered. Install "
                "etlantic-sql and ensure it is discoverable."
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


def assert_sql_write_capabilities(
    context: PlanningContext,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
) -> None:
    registry = get_engine_registry()
    engines = {default_engine} | {impl.engine for impl in implementations.values()}
    if not any(registry.is_sql_engine(e) for e in engines):
        return
    required = list(context.profile.required_sql_capabilities)
    if not required:
        return
    for engine in engines:
        if not registry.is_sql_engine(engine):
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


def assert_spark_engines_available(
    context: PlanningContext,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
) -> None:
    registry = get_engine_registry()
    engines = {default_engine} | {impl.engine for impl in implementations.values()}
    missing = sorted(
        engine
        for engine in engines
        if registry.is_spark_engine(engine) and engine not in context.registry.engines
    )
    if not missing:
        return
    diagnostics = [
        Diagnostic(
            code="PMPLAN414",
            severity=Severity.ERROR,
            message=(
                f"Spark engine {engine!r} is not registered. Install "
                "etlantic-pyspark and ensure it is discoverable."
            ),
            path=("capability", engine),
            phase="capability",
        )
        for engine in missing
    ]
    raise PipelineValidationError(
        "Missing Spark engine plugin(s).",
        report=ValidationReport.from_diagnostics(diagnostics, phases=("capability",)),
    )


def assert_spark_capabilities(
    context: PlanningContext,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
) -> None:
    registry = get_engine_registry()
    engines = {default_engine} | {impl.engine for impl in implementations.values()}
    if not any(registry.is_spark_engine(e) for e in engines):
        return
    required = list(context.profile.required_spark_capabilities)
    if context.profile.spark_streaming:
        required = [*required, "spark_streaming", "streaming"]
    if not required:
        return
    for engine in engines:
        if not registry.is_spark_engine(engine):
            continue
        available = context.registry.engines.get(engine)
        if available is None:
            continue
        unsupported = [req for req in required if not available.supports(req)]
        if not unsupported:
            continue
        diagnostics = [
            Diagnostic(
                code="PMPLAN415",
                severity=Severity.ERROR,
                message=(
                    f"Spark capability {req!r} unsupported by {engine!r}; "
                    "failing before execution."
                ),
                path=("capability", req),
                phase="capability",
            )
            for req in unsupported
        ]
        raise PipelineValidationError(
            "Unsupported Spark capabilities.",
            report=ValidationReport.from_diagnostics(
                diagnostics, phases=("capability",)
            ),
        )


def assert_capabilities_supported(
    capability_decisions: list[dict[str, Any]],
    context: PlanningContext,
    engine: str,
) -> None:
    unsupported = [
        item
        for item in capability_decisions
        if item.get("decision") == CapabilityDecision.UNSUPPORTED.value
    ]
    available = context.registry.engines.get(engine)
    if (
        available is not None
        and "lazy" in context.required_capabilities
        and not available.supports("lazy")
    ):
        unsupported.append(
            {
                "requirement": "lazy",
                "engine": engine,
                "decision": CapabilityDecision.UNSUPPORTED.value,
                "message": "Engine does not support lazy execution.",
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


def assert_quality_rule_capabilities(
    *,
    required_capabilities: frozenset[str] | set[str] | list[str],
    available: PluginCapabilities | None,
    engine: str,
    node_name: str | None = None,
) -> None:
    """Fail closed when required portable quality rules are unsupported.

    Emits ``PMPLAN420`` for missing ``invalid_row_separation`` and
    ``PMPLAN421`` for unsupported ``quality.*`` rule capabilities.
    """
    if available is None:
        diagnostics = [
            Diagnostic(
                code="PMPLAN420",
                severity=Severity.ERROR,
                message=(
                    f"Cannot negotiate quality rules for engine {engine!r}: "
                    "engine capabilities are not registered."
                ),
                path=("capability", "quality", engine),
                phase="capability",
            )
        ]
        raise PipelineValidationError(
            "Missing engine capabilities for quality rules.",
            report=ValidationReport.from_diagnostics(
                diagnostics, phases=("capability",)
            ),
        )

    missing: list[tuple[str, str]] = []
    for req in sorted(required_capabilities):
        if available.supports(req):
            continue
        code = "PMPLAN420" if req == "invalid_row_separation" else "PMPLAN421"
        missing.append((code, req))
    if not missing:
        return
    path_prefix: tuple[str, ...] = ("capability", "quality")
    if node_name:
        path_prefix = ("nodes", node_name, "quality")
    diagnostics = [
        Diagnostic(
            code=code,
            severity=Severity.ERROR,
            message=(
                f"Required quality capability {req!r} unsupported by "
                f"{engine!r}; failing before data access."
            ),
            path=(*path_prefix, req),
            phase="capability",
        )
        for code, req in missing
    ]
    raise PipelineValidationError(
        "Unsupported quality rule capabilities.",
        report=ValidationReport.from_diagnostics(diagnostics, phases=("capability",)),
    )


def assert_write_mode_capabilities(
    *,
    mode: str,
    available: PluginCapabilities | None,
    engine: str,
    node_name: str | None = None,
    partition_replace: bool = False,
) -> None:
    """Fail closed when a declared write mode is unsupported by the engine.

    Emits ``PMPLAN430`` when engine capabilities are missing and ``PMPLAN431``
    when a required ``write.*`` extra is absent.
    """
    from etlantic.reliability import WriteMode, write_capability_for_mode

    try:
        write_mode = WriteMode(mode)
    except ValueError:
        diagnostics = [
            Diagnostic(
                code="PMPLAN431",
                severity=Severity.ERROR,
                message=f"Unknown write mode {mode!r} for engine {engine!r}.",
                path=("nodes", node_name or engine, "write_mode"),
                phase="capability",
            )
        ]
        raise PipelineValidationError(
            "Unknown write mode.",
            report=ValidationReport.from_diagnostics(
                diagnostics, phases=("capability",)
            ),
        ) from None

    if write_mode is WriteMode.NO_WRITE:
        return

    if available is None:
        diagnostics = [
            Diagnostic(
                code="PMPLAN430",
                severity=Severity.ERROR,
                message=(
                    f"Cannot negotiate write mode {write_mode.value!r} for "
                    f"engine {engine!r}: engine capabilities are not registered."
                ),
                path=("capability", "write", engine),
                phase="capability",
            )
        ]
        raise PipelineValidationError(
            "Missing engine capabilities for write mode.",
            report=ValidationReport.from_diagnostics(
                diagnostics, phases=("capability",)
            ),
        )

    # Engines that do not advertise any write.* extras are treated as supporting
    # append/overwrite only (local/memory default). Explicit merge/skip/partition
    # require extras or sql_merge/spark_merge legacy flags.
    required = write_capability_for_mode(
        write_mode, partition_replace=partition_replace
    )
    if available.supports(required):
        return
    if write_mode in {WriteMode.APPEND, WriteMode.OVERWRITE}:
        # Default portable modes remain available without explicit extras.
        return
    if write_mode in {WriteMode.MERGE, WriteMode.UPSERT} and (
        available.supports("sql_merge") or available.supports("spark_merge")
    ):
        return
    path: tuple[str, ...] = ("capability", "write", required)
    if node_name:
        path = ("nodes", node_name, "write", required)
    diagnostics = [
        Diagnostic(
            code="PMPLAN431",
            severity=Severity.ERROR,
            message=(
                f"Required write capability {required!r} unsupported by "
                f"{engine!r}; failing before target mutation."
            ),
            path=path,
            phase="capability",
        )
    ]
    raise PipelineValidationError(
        "Unsupported write mode capabilities.",
        report=ValidationReport.from_diagnostics(diagnostics, phases=("capability",)),
    )


def assert_storage_delta_capabilities(
    *,
    operations: list[str] | tuple[str, ...],
    available: PluginCapabilities | None,
    engine: str,
    node_name: str | None = None,
) -> None:
    """Fail closed when required Delta storage ops lack advertised capabilities.

    Emits ``PMPLAN440`` when engine capabilities are missing and ``PMPLAN441``
    when a required ``storage.delta.*`` extra (or legacy ``spark_delta`` for
    merge-only fallback) is absent. Maintenance ops are never treated as
    generic writes.
    """
    from etlantic.storage.delta_capabilities import (
        DELTA_OP_CAPABILITY,
        storage_capability_for_delta_op,
    )

    ops = [str(op).strip().lower() for op in operations if str(op).strip()]
    if not ops:
        return

    if available is None:
        diagnostics = [
            Diagnostic(
                code="PMPLAN440",
                severity=Severity.ERROR,
                message=(
                    f"Cannot negotiate Delta storage operations for engine "
                    f"{engine!r}: engine capabilities are not registered."
                ),
                path=("capability", "storage", engine),
                phase="capability",
            )
        ]
        raise PipelineValidationError(
            "Missing engine capabilities for Delta storage.",
            report=ValidationReport.from_diagnostics(
                diagnostics, phases=("capability",)
            ),
        )

    missing: list[tuple[str, str]] = []
    for op in ops:
        if op not in DELTA_OP_CAPABILITY:
            missing.append((op, f"unknown:{op}"))
            continue
        required = storage_capability_for_delta_op(op)
        if available.supports(required):
            continue
        # Legacy: merge alone may be covered by spark_delta / spark_merge /
        # write.merge until plugins advertise fine-grained extras.
        if op == "merge" and (
            available.supports("spark_delta")
            or available.supports("spark_merge")
            or available.supports("write.merge")
        ):
            continue
        missing.append((op, required))

    if not missing:
        return

    diagnostics = []
    for op, required in missing:
        path: tuple[str, ...] = ("capability", "storage", required)
        if node_name:
            path = ("nodes", node_name, "storage", required)
        if required.startswith("unknown:"):
            diagnostics.append(
                Diagnostic(
                    code="PMPLAN441",
                    severity=Severity.ERROR,
                    message=(
                        f"Unknown Delta storage operation {op!r} for engine "
                        f"{engine!r}; failing before storage mutation."
                    ),
                    path=path,
                    phase="capability",
                )
            )
        else:
            diagnostics.append(
                Diagnostic(
                    code="PMPLAN441",
                    severity=Severity.ERROR,
                    message=(
                        f"Required storage capability {required!r} unsupported "
                        f"by {engine!r}; failing before Delta operation "
                        f"{op!r}."
                    ),
                    path=path,
                    phase="capability",
                )
            )
    raise PipelineValidationError(
        "Unsupported Delta storage capabilities.",
        report=ValidationReport.from_diagnostics(diagnostics, phases=("capability",)),
    )


def collect_required_delta_operations(
    *,
    profile: Any,
    graph: Any | None = None,
    definition: Any | None = None,
) -> list[str]:
    """Collect declared Delta ops from profile / graph / definition metadata."""
    ops: list[str] = []
    required_caps = list(getattr(profile, "required_spark_capabilities", ()) or ())
    for cap in required_caps:
        text = str(cap).strip().lower()
        if text.startswith("storage.delta."):
            ops.append(text.removeprefix("storage.delta."))
        elif text in {"spark_merge", "write.merge", "write.upsert"}:
            ops.append("merge")

    for source in (
        getattr(profile, "metadata", None),
        getattr(definition, "metadata", None) if definition is not None else None,
        getattr(graph, "metadata", None) if graph is not None else None,
    ):
        if not isinstance(source, dict):
            continue
        for key in ("required_delta_operations", "delta_operations", "delta_ops"):
            raw = source.get(key)
            if raw:
                ops.extend(str(x).strip().lower() for x in list(raw) if str(x).strip())

    if graph is not None:
        nodes = getattr(graph, "nodes", None)
        if isinstance(nodes, dict):
            node_iter = nodes.values()
        elif isinstance(nodes, (list, tuple)):
            node_iter = nodes
        else:
            node_iter = ()
        for node in node_iter:
            meta = getattr(node, "metadata", None) or {}
            if not isinstance(meta, dict):
                continue
            for key in ("required_delta_operations", "delta_operations", "delta_ops"):
                raw = meta.get(key)
                if raw:
                    ops.extend(
                        str(x).strip().lower() for x in list(raw) if str(x).strip()
                    )
            write_mode = str(meta.get("write_mode") or meta.get("mode") or "").lower()
            if write_mode in {"merge", "upsert"}:
                ops.append("merge")

    # Preserve order, drop empties/duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for op in ops:
        if not op or op in seen:
            continue
        seen.add(op)
        ordered.append(op)
    return ordered


def assert_profile_storage_delta_capabilities(
    context: PlanningContext,
    implementations: dict[str, ImplementationDescriptor],
    default_engine: str,
    *,
    graph: Any | None = None,
    definition: Any | None = None,
) -> None:
    """Negotiate declared Delta storage ops against Spark engine capabilities."""
    ops = collect_required_delta_operations(
        profile=context.profile,
        graph=graph,
        definition=definition,
    )
    if not ops:
        return
    registry = get_engine_registry()
    engines = {default_engine} | {impl.engine for impl in implementations.values()}
    spark_engines = [e for e in engines if registry.is_spark_engine(e)]
    if not spark_engines:
        # Delta ops require a Spark engine; fail closed when none is selected.
        assert_storage_delta_capabilities(
            operations=ops,
            available=None,
            engine=default_engine,
        )
        return
    for engine in spark_engines:
        assert_storage_delta_capabilities(
            operations=ops,
            available=context.registry.engines.get(engine),
            engine=engine,
        )
