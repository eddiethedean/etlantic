# Migration 0.22 → 0.23

## Version pins

Bump core and plugins together:

```bash
pip install 'etlantic==0.23.0' 'etlantic-polars==0.23.0'  # etc.
```

Plugins require `etlantic>=0.23.0,<0.24`.

## Benchmark baselines

If you maintain forked CI, optional gate:

```bash
uv run python scripts/check_benchmarks.py
```

Regressions fail unless `benchmarks/baselines/core.json` is updated in the same
PR with rationale (`ETLANTIC_BENCHMARK_UPDATE=1`).

## Fault injection

New public test helper: `etlantic.testing.faults`. It is **inactive** in normal
runs unless `ETLANTIC_FAULT_INJECTION=1` or an active `with_faults(...)` context.
Do not enable in production profiles.

## Interchange evidence

Cross-engine plan descriptors now include non-empty `evidence_refs`. Runtime
step metrics may include `interchange_evidence` in `DataframeMetrics.extras`.
Use `reconcile_interchange_evidence` when asserting Gate A interchange claims in
tests.

## Terminal reports

Orchestrator persistence tracks publication vs report writes. Failed report
persistence after successful publication surfaces `PMEXEC410` instead of silent
success.

## Airflow testing

Optional `airflow-runtime` uv group installs `apache-airflow` for import-matrix
CI. Core remains orchestration-compile friendly without a scheduler runtime.

## No breaking public API removals

0.23 is additive for stable surfaces. The 0.x compatibility aliases from 0.22
remain unchanged.
