"""Hybrid SQL↔Python boundary example (planned materialization)."""

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
from pipelantic.registry import (
    BindingDescriptor,
    PlanningContext,
    builtin_stub_registry,
)
from pipelantic.sql import RelationRef, col, select
from pipelantic.sql.discovery import register_discovered_plugins


class Row(Data):
    id: int
    label: str


class SqlRead(Transformation):
    rows: Input[Row]
    result: Output[Row]


@SqlRead.implementation("sql")
def sql_read(rows: RelationRef):
    return select(col("id"), col("label"), source=rows)


class PythonTouch(Transformation):
    rows: Input[Row]
    result: Output[Row]


@PythonTouch.implementation("local")
def python_touch(rows: list[Row]) -> list[Row]:
    return [Row(id=r.id, label=r.label.upper()) for r in rows]


class HybridPipeline(Pipeline):
    src: Source[Row] = Source(binding="src_rows")
    from_sql = SqlRead.step(rows=src)
    touched = PythonTouch.step(rows=from_sql.result)
    out: Sink[Row] = Sink(input=touched.result, binding="out_rows")


def main() -> None:
    os.environ.setdefault("PIPELANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from pipelantic_sql import create_plugin

    plugin = create_plugin()
    engine = plugin._get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS out_rows"))
        conn.execute(text("DROP TABLE IF EXISTS src_rows"))
        conn.execute(text("CREATE TABLE src_rows (id INTEGER, label TEXT)"))
        conn.execute(text("INSERT INTO src_rows VALUES (1, 'ada')"))
        conn.execute(text("CREATE TABLE out_rows (id INTEGER, label TEXT)"))

    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": plugin})
    registry.register_binding(
        BindingDescriptor(binding="src_rows", provider="sql", location="src_rows")
    )
    registry.register_binding(
        BindingDescriptor(binding="out_rows", provider="memory", location="out_rows")
    )
    # Hybrid: SQL region then local Python; sink uses memory.
    profile = Profile(name="hybrid", sql_engine="sql")
    context = PlanningContext.create(profile, registry=registry)
    runtime = PipelineRuntime(registry=registry)
    runtime.register_sql_plugin("sql", plugin)
    report = HybridPipeline.run(profile=profile, runtime=runtime, context=context)
    print(report.to_text())
    print("memory", runtime.memory.get("out_rows"))


if __name__ == "__main__":
    main()
