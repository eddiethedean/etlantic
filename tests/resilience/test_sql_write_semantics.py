"""SQL runtime write/retry semantics (WP6)."""

from __future__ import annotations

import os

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
from etlantic.registry import BindingDescriptor, PlanningContext, builtin_stub_registry
from etlantic.reliability import RetrySafetyDeclaration
from etlantic.runtime.request import RetryPolicy, RunRequest
from etlantic.runtime.state import RunStatus
from etlantic.sql import RelationRef
from etlantic.sql.discovery import register_discovered_plugins

pytestmark = pytest.mark.sql


class Item(Data):
    id: int
    name: str


class FailSql(Transformation):
    items: Input[Item]
    result: Output[Item]


@FailSql.implementation("sql")
def fail_sql(items: RelationRef):
    _ = items
    raise RuntimeError("sql-step-boom")


class FailSqlPipeline(Pipeline):
    raw: Extract[Item] = Extract(asset="raw_items")
    step = FailSql.step(items=raw)
    curated: Load[Item] = Load(input=step.result, asset="sql_dst")


@pytest.fixture
def sql_plugin():
    pytest.importorskip("sqlalchemy")
    os.environ.setdefault("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from etlantic_sql import create_plugin

    return create_plugin()


def test_sql_unsafe_retry_blocked_with_pmexec501(sql_plugin) -> None:
    from sqlalchemy import text

    engine = sql_plugin._get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS sql_dst"))
        conn.execute(text("DROP TABLE IF EXISTS raw_items"))
        conn.execute(text("CREATE TABLE raw_items (id INTEGER, name TEXT)"))
        conn.execute(text("INSERT INTO raw_items VALUES (1, 'a')"))
        conn.execute(text("CREATE TABLE sql_dst (id INTEGER, name TEXT)"))

    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": sql_plugin})
    registry.register_binding(
        BindingDescriptor(binding="raw_items", provider="sql", location="raw_items")
    )
    registry.register_binding(
        BindingDescriptor(
            binding="sql_dst",
            provider="sql",
            location="sql_dst",
            metadata={"write_intent": "insert_select"},
        )
    )
    profile = Profile(name="sql-retry", sql_engine="sql")
    context = PlanningContext.create(profile, registry=registry)
    runtime = PipelineRuntime(registry=registry)
    runtime.register_sql_plugin("sql", sql_plugin)
    report = FailSqlPipeline.run(
        profile=profile,
        runtime=runtime,
        context=context,
        request=RunRequest(
            retry=RetryPolicy(max_attempts=3, backoff_seconds=0),
            metadata={
                "retry_safety": {
                    "step": RetrySafetyDeclaration(subject_id="step", safe=False)
                }
            },
        ),
    )
    assert report.status in {RunStatus.FAILED, RunStatus.PARTIAL}
    assert any(d.code == "PMEXEC501" for d in report.diagnostics)
    step = next(s for s in report.steps if s.step_name == "step")
    assert step.attempts == 1
