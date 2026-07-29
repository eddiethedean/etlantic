"""Production-shaped pilot pipeline (local + optional Polars).

Clone companion: ``uv run python -m examples.sample_pilot.run_pilot``.
PyPI-only users: follow docs/09_EXAMPLES/PRODUCTION_SAMPLE.md instead.
"""

from __future__ import annotations

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation


class Row(Data):
    id: int
    name: str


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("local")
def identity_local(rows: list[Row]) -> list[Row]:
    return list(rows)


@Identity.implementation("polars")
def identity_polars(rows):
    import polars as pl

    if hasattr(rows, "with_columns"):
        return rows
    return pl.DataFrame(
        [row.model_dump() if hasattr(row, "model_dump") else row for row in rows]
    )


class PilotPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")
