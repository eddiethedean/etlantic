"""Execute transformation steps through the SQL protocol."""

from __future__ import annotations

from typing import Any

from pipelantic.exceptions import NodeExecutionError
from pipelantic.model import Node
from pipelantic.plan.model import PipelinePlan
from pipelantic.runtime.state import FailureStage
from pipelantic.sql.discovery import load_sql_plugin
from pipelantic.sql.protocol import (
    SQL_ENGINES,
    RelationRef,
    SqlExecutionContext,
    SqlExecutionResult,
    SqlPlugin,
    SqlQuery,
    SqlWrite,
    TransactionOutcome,
    WriteIntentKind,
)
from pipelantic.transformation import ImplementationRecord


def is_sql_engine(engine: str) -> bool:
    return engine in SQL_ENGINES


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
        f"No SQL plugin available for engine {engine!r}. Install pipelantic-sql.",
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
    _ = _context(
        plan=plan,
        node=node,
        run_id=run_id,
        attempt=attempt,
        allow_trusted_sql=allow_trusted_sql,
    )
    kwargs = {**dict(params), **dict(inputs)}
    result = impl.callable(**kwargs)
    if isinstance(result, (SqlQuery, RelationRef, SqlWrite)):
        return result
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
    except ValueError:
        intent = WriteIntentKind.INSERT_SELECT

    if isinstance(source_value, SqlWrite):
        write = source_value
    else:
        write = SqlWrite(intent=intent, target=target, source=source_value)

    # Fail closed for unsupported merge / partition replace before mutation.
    caps = plugin.capabilities()
    if write.intent is WriteIntentKind.MERGE and not caps.supports("sql_merge"):
        raise NodeExecutionError(
            f"Write intent {write.intent.value!r} unsupported by SQL plugin; "
            "failing before target mutation.",
            node_name=node.name,
            stage=FailureStage.PUBLICATION.value,
            code="PMEXEC432",
        )
    if write.intent is WriteIntentKind.REPLACE_PARTITION:
        raise NodeExecutionError(
            "replace_partition is not supported by the 0.6 reference plugin; "
            "failing before target mutation.",
            node_name=node.name,
            stage=FailureStage.PUBLICATION.value,
            code="PMEXEC432",
        )

    result = plugin.execute_write(write, params=params or {}, context=context)
    if result.outcome is TransactionOutcome.UNKNOWN:
        # Caller must not retry blindly.
        result.diagnostics.append(
            {
                "code": "PMSQL440",
                "severity": "error",
                "message": "Unknown commit outcome; automatic retry suppressed.",
            }
        )
    return result


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
    """Materialize an intermediate SQL query as a temp relation (no Python fetch)."""
    context = _context(
        plan=plan,
        node=node,
        run_id=run_id,
        attempt=attempt,
        allow_trusted_sql=allow_trusted_sql,
    )
    result = plugin.materialize_temp(
        query, temp_name=temp_name, params=params or {}, context=context
    )
    if result.relation is None:
        raise NodeExecutionError(
            f"SQL temp materialization for {node.name!r} produced no relation.",
            node_name=node.name,
            stage=FailureStage.TRANSFORM.value,
            code="PMEXEC433",
        )
    return result.relation
