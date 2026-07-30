# Performance Baselines

> **Historical note:** The published smoke numbers in the harness appendix were
> first recorded on ETLantic **0.10.0** and restamped for the **0.34** Beta
> docs train. They remain a reproducibility check for the harness, not current
> capacity claims. Re-run the harness on your environment before using any
> timing in diligence.

ETLantic does not publish production-grade performance claims. This page
defines the evidence required before such claims are made.

## 0.23 coordination envelopes (current)

Microbenchmark baselines in `benchmarks/baselines/core.json` (schema
`etlantic.benchmark_baseline/1`) bound modeling, discovery, and interchange
reconciliation overhead. CI enforces them via `scripts/check_benchmarks.py`.

| Scenario | Baseline p95 | Tolerance |
|---|---:|---:|
| modeling.plan_small | 0.025 s | 15% |
| modeling.validate_small | 0.015 s | 15% |
| discovery.enabled | 0.05 s | 20% |
| interchange.reconcile | 0.00005 s | 50% |

These are **not** dataframe engine throughput claims. Re-run locally before
using timings in diligence.

## Current evidence

The repository includes `benchmarks/dataframe_scale.py`, a lightweight timing
and correctness harness for Polars and Pandas. Its results are environment
dependent and are not a substitute for validation/planning scale benchmarks.

```bash
uv sync --group dataframes
uv run python benchmarks/dataframe_scale.py polars
uv run python benchmarks/dataframe_scale.py pandas
```

## Reproducible result format

Every published result must include commit, Python and dependency versions,
CPU, memory, operating system, dataset shape, warm-up count, sample count,
median, p95, and raw result artifact. Report ETLantic overhead separately from
backend execution and I/O.

## Published smoke baseline (historical — ETLantic 0.10.0)

The following numbers are a reproducibility smoke test, not a throughput claim.
They are one harness invocation per engine over 50,000 rows; no distribution or
p95 is available yet.

| Commit | Environment | ETLantic | Backend | Rows | Elapsed | Status |
|---|---|---:|---|---:|---:|---|
| `838feba` | macOS 26.5.2, arm64, Python 3.11.14 | 0.10.0 | Polars 1.42.1 | 50,000 | 0.3332 s | succeeded |
| `838feba` | macOS 26.5.2, arm64, Python 3.11.14 | 0.10.0 | Pandas 2.3.3 | 50,000 | 0.3340 s | succeeded |

These results establish that the committed harness completed for both reference
dataframe plugins on the recorded environment. They do not establish equivalent
engine performance and must not be extrapolated to production data shapes.

## Adoption guidance

Until representative 0.18+ baselines are published, evaluators must benchmark
their own graph sizes, plugin discovery, plan generation, and run-report
overhead. Do not infer backend throughput from ETLantic's framework timings.

See [Benchmark design](BENCHMARKS.md) and [Performance guidance](PERFORMANCE.md).
