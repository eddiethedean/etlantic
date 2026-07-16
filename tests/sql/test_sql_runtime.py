"""SQL plugin end-to-end tests (SQLite by default via PIPELANTIC_SQL_URL)."""

from __future__ import annotations

import pytest

from pipelantic import (
    Data,
    Input,
    Output,
    Pipeline,
    PipelineRuntime,
    Profile,
    Sink,
    Source,
    Transformation,
)
from pipelantic.exceptions import PipelineValidationError
from pipelantic.plan import explain_plan
from pipelantic.registry import (
    BindingDescriptor,
    PlanningContext,
    builtin_stub_registry,
)
from pipelantic.sql import RelationRef, col, concat, select
from pipelantic.sql.discovery import register_discovered_plugins
from pipelantic.testing import assert_sql_plugin_info, run_sql_conformance_suite

pytestmark = pytest.mark.sql


class RawCustomer(Data):
    customer_id: int
    first_name: str
    last_name: str


class Customer(Data):
    customer_id: int
    full_name: str


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


@NormalizeCustomers.implementation("sql")
def normalize_sql(customers: RelationRef):
    return select(
        col("customer_id"),
        concat(col("first_name"), col("last_name"), as_="full_name"),
        source=customers,
    )


class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="raw_customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(input=normalized.result, binding="curated_customers")


class Row(Data):
    id: int


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("sql")
def identity_sql(rows: RelationRef):
    return select(col("id"), source=rows)


class MergeProbePipeline(Pipeline):
    src: Source[Row] = Source(binding="t")
    step = Identity.step(rows=src)
    sink: Sink[Row] = Sink(input=step.result, binding="out")


@pytest.fixture
def sql_plugin(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("sqlalchemy")
    monkeypatch.setenv("PIPELANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from pipelantic_sql import create_plugin

    return create_plugin()


def test_sql_conformance(sql_plugin) -> None:
    run_sql_conformance_suite(sql_plugin)
    assert_sql_plugin_info(sql_plugin)


def test_sql_to_sql_no_python_fetch(sql_plugin) -> None:
    from sqlalchemy import text

    engine = sql_plugin._get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS curated_customers"))
        conn.execute(text("DROP TABLE IF EXISTS raw_customers"))
        conn.execute(
            text(
                "CREATE TABLE raw_customers ("
                "customer_id INTEGER, first_name TEXT, last_name TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO raw_customers VALUES "
                "(1, 'Ada', 'Lovelace'), (2, 'Grace', 'Hopper')"
            )
        )
        conn.execute(
            text("CREATE TABLE curated_customers (customer_id INTEGER, full_name TEXT)")
        )

    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": sql_plugin})
    registry.register_binding(
        BindingDescriptor(
            binding="raw_customers",
            provider="sql",
            kind="relation",
            location="raw_customers",
        )
    )
    registry.register_binding(
        BindingDescriptor(
            binding="curated_customers",
            provider="sql",
            kind="relation",
            location="curated_customers",
            metadata={"write_intent": "insert_select"},
        )
    )
    profile = Profile(name="sql-test", sql_engine="sql")
    context = PlanningContext.create(profile, registry=registry)
    CustomerPipeline.validate(profile=profile, context=context).raise_for_errors()
    plan = CustomerPipeline.plan(profile=profile, context=context)
    assert any(r.engine == "sql" for r in plan.regions)
    explanation = explain_plan(plan)
    assert explanation.get("sql_protocol") == "pipelantic.sql/1"

    runtime = PipelineRuntime(registry=registry)
    runtime.register_sql_plugin("sql", sql_plugin)
    before = sql_plugin.rows_fetched_total()
    report = CustomerPipeline.run(profile=profile, runtime=runtime, context=context)
    assert report.status.value == "succeeded"
    assert sql_plugin.rows_fetched_total() == before

    with engine.connect() as conn:
        rows = list(
            conn.execute(
                text("SELECT customer_id, full_name FROM curated_customers ORDER BY 1")
            )
        )
    assert rows == [(1, "Ada Lovelace"), (2, "Grace Hopper")]


def test_merge_fails_closed_on_sqlite(sql_plugin) -> None:
    profile = Profile(
        name="sql-merge",
        sql_engine="sql",
        required_sql_capabilities=("sql_merge",),
    )
    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": sql_plugin})
    context = PlanningContext.create(profile, registry=registry)
    if sql_plugin.capabilities().supports("sql_merge"):
        pytest.skip("reference URL supports merge")

    registry.register_binding(
        BindingDescriptor(binding="t", provider="sql", location="t")
    )
    registry.register_binding(
        BindingDescriptor(binding="out", provider="sql", location="out")
    )
    with pytest.raises(PipelineValidationError):
        MergeProbePipeline.plan(profile=profile, context=context)
