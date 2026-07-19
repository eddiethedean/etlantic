"""Failure recovery: unsupported merge fails closed before mutation."""

from __future__ import annotations

import os
import sys

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    Profile,
    Transformation,
)
from etlantic.exceptions import PipelineValidationError
from etlantic.registry import (
    BindingDescriptor,
    PlanningContext,
    builtin_stub_registry,
)
from etlantic.sql import RelationRef, col, select
from etlantic.sql.discovery import register_discovered_plugins


class Row(Data):
    id: int


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("sql")
def identity_sql(rows: RelationRef):
    return select(col("id"), source=rows)


class MergePipeline(Pipeline):
    src: Extract[Row] = Extract(asset="t")
    step = Identity.step(rows=src)
    sink: Load[Row] = Load(input=step.result, asset="out")


def main() -> None:
    os.environ.setdefault("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    from etlantic_sql import create_plugin

    plugin = create_plugin()
    registry = builtin_stub_registry()
    register_discovered_plugins(registry, plugins={"sql": plugin})
    registry.register_binding(
        BindingDescriptor(binding="t", provider="sql", location="t")
    )
    registry.register_binding(
        BindingDescriptor(binding="out", provider="sql", location="out")
    )
    profile = Profile(
        name="sql-fail",
        sql_engine="sql",
        required_sql_capabilities=("sql_merge",),
    )
    context = PlanningContext.create(profile, registry=registry)
    if plugin.capabilities().supports("sql_merge"):
        print("dialect supports merge; skip fail-closed demo")
        return
    try:
        MergePipeline.plan(profile=profile, context=context)
    except PipelineValidationError as exc:
        print("fail-closed before mutation:", exc)
        sys.exit(0)
    raise SystemExit("expected validation failure for unsupported merge")


if __name__ == "__main__":
    main()
