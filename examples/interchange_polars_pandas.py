"""Gate A demo: Polars → Pandas boundary with versioned etlantic.interchange/1.

Requires:

    uv sync --group dataframes

Or from published packages:

    pip install 'etlantic[dataframes]==0.21.0'

Run with:

    uv run python examples/interchange_polars_pandas.py
"""

from __future__ import annotations

from typing import Any

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
    explain_plan,
    plan_pipeline,
)
from etlantic.dataframe import discover_dataframe_plugins
from etlantic.interchange.tabular import SCHEMA
from etlantic.registry import PlanningContext
from etlantic.runtime import RunStatus


class Row(Data):
    value: int
    label: str


class PolarsIdentity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@PolarsIdentity.implementation("polars")
def polars_identity(rows):
    import polars as pl

    frame = rows if hasattr(rows, "with_columns") else pl.DataFrame(rows)
    return frame.select("value", "label")


class PandasIdentity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@PandasIdentity.implementation("pandas")
def pandas_identity(rows):
    import pandas as pd

    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    return frame[["value", "label"]]


class CrossEnginePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    polars_step = PolarsIdentity.step(rows=raw)
    pandas_step = PandasIdentity.step(rows=polars_step.result)
    out: Load[Row] = Load(input=pandas_step.result, asset="out")


def _require_plugins() -> dict[str, Any]:
    found = discover_dataframe_plugins()
    missing = [name for name in ("polars", "pandas") if name not in found]
    if missing:
        raise SystemExit(
            "Missing dataframe plugin(s): "
            + ", ".join(missing)
            + ". Install with: uv sync --group dataframes "
            "or pip install 'etlantic[dataframes]==0.21.0'"
        )
    return found


def run_example() -> tuple[PipelineRuntime, object, dict[str, Any]]:
    _require_plugins()
    profile = Profile(
        name="interchange-polars-pandas",
        dataframe_engine="polars",
        implementation_overrides={"pandas_step": "pandas"},
        portable_transform_policy="native",
    )
    runtime = PipelineRuntime()
    runtime.memory.seed(
        "rows",
        [
            Row(value=1, label="alpha"),
            Row(value=2, label="beta"),
        ],
    )
    context = PlanningContext.create(profile=profile, registry=runtime.registry)
    plan = plan_pipeline(CrossEnginePipeline, context=context)
    explained = explain_plan(plan)
    report = CrossEnginePipeline.run(
        profile=profile,
        runtime=runtime,
        context=context,
    )
    return runtime, report, explained


def _interchange_descriptor(explained: dict[str, Any]) -> dict[str, Any]:
    for boundary in explained.get("conversion_boundaries") or []:
        interchange = boundary.get("interchange")
        if (
            isinstance(interchange, dict)
            and boundary.get("producer_node") == "polars_step"
        ):
            return interchange
    raise SystemExit(
        "Plan did not record an etlantic.interchange/1 descriptor on the "
        "Polars→Pandas boundary"
    )


if __name__ == "__main__":
    runtime, report, explained = run_example()
    if report.status is not RunStatus.SUCCEEDED:
        raise SystemExit(f"Pipeline failed: {report.status}")

    descriptor = _interchange_descriptor(explained)
    if descriptor.get("schema") != SCHEMA:
        raise SystemExit(
            f"Unexpected interchange schema: {descriptor.get('schema')!r} "
            f"(expected {SCHEMA!r})"
        )

    rows = [
        row.model_dump() if hasattr(row, "model_dump") else dict(row)
        for row in (runtime.memory.get("out") or [])
    ]
    print("Gate A interchange demo: SUCCESS")
    print(f"  schema={descriptor['schema']}")
    print(f"  mechanism={descriptor.get('mechanism')}")
    print(
        f"  producer={descriptor.get('producer_engine')} → "
        f"consumer={descriptor.get('consumer_engine')}"
    )
    print(f"  copy_eligibility={descriptor.get('copy_eligibility')}")
    print(f"  rows={rows}")
    print(report.to_text())
