"""Transactional replace / insert-select write example."""

from __future__ import annotations

import os

from sqlalchemy import text

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
from etlantic.registry import (
    BindingDescriptor,
    PlanningContext,
    builtin_stub_registry,
)
from etlantic.sql import RelationRef, col, select
from etlantic.sql.discovery import register_discovered_plugins


class Item(Data):
    id: int
    name: str


class Pass(Transformation):
    items: Input[Item]
    result: Output[Item]


@Pass.implementation("sql")
def pass_sql(items: RelationRef):
    return select(col("id"), col("name"), source=items)


class TxPipeline(Pipeline):
    src: Extract[Item] = Extract(asset="items_src")
    step = Pass.step(items=src)
    dst: Load[Item] = Load(input=step.result, asset="items_dst")


def main() -> None:
    os.environ.setdefault("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from etlantic_sql import create_plugin

    plugin = create_plugin()
    engine = plugin._get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS items_dst"))
        conn.execute(text("DROP TABLE IF EXISTS items_src"))
        conn.execute(text("CREATE TABLE items_src (id INTEGER, name TEXT)"))
        conn.execute(text("INSERT INTO items_src VALUES (1, 'a'), (2, 'b')"))
        conn.execute(text("CREATE TABLE items_dst (id INTEGER, name TEXT)"))

    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": plugin})
    for name in ("items_src", "items_dst"):
        meta = {"write_intent": "insert_select"} if name.endswith("dst") else {}
        registry.register_binding(
            BindingDescriptor(
                binding=name, provider="sql", location=name, metadata=meta
            )
        )
    profile = Profile(name="sql-txn", sql_engine="sql")
    context = PlanningContext.create(profile, registry=registry)
    runtime = PipelineRuntime(registry=registry)
    runtime.register_sql_plugin("sql", plugin)
    report = TxPipeline.run(profile=profile, runtime=runtime, context=context)
    print(report.to_text())
    with engine.connect() as conn:
        print(list(conn.execute(text("SELECT * FROM items_dst ORDER BY 1"))))


if __name__ == "__main__":
    main()
