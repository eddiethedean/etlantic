"""Golden fixtures for SQL plan / compile / evidence shapes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.sql.test_sql_runtime import CustomerPipeline

from pipelantic import Profile
from pipelantic.plan import explain_plan
from pipelantic.registry import (
    BindingDescriptor,
    PlanningContext,
    builtin_stub_registry,
)
from pipelantic.sql.discovery import register_discovered_plugins
from pipelantic.sql.expression import col
from pipelantic.sql.protocol import RelationRef, SqlExecutionContext, SqlQuery

pytestmark = pytest.mark.sql

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sql_plugin(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("sqlalchemy")
    monkeypatch.setenv("PIPELANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from pipelantic_sql import create_plugin

    return create_plugin()


def test_explain_plan_sql_golden_shape(sql_plugin) -> None:
    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": sql_plugin})
    registry.register_binding(
        BindingDescriptor(
            binding="raw_customers", provider="sql", location="raw_customers"
        )
    )
    registry.register_binding(
        BindingDescriptor(
            binding="curated_customers",
            provider="sql",
            location="curated_customers",
            metadata={"write_intent": "insert_select"},
        )
    )
    profile = Profile(name="sql-golden", sql_engine="sql")
    context = PlanningContext.create(profile, registry=registry)
    plan = CustomerPipeline.plan(profile=profile, context=context)
    explanation = explain_plan(plan)
    assert explanation["sql_protocol"] == "pipelantic.sql/1"
    assert explanation["sql_fusion"]
    # Dialect-sensitive compile fixture
    ctx = SqlExecutionContext(
        run_id="g", pipeline_id="g", plan_id=plan.plan_id, step_name="normalized"
    )
    compiled = sql_plugin.compile_query(
        SqlQuery(
            source=RelationRef(name="raw_customers"), columns=(col("customer_id"),)
        ),
        context=ctx,
    )
    snapshot = {
        "dialect": compiled.dialect,
        "has_params": bool(compiled.param_names),
        "text_contains_select": "SELECT" in compiled.text.upper(),
        "redacted": compiled.redacted_params,
    }
    expected_path = FIXTURES / "compile_select_shape.json"
    if not expected_path.exists():
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.write_text(
            json.dumps(snapshot, indent=2) + "\n", encoding="utf-8"
        )
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert snapshot == expected
