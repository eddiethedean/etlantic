# Performance Guidance

> **Status: Available in ETLantic 0.18.0 framing.** ETLantic publishes **no**
> capacity, throughput, or latency claims for production sizing.

Recorded smoke baselines (historical, ETLantic **0.10.0**) prove only that a
small harness completed in one environment. They are not production evidence.
See [Performance Baselines](PERFORMANCE_RESULTS.md).

## Run the local harness

```bash
uv sync --group dataframes
uv run python benchmarks/dataframe_scale.py polars
uv run python benchmarks/dataframe_scale.py pandas
```

Record commit, Python and dependency versions, hardware, OS, dataset shape,
warm-ups, samples, median, p95, and raw results. Do not compare unlike
environments as controlled benchmarks.

## Measure your workload

Benchmark representative graphs, data shapes, I/O, concurrency, and failure
paths on the engines you will deploy. Plans are data-only coordination
artifacts: construction does not read source rows or execute transformations.
Execution cost belongs primarily to selected backends.

Separate validation/planning overhead from backend execution and I/O. See
[Benchmark Design](BENCHMARKS.md).

## Evaluator note

Until representative 0.18+ baselines are published, treat performance as
**adopter-measured**. Do not infer warehouse throughput from framework smoke
timings.
