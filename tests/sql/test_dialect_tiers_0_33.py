"""0.33 dialect tiers, merge compile, and model DDL helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from etlantic.sql.expression import col
from etlantic.sql.protocol import (
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
