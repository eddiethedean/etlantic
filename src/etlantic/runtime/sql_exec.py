"""Execute transformation steps through the SQL protocol."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

from etlantic.exceptions import NodeExecutionError
from etlantic.model import Node
from etlantic.plan.model import PipelinePlan
from etlantic.registry import ImplementationDescriptor
from etlantic.runtime.state import FailureStage
from etlantic.sql.discovery import load_sql_plugin
from etlantic.sql.helpers import require_safe_identifier
from etlantic.sql.protocol import (
    RelationRef,
    SqlExecutionContext,
    SqlExecutionResult,
    SqlPlugin,
    SqlQuery,
    SqlWrite,
    TransactionOutcome,
    TrustedSqlFragment,
    WriteIntentKind,
)
from etlantic.transformation import ImplementationRecord


def is_sql_engine(
    engine: str,
    engines: dict[str, object] | object | None = None,
    *,
    profile: Any | None = None,
) -> bool:
    """Return True when capabilities/registration say sql (builtin name fallback)."""
    from etlantic.engines import get_engine_registry

    if get_engine_registry().is_sql_engine(engine, engines):
        return True
    # Runtime dispatch may not carry a PlanningContext registry.  Consult the
    # authorized discovery surface rather than maintaining a DuckDB-specific
    # alias list; third-party SQL engines therefore route by their advertised
    # capability as well.
    try:
        plugins = (
            engines
            if isinstance(engines, dict)
            else getattr(engines, "sql_plugins", None)
        )
        if isinstance(plugins, dict):
            if engine in plugins:
                return bool(plugins[engine].capabilities().supports("sql"))
            # An explicitly supplied runtime map is authoritative.  Do not
            # silently fall back to an unauthorized global discovery result.
            if engines is not None:
                return False
        from etlantic.sql.discovery import discover_sql_plugins

        plugin = discover_sql_plugins(profile=profile).get(engine)
        return plugin is not None and plugin.capabilities().supports("sql")
    except Exception:
        return False


def resolve_sql_plugin(
    engine: str = "sql",
    *,
    plugins: dict[str, SqlPlugin] | None = None,
    profile: Any | None = None,
) -> SqlPlugin:
    if plugins is not None and engine in plugins:
        return plugins[engine]
    plugin = load_sql_plugin(engine, profile=profile)
    if plugin is not None:
        return plugin
    raise NodeExecutionError(
        f"No SQL plugin available for engine {engine!r}. Install etlantic-sql.",
        node_name="sql",
        stage=FailureStage.TRANSFORM.value,
        code="PMEXEC434",
    )


def _context(
    *,
    plan: PipelinePlan,
    node: Node,
    run_id: str,
    attempt: int,
    allow_trusted_sql: bool,
    engine: str = "sql",
) -> SqlExecutionContext:
    return SqlExecutionContext(
        run_id=run_id,
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        step_name=node.name,
        engine=engine,
        attempt=attempt,
        connection_binding=node.binding,
        allow_trusted_sql=allow_trusted_sql,
        metadata={"security_domain": plan.security_domain},
    )


def _contains_trusted_fragment(value: Any) -> bool:
    if isinstance(value, TrustedSqlFragment):
        return True
    if isinstance(value, SqlQuery):
        if any(isinstance(c, TrustedSqlFragment) for c in value.columns):
            return True
        if isinstance(value.where, TrustedSqlFragment):
            return True
    if isinstance(value, SqlWrite) and isinstance(value.source, SqlQuery):
        return _contains_trusted_fragment(value.source)
    return False


def _assert_trusted_sql_allowed(
    *,
    value: Any,
    plugin: SqlPlugin,
    allow_trusted_sql: bool,
    node_name: str,
) -> None:
    if not _contains_trusted_fragment(value):
        return
    caps = plugin.capabilities()
    if not allow_trusted_sql or not caps.supports("sql_trusted_fragments"):
        raise NodeExecutionError(
            "Trusted SQL fragments are disabled by profile policy "
            "or plugin capability; failing closed.",
            node_name=node_name,
            stage=FailureStage.TRANSFORM.value,
            code="PMEXEC455",
        )


async def execute_sql_source(
    *,
    plugin: SqlPlugin,
    node: Node,
    plan: PipelinePlan,
    run_id: str,
    attempt: int,
    location: str | None,
    binding: str | None,
    engine: str | None = None,
) -> RelationRef:
    """Resolve a SQL source to a RelationRef without fetching rows."""
    return plugin.relation_from_binding(
        binding=binding or node.binding or node.name,
        location=location,
        metadata={"node": node.name, "plan_id": plan.plan_id},
    )


async def execute_sql_step(
    *,
    plugin: SqlPlugin,
    impl: ImplementationRecord,
    node: Node,
    inputs: dict[str, Any],
    params: dict[str, Any],
    plan: PipelinePlan,
    run_id: str,
    attempt: int,
    allow_trusted_sql: bool = False,
    engine: str | None = None,
) -> Any:
    """Invoke a SQL transformation implementation and keep IR in-process.

    Intermediate Python row materialization is forbidden: implementations must
    return ``SqlQuery`` / ``RelationRef`` / ``SqlWrite`` handles.
    """
    _context(
        plan=plan,
        node=node,
        run_id=run_id,
        attempt=attempt,
        allow_trusted_sql=allow_trusted_sql,
        engine=engine or plugin.info.engine,
    )
    kwargs = {**dict(params), **dict(inputs)}
    result = impl.callable(**kwargs)
    if isinstance(result, (SqlQuery, RelationRef, SqlWrite)):
        _assert_trusted_sql_allowed(
            value=result,
            plugin=plugin,
            allow_trusted_sql=allow_trusted_sql,
            node_name=node.name,
        )
        return result
    if isinstance(result, TrustedSqlFragment):
        _assert_trusted_sql_allowed(
            value=result,
            plugin=plugin,
            allow_trusted_sql=allow_trusted_sql,
            node_name=node.name,
        )
    raise NodeExecutionError(
        f"SQL implementation for {node.name!r} must return SqlQuery, "
        f"RelationRef, or SqlWrite; got {type(result)!r}.",
        node_name=node.name,
        stage=FailureStage.TRANSFORM.value,
        code="PMEXEC456",
    )


async def execute_portable_sql_step(
    *,
    plugin: SqlPlugin,
    descriptor: ImplementationDescriptor,
    node: Node,
    inputs: dict[str, Any],
    params: dict[str, Any],
    plan: PipelinePlan,
    run_id: str,
    attempt: int,
) -> Any:
    """Compile and execute a sealed portable transform through the selected SQL engine."""
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
        preflight_portable_support,
    )
    from etlantic.transform.discovery import load_transform_compiler

    definition = descriptor.portable_plan
    if not isinstance(definition, dict):
        raise NodeExecutionError(
            f"portable_compiled step {node.name!r} has no embedded portable plan",
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM302",
        )
    engine = plugin.info.engine
    from etlantic.profile import Profile

    profile_snapshot = plan.profile_snapshot or {}
    profile = (
        Profile.from_plan_snapshot(dict(profile_snapshot))
        if isinstance(profile_snapshot, Mapping)
        else None
    )
    compiler = load_transform_compiler(engine, profile=profile)
    if compiler is None:
        raise NodeExecutionError(
            f"No portable compiler is registered for SQL engine {engine!r}",
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM303",
        )
    info = compiler.info
    if descriptor.compiler_name and info.name != descriptor.compiler_name:
        raise NodeExecutionError(
            f"Planned transform compiler {descriptor.compiler_name!r} is not installed",
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM307",
        )
    if descriptor.compiler_version and info.version != descriptor.compiler_version:
        raise NodeExecutionError(
            f"Planned transform compiler version {descriptor.compiler_version!r} is not installed",
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM307",
        )
    if (
        descriptor.compiler_protocol
        and info.compiler_protocol != descriptor.compiler_protocol
    ):
        raise NodeExecutionError(
            f"Planned transform compiler protocol {descriptor.compiler_protocol!r} is not installed",
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM307",
        )
    if info.engine and info.engine != engine:
        raise NodeExecutionError(
            f"Transform compiler targets {info.engine!r}, not planned engine {engine!r}",
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM307",
        )
    try:
        preflight_portable_support(descriptor, compiler, engine=engine)
    except ValueError as exc:
        raise NodeExecutionError(
            str(exc),
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM306",
        ) from exc
    compiled = compiler.compile(
        definition,
        context=TransformCompileContext(
            pipeline_id=plan.pipeline_id,
            plan_id=plan.plan_id,
            step_name=node.name,
            profile_name=str((plan.profile_snapshot or {}).get("name") or "runtime"),
            engine=engine,
            metadata={"planned_ir_fingerprint": descriptor.ir_fingerprint},
        ),
        requirements=descriptor.requirements,
    )
    if (
        descriptor.ir_fingerprint
        and compiled.ir_fingerprint != descriptor.ir_fingerprint
    ):
        raise NodeExecutionError(
            f"Portable plan fingerprint drift for {node.name!r}; replan required",
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM304",
        )
    bundle = await compiler.execute(
        compiled,
        inputs=inputs,
        parameters=params,
        context=TransformExecutionContext(
            run_id=run_id,
            pipeline_id=plan.pipeline_id,
            plan_id=plan.plan_id,
            step_name=node.name,
            engine=engine,
            attempt=attempt,
            metadata={
                "_sql_plugin": plugin,
                "_duckdb_plugin": plugin,
                "_return_handles": True,
            },
        ),
    )
    if not bundle.valid:
        raise NodeExecutionError(
            f"Portable SQL compiler produced no valid outputs for {node.name!r}",
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMXFORM305",
        )
    return (
        next(iter(bundle.valid.values()))
        if len(bundle.valid) == 1
        else dict(bundle.valid)
    )


async def execute_sql_sink(
    *,
    plugin: SqlPlugin,
    node: Node,
    source_value: Any,
    plan: PipelinePlan,
    run_id: str,
    attempt: int,
    target_location: str | None,
    write_intent: str = "insert_select",
    params: dict[str, Any] | None = None,
    allow_trusted_sql: bool = False,
    engine: str | None = None,
) -> SqlExecutionResult:
    """Publish a SQL query/relation into a sink without fetching intermediates."""
    # LOAD injection is owned by LocalOrchestrator (once per logical sink).
    context = _context(
        plan=plan,
        node=node,
        run_id=run_id,
        attempt=attempt,
        allow_trusted_sql=allow_trusted_sql,
        engine=engine or plugin.info.engine,
    )
    target = plugin.relation_from_binding(
        binding=node.binding or node.name,
        location=target_location,
    )
    try:
        intent = WriteIntentKind(write_intent)
    except ValueError as exc:
        raise NodeExecutionError(
            f"Unknown SQL write_intent {write_intent!r}; failing before mutation.",
            node_name=node.name,
            stage=FailureStage.WRITE.value,
            code="PMEXEC432",
        ) from exc

    if isinstance(source_value, SqlWrite):
        write = source_value
    else:
        write = SqlWrite(intent=intent, target=target, source=source_value)

    _assert_trusted_sql_allowed(
        value=write,
        plugin=plugin,
        allow_trusted_sql=allow_trusted_sql,
        node_name=node.name,
    )

    caps = plugin.capabilities()
    if write.intent is WriteIntentKind.MERGE and not caps.supports("sql_merge"):
        raise NodeExecutionError(
            f"Write intent {write.intent.value!r} unsupported by SQL plugin; "
            "failing before target mutation.",
            node_name=node.name,
            stage=FailureStage.WRITE.value,
            code="PMEXEC432",
        )
    if write.intent is WriteIntentKind.REPLACE_PARTITION:
        raise NodeExecutionError(
            "replace_partition is not supported by the 0.6 reference plugin; "
            "failing before target mutation.",
            node_name=node.name,
            stage=FailureStage.WRITE.value,
            code="PMEXEC432",
        )

    result = plugin.execute_write(write, params=params or {}, context=context)
    if result.outcome is TransactionOutcome.UNKNOWN:
        result.diagnostics.append(
            {
                "code": "PMSQL440",
                "severity": "error",
                "message": "Unknown commit outcome; automatic retry suppressed.",
            }
        )
    return result


def safe_staging_name(*, run_id: str, node_name: str, port_name: str) -> str:
    """Build a durable cross-connection staging table name from safe parts."""
    digest = hashlib.sha1(run_id.encode("utf-8")).hexdigest()[:10]
    raw = f"pl_tmp_{digest}_{node_name}_{port_name}"
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    if cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return require_safe_identifier(cleaned[:60])


async def materialize_sql_temp(
    *,
    plugin: SqlPlugin,
    query: SqlQuery,
    temp_name: str,
    plan: PipelinePlan,
    node: Node,
    run_id: str,
    attempt: int,
    params: dict[str, Any] | None = None,
    allow_trusted_sql: bool = False,
    engine: str | None = None,
) -> RelationRef:
    """Materialize an intermediate SQL query as a durable staging relation."""
    context = _context(
        plan=plan,
        node=node,
        run_id=run_id,
        attempt=attempt,
        allow_trusted_sql=allow_trusted_sql,
        engine=engine or plugin.info.engine,
    )
    _assert_trusted_sql_allowed(
        value=query,
        plugin=plugin,
        allow_trusted_sql=allow_trusted_sql,
        node_name=node.name,
    )
    result = plugin.materialize_temp(
        query, temp_name=temp_name, params=params or {}, context=context
    )
    if result.outcome is not TransactionOutcome.COMMITTED or result.relation is None:
        raise NodeExecutionError(
            f"SQL temp materialization for {node.name!r} failed "
            f"(outcome={result.outcome.value}).",
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMEXEC433",
        )
    return result.relation
