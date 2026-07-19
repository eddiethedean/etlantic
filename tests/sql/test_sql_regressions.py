"""Regression tests for 0.6 SQL correctness fixes."""

from __future__ import annotations

import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    Transformation,
)
from etlantic.exceptions import NodeExecutionError
from etlantic.model import LogicalGraph, Node, NodeKind
from etlantic.plan.model import PipelinePlan
from etlantic.registry import (
    BindingDescriptor,
    PlanningContext,
    builtin_stub_registry,
)
from etlantic.runtime.logging import redact_message
from etlantic.runtime.request import RetryPolicy, RunRequest
from etlantic.runtime.sql_exec import execute_sql_sink, safe_staging_name
from etlantic.sql import RelationRef, col, select
from etlantic.sql.discovery import register_discovered_plugins
from etlantic.sql.expression import col as col_expr
from etlantic.sql.protocol import SqlExecutionContext, TransactionOutcome

pytestmark = pytest.mark.sql


class Item(Data):
    id: int
    name: str


class LocalMake(Transformation):
    items: Input[Item]
    result: Output[Item]


@LocalMake.implementation("local")
def make_local(items: list[Item]) -> list[Item]:
    return list(items)


class PythonToSqlPipeline(Pipeline):
    src: Extract[Item] = Extract(asset="mem_items")
    made = LocalMake.step(items=src)
    dst: Load[Item] = Load(input=made.result, asset="sql_dst")


class FailWriteNorm(Transformation):
    customers: Input[Item]
    result: Output[Item]


@FailWriteNorm.implementation("sql")
def fail_norm(customers: RelationRef):
    return select(col("id"), col("name"), source=customers)


class FailWritePipeline(Pipeline):
    raw: Extract[Item] = Extract(asset="raw_items")
    step = FailWriteNorm.step(customers=raw)
    curated: Load[Item] = Load(input=step.result, asset="missing_dst")


def test_invalid_write_intent_fails_closed(sql_plugin) -> None:
    import anyio

    plan = PipelinePlan(
        schema="etlantic.plan/1",
        plan_id="p",
        pipeline_id="pipe",
        pipeline_name="pipe",
        profile_name="t",
        fingerprint="f",
        logical_graph=LogicalGraph(
            pipeline_id="pipe", pipeline_name="pipe", nodes=(), edges=()
        ),
    )
    node = Node(
        name="sink",
        kind=NodeKind.SINK,
        identity="sink",
        binding="out",
    )

    async def _run() -> None:
        await execute_sql_sink(
            plugin=sql_plugin,
            node=node,
            source_value=RelationRef(name="t"),
            plan=plan,
            run_id="r",
            attempt=1,
            target_location="out",
            write_intent="not_a_real_intent",
        )

    with pytest.raises(NodeExecutionError) as exc:
        anyio.run(_run)
    assert exc.value.code == "PMEXEC432"


def test_write_failure_marks_run_failed(sql_plugin) -> None:
    from sqlalchemy import text

    engine = sql_plugin._get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS missing_dst"))
        conn.execute(text("DROP TABLE IF EXISTS raw_items"))
        conn.execute(text("CREATE TABLE raw_items (id INTEGER, name TEXT)"))
        conn.execute(text("INSERT INTO raw_items VALUES (1, 'a')"))
        # missing_dst intentionally absent → INSERT SELECT fails → ROLLED_BACK

    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": sql_plugin})
    registry.register_binding(
        BindingDescriptor(binding="raw_items", provider="sql", location="raw_items")
    )
    registry.register_binding(
        BindingDescriptor(
            binding="missing_dst",
            provider="sql",
            location="missing_dst",
            metadata={"write_intent": "insert_select"},
        )
    )
    profile = Profile(name="fail-write", sql_engine="sql")
    context = PlanningContext.create(profile, registry=registry)
    runtime = PipelineRuntime(registry=registry)
    runtime.register_sql_plugin("sql", sql_plugin)
    report = FailWritePipeline.run(profile=profile, runtime=runtime, context=context)
    assert report.status.value in {"failed", "partial"}


def test_unknown_commit_not_retried() -> None:
    from etlantic.runtime.orchestrator import LocalOrchestrator

    orch = LocalOrchestrator.__new__(LocalOrchestrator)
    orch.request = RunRequest(
        intent="standard",
        retry=RetryPolicy(max_attempts=3),
    )
    exc = NodeExecutionError(
        "unknown",
        node_name="s",
        stage="publication",
        code="PMEXEC434",
    )
    assert orch._should_retry(exc) is False


def test_redact_dsn_credentials() -> None:
    msg = "could not connect to postgresql+psycopg://alice:s3cret@localhost:5432/db"
    redacted = redact_message(msg)
    assert "s3cret" not in redacted
    assert "alice:***@" in redacted


def test_safe_staging_name_is_identifier() -> None:
    name = safe_staging_name(run_id="run-1", node_name="a.b", port_name="result")
    assert "." not in name
    assert name[0].isalpha() or name[0] == "_"


def test_temp_handoff_across_executes(sql_plugin) -> None:
    """Durable staging must be visible on a subsequent connection/execute."""
    from sqlalchemy import text

    engine = sql_plugin._get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS src_t"))
        conn.execute(text("DROP TABLE IF EXISTS pl_tmp_handoff_test"))
        conn.execute(text("CREATE TABLE src_t (id INTEGER)"))
        conn.execute(text("INSERT INTO src_t VALUES (1), (2)"))

    ctx = SqlExecutionContext(
        run_id="handoff", pipeline_id="p", plan_id="pl", step_name="s"
    )
    query = select(col_expr("id"), source="src_t")
    temp = "pl_tmp_handoff_test"
    result = sql_plugin.materialize_temp(query, temp_name=temp, params={}, context=ctx)
    assert result.outcome is TransactionOutcome.COMMITTED
    assert result.relation is not None
    with engine.connect() as conn:
        rows = list(conn.execute(text(f'SELECT id FROM "{temp}" ORDER BY 1')))
    assert rows == [(1,), (2,)]
    sql_plugin.cleanup_staging()


def test_python_to_sql_load_records(sql_plugin) -> None:
    from sqlalchemy import text

    engine = sql_plugin._get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS sql_dst"))
        conn.execute(text("CREATE TABLE sql_dst (id INTEGER, name TEXT)"))

    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": sql_plugin})
    registry.register_binding(
        BindingDescriptor(binding="mem_items", provider="memory", location="mem_items")
    )
    registry.register_binding(
        BindingDescriptor(
            binding="sql_dst",
            provider="sql",
            location="sql_dst",
            metadata={"write_intent": "insert_select"},
        )
    )
    # Default engine local so LocalMake selects local; sink provider forces SQL region.
    profile = Profile(name="hybrid-load", sql_engine=None)
    context = PlanningContext.create(profile, registry=registry)
    # Force sql plugin available for sink even without sql_engine default.
    runtime = PipelineRuntime(registry=registry)
    runtime.register_sql_plugin("sql", sql_plugin)
    runtime.memory.seed(
        "mem_items",
        [Item(id=1, name="a"), Item(id=2, name="b")],
    )
    # Plan/run with sql_engine so sink is SQL; LocalMake falls back to sole local impl.
    profile = Profile(name="hybrid-load", sql_engine="sql")
    context = PlanningContext.create(profile, registry=registry)
    report = PythonToSqlPipeline.run(profile=profile, runtime=runtime, context=context)
    assert report.status.value == "succeeded"
    with engine.connect() as conn:
        rows = list(conn.execute(text("SELECT id, name FROM sql_dst ORDER BY 1")))
    assert rows == [(1, "a"), (2, "b")]
