# pyright: reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Graduated 0.17 portable families on Polars (string-advanced + window/1).

Requires:

    uv sync --group polars

Run with:

    uv run --group polars python examples/portable_wave17.py
"""

from __future__ import annotations

from typing import Any

# Optional dataframe plugin factories and runtime reports are dynamic by design.
# pyright: reportAttributeAccessIssue=false
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
from etlantic.plan import explain_plan, plan_pipeline
from etlantic.registry import PlanningContext
from etlantic.transform import Window
from etlantic.transform import functions as F
from etlantic_polars import create_plugin


class RawRow(Data):
    id: int
    name: str
    score: float


class RankedRow(Data):
    id: int
    name: str
    rn: int


class RankRows(Transformation):
    rows: Input[RawRow]
    result: Output[RankedRow]


@RankRows.portable
def rank_rows(rows: Any) -> Any:
    w = Window.orderBy(F.col("score").desc())
    return (
        rows.withColumn("name", F.trim(F.col("name")))
        .withColumn("rn", F.row_number().over(w))
        .select("id", "name", "rn")
    )


class Wave17Pipeline(Pipeline):
    raw: Extract[RawRow] = Extract(asset="rows")
    ranked = RankRows.step(rows=raw)
    out: Load[RankedRow] = Load(input=ranked.result, asset="ranked")


def run_example() -> tuple[PipelineRuntime, object, dict[str, Any]]:
    profile = Profile(
        name="wave17-polars",
        dataframe_engine="polars",
        portable_transform_policy="require",
    )
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_plugin())
    runtime.memory.seed(
        "rows",
        [
            RawRow(id=1, name="  Ada  ", score=9.5),
            RawRow(id=2, name="Bob", score=8.0),
        ],
    )
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(Wave17Pipeline, context=context)
    explained = explain_plan(plan)
    report = Wave17Pipeline.run(profile=profile, runtime=runtime, context=context)
    return runtime, report, explained


if __name__ == "__main__":
    runtime, report, explained = run_example()
    print(report.to_text())
    step = next(s for s in explained["steps"] if s["node"] == "ranked")
    print(
        "implementation_kind=",
        step.get("implementation_kind"),
        "compiler=",
        (step.get("compiler") or {}).get("name"),
    )
    for row in runtime.memory.get("ranked") or []:
        data = row.model_dump() if hasattr(row, "model_dump") else dict(row)
        print(data)
