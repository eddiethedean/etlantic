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
