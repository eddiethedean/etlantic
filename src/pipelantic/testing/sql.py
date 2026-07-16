"""Reusable SQL plugin conformance helpers."""

from __future__ import annotations

from pipelantic.sql.expression import col, select
from pipelantic.sql.protocol import (
    SQL_PROTOCOL_VERSION,
    RelationRef,
    SqlExecutionContext,
    SqlPlugin,
)


def assert_sql_plugin_info(plugin: SqlPlugin) -> None:
    info = plugin.info
    assert info.engine == "sql"
    assert info.protocol_version == SQL_PROTOCOL_VERSION
    caps = plugin.capabilities()
    assert caps.supports("sql")
    assert caps.supports("transactions")
    assert caps.supports("sql_catalog_inspect")


def run_sql_conformance_suite(plugin: SqlPlugin) -> None:
    """Minimal conformance checks for SQL plugins (driver-backed)."""
    assert_sql_plugin_info(plugin)
    ctx = SqlExecutionContext(
        run_id="conformance",
        pipeline_id="conformance",
        plan_id="plan",
        step_name="step",
    )
    # Identifier policy
    quoted = plugin.quote_identifier("customers")
    assert "customers" in quoted
    try:
        plugin.quote_identifier("customers; drop table t")
        raise AssertionError("expected illegal identifier to fail")
    except ValueError:
        pass

    # Compile must use placeholders, not interpolated literals
    from pipelantic.sql.protocol import LiteralExpr, SqlQuery

    query = SqlQuery(
        source=RelationRef(name="customers"),
        columns=(col("customer_id"),),
        where=LiteralExpr(value="x"),
    )
    compiled = plugin.compile_query(query, context=ctx)
    assert ":p" in compiled.text or compiled.param_names
    assert "x" not in compiled.text
    assert all(v == "<redacted>" for v in compiled.redacted_params.values())

    assert plugin.rows_fetched_total() == 0
    _ = select(col("customer_id"), source="customers")
