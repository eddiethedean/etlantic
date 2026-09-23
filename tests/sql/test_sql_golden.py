# pyright: reportAttributeAccessIssue=false, reportMissingParameterType=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Golden fixtures for SQL plan / compile / evidence shapes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.sql.test_sql_runtime import CustomerPipeline

from etlantic import Profile
from etlantic.plan import explain_plan
from etlantic.registry import (
    BindingDescriptor,
    PlanningContext,
    builtin_stub_registry,
)
from etlantic.sql.discovery import register_discovered_plugins
from etlantic.sql.expression import col
from etlantic.sql.protocol import RelationRef, SqlExecutionContext, SqlQuery

pytestmark = pytest.mark.sql

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sql_plugin():
    pytest.importorskip("sqlalchemy")
    import os

    os.environ.setdefault("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from etlantic_sql import create_plugin

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
    assert explanation["sql_protocol"] == "etlantic.sql/1"
    assert explanation["sql_fusion"]

    ctx = SqlExecutionContext(
        run_id="g", pipeline_id="g", plan_id=plan.plan_id, step_name="normalized"
    )
    compiled = sql_plugin.compile_query(
        SqlQuery(
            source=RelationRef(name="raw_customers"), columns=(col("customer_id"),)
        ),
        context=ctx,
    )
    path = FIXTURES / f"compile_select_shape_{compiled.dialect}.json"
    assert path.is_file(), f"Missing committed golden: {path}"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert compiled.dialect == expected["dialect"]
    assert compiled.text == expected["text"]
    assert list(compiled.param_names) == list(expected["param_names"])
    assert bool(compiled.param_names) is expected["has_params"]
    assert ("SELECT" in compiled.text.upper()) is expected["text_contains_select"]
    assert dict(compiled.redacted_params) == dict(expected["redacted"])
