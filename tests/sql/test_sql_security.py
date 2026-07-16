"""Security corpus for SQL compilation and identifier policy."""

from __future__ import annotations

import pytest

from pipelantic.sql import RelationRef, col, lit, select
from pipelantic.sql.protocol import LiteralExpr, SqlExecutionContext, SqlQuery

pytestmark = pytest.mark.sql


@pytest.fixture
def sql_plugin(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("sqlalchemy")
    monkeypatch.setenv("PIPELANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from pipelantic_sql import create_plugin

    return create_plugin()


def _ctx() -> SqlExecutionContext:
    return SqlExecutionContext(
        run_id="sec",
        pipeline_id="sec",
        plan_id="plan",
        step_name="step",
    )


def test_value_injection_uses_bound_params(sql_plugin) -> None:
    query = SqlQuery(
        source=RelationRef(name="customers"),
        columns=(col("customer_id"),),
        where=LiteralExpr(value="1; DROP TABLE customers;--"),
    )
    compiled = sql_plugin.compile_query(query, context=_ctx())
    assert "DROP" not in compiled.text.upper()
    assert ":p" in compiled.text
    assert all(v == "<redacted>" for v in compiled.redacted_params.values())


def test_identifier_injection_rejected(sql_plugin) -> None:
    with pytest.raises(ValueError):
        sql_plugin.quote_identifier('customers"; DROP TABLE t;--')


def test_relation_name_injection_rejected(sql_plugin) -> None:
    with pytest.raises(ValueError):
        sql_plugin.relation_from_binding(binding="x", location='evil"; DROP TABLE t;--')


def test_trusted_fragments_disabled_by_default(sql_plugin) -> None:
    caps = sql_plugin.capabilities()
    assert not caps.supports("sql_trusted_fragments")


def test_compiled_artifacts_are_secret_free(sql_plugin) -> None:
    query = select(col("id"), lit("secret-token"), source="t")
    compiled = sql_plugin.compile_query(query, context=_ctx())
    assert "secret-token" not in compiled.text
    assert "secret-token" not in str(compiled.redacted_params)
    # Bound values may live in private metadata for execution only.
    bound = compiled.metadata.get("_bound_params") or {}
    assert "secret-token" in bound.values()
