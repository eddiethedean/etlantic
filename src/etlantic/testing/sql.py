"""Reusable SQL plugin conformance helpers."""

from __future__ import annotations

from etlantic.sql.expression import col, select
from etlantic.sql.protocol import (
    SQL_PROTOCOL_VERSION,
    RelationRef,
    SqlExecutionContext,
    SqlPlugin,
    TransactionOutcome,
)
from etlantic.testing.capability_truthfulness import (
    assert_capability_claims_consistent,
)


def assert_sql_plugin_info(plugin: SqlPlugin) -> None:
    """Assert a SQL plugin advertises protocol version and core capabilities."""
    info = plugin.info
    assert info.engine == "sql"
    assert info.protocol_version == SQL_PROTOCOL_VERSION
    caps = plugin.capabilities()
    assert caps.supports("sql")
    assert caps.supports("transactions")
    assert caps.supports("sql_catalog_inspect")
    assert_capability_claims_consistent(caps)


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
    from etlantic.sql.protocol import LiteralExpr, SqlQuery

    secret_literal = "s3cr3t-value"
    query = SqlQuery(
        source=RelationRef(name="customers"),
        columns=(col("customer_id"),),
        where=LiteralExpr(value=secret_literal),
    )
    compiled = plugin.compile_query(query, context=ctx)
    assert ":p" in compiled.text or compiled.param_names
    # Redaction / no-leak: the literal must never appear in compiled artifacts.
    assert secret_literal not in compiled.text
    assert all(v == "<redacted>" for v in compiled.redacted_params.values())
    assert secret_literal not in str(compiled.to_dict())
    # Every declared parameter name must have a redacted entry (no silent gaps).
    for name in compiled.param_names:
        assert name in compiled.redacted_params, (
            f"Parameter {name!r} is declared but missing from redacted_params."
        )
    # Malformed-output guard: compiled statement text must be a non-empty string.
    assert isinstance(compiled.text, str) and compiled.text.strip(), (
        "Compiled SQL text must be a non-empty string."
    )

    assert plugin.rows_fetched_total() == 0
    _ = select(col("customer_id"), source="customers")

    # Dialect-tier / merge truthfulness
    caps = plugin.capabilities()
    dialect = str(getattr(plugin.info, "dialect", "") or "")
    if dialect == "postgresql":
        assert caps.supports("sql_merge"), "PostgreSQL must advertise sql_merge"
    elif dialect == "sqlite":
        assert not caps.supports("sql_merge"), (
            "SQLite reference path must not advertise sql_merge"
        )

    # Lazy relational claim lives on the transform compiler (SqlQuery handles),
    # not PluginCapabilities.lazy (which implies dataframe).
    if caps.supports("sql_cte"):
        assert caps.supports("sql"), "sql_cte requires sql"

    # Rollback / unknown-outcome classification surface
    assert TransactionOutcome.ROLLED_BACK.value == "rolled_back"
    assert TransactionOutcome.UNKNOWN.value == "unknown"
    assert hasattr(plugin, "execute")
