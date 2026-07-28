# Performance Guidance

> **Status: ETLantic 0.30.0.** ETLantic publishes **measured microbenchmark
> envelopes** for modeling/planning/discovery coordination and **no** production
> throughput or warehouse sizing claims.

## 0.23 measured envelopes (coordination only)

| Scenario | Baseline p95 (s) | Notes |
|---|---|---|
| `modeling.plan_small` | 0.025 | Sample pipeline plan |
| `modeling.validate_small` | 0.015 | Sample pipeline validate |
| `discovery.enabled` | 0.05 | Coordinator with runtime groups |
| `interchange.reconcile` | 0.00005 | Descriptor vs evidence compare |

Source: `benchmarks/baselines/core.json`. CI enforces via
`scripts/check_benchmarks.py`. These limits bound **framework overhead**, not
engine execution.

## Run harnesses locally

```bash
uv run python scripts/check_benchmarks.py
uv sync --group dataframes
uv run python benchmarks/dataframe_scale.py polars
uv run python benchmarks/dataframe_scale.py pandas --json
```

See [Benchmark Design](BENCHMARKS.md) and [Performance Baselines](PERFORMANCE_RESULTS.md).

## Evaluator note

Do not infer warehouse throughput from framework microbenchmarks. Measure your
graphs, data shapes, I/O, concurrency, and failure paths on deployed engines.
