"""SQL-to-SQL example: normalize customers inside the database.

Requires ``pipelantic-sql``. Uses ``PIPELANTIC_SQL_URL`` (defaults to
in-memory SQLite for local demos).
"""

from __future__ import annotations

import os

from sqlalchemy import text

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
from pipelantic.plan import explain_plan
from pipelantic.registry import (
    BindingDescriptor,
    PlanningContext,
    builtin_stub_registry,
)
from pipelantic.sql import RelationRef, col, concat, select
from pipelantic.sql.discovery import register_discovered_plugins


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


class CustomerSqlPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="raw_customers")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(input=normalized.result, binding="curated_customers")


def main() -> None:
    os.environ.setdefault("PIPELANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from pipelantic_sql import create_plugin

    plugin = create_plugin()
    engine = plugin._get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS curated_customers"))
        conn.execute(text("DROP TABLE IF EXISTS raw_customers"))
        conn.execute(
            text(
                "CREATE TABLE raw_customers ("
                "customer_id INTEGER, first_name TEXT, last_name TEXT)"
            )
        )
        conn.execute(text("INSERT INTO raw_customers VALUES (1, 'Ada', 'Lovelace')"))
        conn.execute(
            text("CREATE TABLE curated_customers (customer_id INTEGER, full_name TEXT)")
        )

    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": plugin})
    registry.register_binding(
        BindingDescriptor(
            binding="raw_customers",
            provider="sql",
            location="raw_customers",
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
    profile = Profile(name="sql-example", sql_engine="sql")
    context = PlanningContext.create(profile, registry=registry)
    CustomerSqlPipeline.validate(profile=profile, context=context).raise_for_errors()
    plan = CustomerSqlPipeline.plan(profile=profile, context=context)
    print(explain_plan(plan)["sql_fusion"])

    runtime = PipelineRuntime(registry=registry)
    runtime.register_sql_plugin("sql", plugin)
    before = plugin.rows_fetched_total()
    report = CustomerSqlPipeline.run(profile=profile, runtime=runtime, context=context)
    print(report.to_text())
    print("rows_fetched", plugin.rows_fetched_total() - before)
    with engine.connect() as conn:
        print(list(conn.execute(text("SELECT * FROM curated_customers"))))


if __name__ == "__main__":
    main()
