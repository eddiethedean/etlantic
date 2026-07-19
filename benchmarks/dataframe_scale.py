"""Lightweight dataframe benchmark harness (correctness + timing)."""

from __future__ import annotations

import time
from dataclasses import dataclass

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
from etlantic.registry import PlanningContext


class Row(Data):
    id: int
    value: float


class Scale(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Scale.implementation("polars")
def scale_polars(rows):
    import polars as pl

    frame = rows if hasattr(rows, "with_columns") else pl.DataFrame(rows)
    return frame.with_columns((pl.col("value") * 2).alias("value"))


@Scale.implementation("pandas")
def scale_pandas(rows):
    import pandas as pd

    frame = rows if hasattr(rows, "assign") else pd.DataFrame(rows)
    out = frame.copy()
    out["value"] = out["value"] * 2
    return out


class BenchPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    scaled = Scale.step(rows=raw)
    out: Load[Row] = Load(input=scaled.result, asset="out")


@dataclass
class BenchResult:
    engine: str
    rows: int
    seconds: float
    status: str


def run_benchmark(engine: str, *, rows: int = 50_000, warmups: int = 1) -> BenchResult:
    """Run a single-engine scale pipeline and return timing."""
    runtime = PipelineRuntime()
    data = [Row(id=i, value=float(i)) for i in range(rows)]
    profile = Profile(name=f"bench-{engine}", dataframe_engine=engine)
    context = PlanningContext.create(profile=profile, registry=runtime.registry)

    def _once() -> str:
        runtime.memory.seed("rows", data)
        report = BenchPipeline.run(profile=profile, runtime=runtime, context=context)
        return report.status.value

    for _ in range(warmups):
        _once()

    started = time.perf_counter()
    status = _once()
    elapsed = time.perf_counter() - started
    return BenchResult(engine=engine, rows=rows, seconds=elapsed, status=status)


if __name__ == "__main__":
    import sys

    engine = sys.argv[1] if len(sys.argv) > 1 else "polars"
    result = run_benchmark(engine)
    print(
        f"engine={result.engine} rows={result.rows} "
        f"seconds={result.seconds:.4f} status={result.status}"
    )
