"""Execute transformation steps through the SQL protocol."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from etlantic.exceptions import NodeExecutionError
from etlantic.model import Node
from etlantic.plan.model import PipelinePlan
from etlantic.runtime.faults import FaultBoundary, maybe_inject
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
) -> bool:
    """Return True when capabilities/registration say sql (builtin name fallback)."""
    from etlantic.engines import get_engine_registry

    return get_engine_registry().is_sql_engine(engine, engines)


def resolve_sql_plugin(
    engine: str = "sql",
    *,
    plugins: dict[str, SqlPlugin] | None = None,
) -> SqlPlugin:
    if plugins and engine in plugins:
        return plugins[engine]
    plugin = load_sql_plugin(engine)
    if plugin is not None:
        return plugin
    raise NodeExecutionError(
        f"No SQL plugin available for engine {engine!r}. Install etlantic-sql.",
        node_name="sql",
        stage=FailureStage.TRANSFORM.value,
        code="PMEXEC430",
    )


def _context(
    *,
    plan: PipelinePlan,
    node: Node,
    run_id: str,
    attempt: int,
    allow_trusted_sql: bool,
) -> SqlExecutionContext:
    return SqlExecutionContext(
        run_id=run_id,
        pipeline_id=plan.pipeline_id,
        plan_id=plan.plan_id,
        step_name=node.name,
        engine="sql",
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
            code="PMEXEC435",
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
        code="PMEXEC431",
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
) -> SqlExecutionResult:
    """Publish a SQL query/relation into a sink without fetching intermediates."""
    maybe_inject(FaultBoundary.LOAD, step_name=node.name)
    context = _context(
        plan=plan,
        node=node,
        run_id=run_id,
        attempt=attempt,
        allow_trusted_sql=allow_trusted_sql,
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
) -> RelationRef:
    """Materialize an intermediate SQL query as a durable staging relation."""
    context = _context(
        plan=plan,
        node=node,
        run_id=run_id,
        attempt=attempt,
        allow_trusted_sql=allow_trusted_sql,
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
