"""0.33 dialect tiers, merge compile, and model DDL helpers."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("sqlalchemy")

from etlantic.sql.expression import col
from etlantic.sql.protocol import (
    AliasedExpr,
    CallExpr,
    RelationRef,
    SqlExecutionContext,
    SqlQuery,
    SqlWrite,
    WriteIntentKind,
)
from etlantic_sql.compiler import SqlCompiler
from etlantic_sql.dialect_tiers import detect_dialect_info
from etlantic_sql.plugin import PostgresSqlPlugin

pytestmark = pytest.mark.sql


def test_dialect_tier_a_sqlite_and_postgresql() -> None:
    assert detect_dialect_info("sqlite+pysqlite:///:memory:").tier == "A"
    assert detect_dialect_info("postgresql+psycopg://localhost/db").name == "postgresql"
    assert detect_dialect_info("postgresql+psycopg://localhost/db").supports_merge


def test_dialect_tier_b_mysql_gated() -> None:
    info = detect_dialect_info("mysql+pymysql://localhost/db")
    assert info.name == "mysql"
    assert info.tier == "B"
    assert not info.supports_merge


def test_sqlite_plugin_refuses_merge_compile() -> None:
    plugin = PostgresSqlPlugin(url="sqlite+pysqlite:///:memory:")
    assert not plugin.capabilities().supports("sql_merge")
    assert plugin.capabilities().supports("sql_cte")
    ctx = SqlExecutionContext(
        run_id="r", pipeline_id="p", plan_id="plan", step_name="m"
    )
    write = SqlWrite(
        intent=WriteIntentKind.MERGE,
        target=RelationRef(name="t"),
        source=RelationRef(name="s"),
        merge_keys=("id",),
    )
    with pytest.raises(ValueError, match="PostgreSQL"):
        plugin.compile_write(write, context=ctx)


def test_postgresql_merge_compile_on_conflict() -> None:
    compiler = SqlCompiler(dialect="postgresql", supports_merge=True)
    ctx = SqlExecutionContext(
        run_id="r", pipeline_id="p", plan_id="plan", step_name="m"
    )
    write = SqlWrite(
        intent=WriteIntentKind.MERGE,
        target=RelationRef(name="customers"),
        source=SqlQuery(
            source=RelationRef(name="staging"),
            columns=(col("id"), col("name")),
        ),
        merge_keys=("id",),
        metadata={"update_columns": ["name"]},
    )
    compiled = compiler.compile_write(write, context=ctx)
    assert "ON CONFLICT" in compiled.text
    assert "EXCLUDED" in compiled.text
    assert "DO UPDATE SET" in compiled.text


def test_postgresql_sigma_context_does_not_use_locale_case_mapping() -> None:
    """Final-sigma context classification must be locale-independent."""
    compiler = SqlCompiler(dialect="postgresql", supports_merge=True)
    compiled = compiler.compile_query(
        SqlQuery(
            source=RelationRef(name="customers"),
            columns=(
                AliasedExpr(
                    CallExpr("dtcs:lower", (col("name"),)),
                    "lower_name",
                ),
            ),
        ),
        context=SqlExecutionContext(
            run_id="r", pipeline_id="p", plan_id="plan", step_name="lower"
        ),
    )

    assert "RIGHT(" in compiled.text
    assert " !~ '" in compiled.text
    assert "UPPER(RIGHT(" not in compiled.text
    assert "LOWER(RIGHT(" not in compiled.text
    assert "TRANSLATE(" in compiled.text
    assert "ASCII(etlantic_chars.ch)" not in compiled.text


def test_postgresql_sigma_mapping_is_stable_under_c_collation() -> None:
    """Unicode sigma mapping must not depend on PostgreSQL's C locale."""
    if not os.environ.get("ETLANTIC_SQL_URL", "").startswith("postgresql"):
        pytest.skip("PostgreSQL collation verification requires ETLANTIC_SQL_URL")
    from sqlalchemy import create_engine, text

    compiler = SqlCompiler(dialect="postgresql", supports_merge=True)
    compiled = compiler.compile_query(
        SqlQuery(
            source=RelationRef(name="sigma_c_033"),
            columns=(
                AliasedExpr(
                    CallExpr("dtcs:lower", (col("name"),)),
                    "lower_name",
                ),
            ),
        ),
        context=SqlExecutionContext(
            run_id="r", pipeline_id="p", plan_id="plan", step_name="lower"
        ),
    )
    engine = create_engine(os.environ["ETLANTIC_SQL_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text('CREATE TEMP TABLE sigma_c_033 (name TEXT COLLATE "C")')
            )
            connection.execute(
                text("INSERT INTO sigma_c_033 VALUES ('A-Σ'), ('AΣ-B'), ('A-𞤀')")
            )
            rows = connection.execute(
                text(compiled.text), compiled.metadata["_bound_params"]
            ).all()
    finally:
        engine.dispose()
    assert rows == [("a-\u03c3",), ("a\u03c2-b",), ("a-𞤢",)]


def test_sql_compiler_evidence_fingerprints_unicode_database() -> None:
    """Unicode-dependent SQL lowering must identify its Unicode data version."""
    from etlantic_sql.transform_compiler import create_transform_compiler
    from etlantic_sql.unicode_data import UNICODE_DATA_FINGERPRINT, UNICODE_DATA_VERSION

    compiler = create_transform_compiler()
    assert compiler.info.environment["unicode"] == UNICODE_DATA_VERSION
    assert compiler.info.environment["unicode_fingerprint"] == UNICODE_DATA_FINGERPRINT


def test_sql_compiler_identity_honors_database_url(monkeypatch) -> None:
    """Compiler evidence must match the runtime URL fallback."""
    monkeypatch.delenv("ETLANTIC_SQL_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1/db"
    )
    from etlantic_sql.transform_compiler import create_transform_compiler

    compiler = create_transform_compiler()
    assert compiler.info.environment["dialect"] == "postgresql"


def test_sql_runtime_rejects_dialect_identity_mismatch() -> None:
    """Runtime engine overrides cannot bypass compiler dialect evidence."""
    from etlantic_sql.transform_compiler import _open_engine

    with pytest.raises(ValueError, match="does not match compiler evidence"):
        _open_engine(
            {"database_url": "postgresql+psycopg://postgres:postgres@127.0.0.1/db"},
            expected_dialect="sqlite",
        )


def test_model_create_and_pk_validation_sqlite() -> None:
    pytest.importorskip("sqlmodel")
    from sqlmodel import Field, SQLModel

    class Customer(SQLModel, table=True):
        __tablename__ = "customers_033"
        id: int = Field(primary_key=True)
        name: str

    plugin = PostgresSqlPlugin(url="sqlite+pysqlite:///:memory:")
    created = plugin.create_table_from_model(Customer)
    assert created["created"] is True
    assert created["primary_key"] == ["id"]
    checked = plugin.validate_primary_keys(
        RelationRef(name="customers_033"),
        expected_keys=["id"],
    )
    assert checked["ok"] is True
    bad = plugin.validate_primary_keys(
        RelationRef(name="customers_033"),
        expected_keys=["name"],
    )
    assert bad["ok"] is False
    assert any(d["code"] == "PMSQL431" for d in bad["diagnostics"])


def test_tier_b_plugin_refuses_engine() -> None:
    plugin = PostgresSqlPlugin(url="mysql+pymysql://localhost/db")
    assert plugin.info.dialect == "mysql"
    assert not plugin.capabilities().supports("transactions")
    with pytest.raises(ValueError, match="Tier"):
        plugin.get_engine()


@pytest.mark.sqlmodel
def test_sqlmodel_pk_helpers() -> None:
    pytest.importorskip("sqlmodel")
    from etlantic_sqlmodel import primary_key_fields, validate_model_primary_keys
    from sqlmodel import Field, SQLModel

    class Order(SQLModel, table=True):
        __tablename__ = "orders_033"
        order_id: int = Field(primary_key=True)
        amount: float

    assert primary_key_fields(Order) == ["order_id"]
    report = validate_model_primary_keys(Order, expected_keys=("order_id",))
    assert report.valid
    bad = validate_model_primary_keys(Order, expected_keys=("amount",))
    assert not bad.valid
