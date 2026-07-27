# What's New in 0.23

ETLantic **0.23.0** ships **Runtime Resilience and Performance Budgets**:
measured microbenchmark envelopes with CI gates, deterministic failure injection,
hardened durable persistence, terminal-state proofs for cancellation/timeout,
interchange evidence reconciliation, and expanded backend CI (real PySpark +
Airflow import matrix).

## Performance budgets

Committed baselines under `benchmarks/baselines/` (`etlantic.benchmark_baseline/1`)
cover modeling, discovery, and interchange microbenchmarks. CI runs
`scripts/check_benchmarks.py`; refresh with reviewed
`ETLANTIC_BENCHMARK_UPDATE=1` when intentional.

```bash
uv run python scripts/check_benchmarks.py
ETLANTIC_BENCHMARK_UPDATE=1 uv run python scripts/check_benchmarks.py
```

See [Benchmarks](../11_DEVELOPMENT/BENCHMARKS.md) and
[Performance](../11_DEVELOPMENT/PERFORMANCE.md).

## Failure injection (test/dev only)

Public API: `etlantic.testing.faults` (`with_faults`, `FaultSpec`, `FaultBoundary`).
Active only when the registry is entered or `ETLANTIC_FAULT_INJECTION=1` is set.
Production profiles ignore the registry by default.

## Interchange evidence

Plans emit stable `evidence_refs` on cross-engine boundaries. Runtime records
observations in step metrics (`interchange_evidence` extra). Reconcile with:

```python
from etlantic.interchange import reconcile_interchange_evidence
```

## Terminal semantics

Cancellation and timeout paths persist exactly one terminal report. When data
publication succeeds but report persistence fails, runs fail closed with
`PMEXEC410`.

## Backend CI

- **Real PySpark:** `SPARKLESS_TEST_MODE=pyspark` job for `@pytest.mark.real_pyspark`
- **Airflow import matrix:** compile fixture DAG and `load_compiled_pipeline()` for
  Airflow 2.8.x, 2.9.x, and 2.10.x (`airflow-runtime` dependency group)

## Migration

See [Migration 0.22 → 0.23](../11_DEVELOPMENT/MIGRATION_0_22_TO_0_23.md) and
[Exit Gate 0.23](../11_DEVELOPMENT/EXIT_GATE_0_23.md).
