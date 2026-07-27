# Exit Gate 0.23 — Runtime Resilience and Performance Budgets

| Deliverable | Status |
|---|---|
| Committed benchmark baselines + CI regression gate | Done |
| Interchange planned vs observed reconciliation | Done |
| Public `etlantic.testing.faults` failure injection | Done |
| Cancellation/timeout terminal report semantics | Done |
| Publication vs report persistence gap detection (`PMEXEC410`) | Done |
| SafeIoPolicy-unified durable stores + concurrency tests | Done |
| Write-mode retry safety matrix | Done |
| Real PySpark CI job (gated) | Done |
| Airflow import version matrix | Done |
| Docs: What's New / Migration / this exit gate | Done |
| Core + plugins bumped to 0.23.0 | Done |

## Acceptance checklist

- [x] Stable microbenchmarks have committed baselines; CI gate enforced (`scripts/check_benchmarks.py`)
- [x] Published scale limits documented (modeling/discovery/interchange envelopes — not production throughput claims)
- [x] Interchange planned vs observed reconciliation tested (`tests/interchange/tabular/test_evidence_reconciliation.py`)
- [x] Fault injection covers listed boundaries with deterministic tests (`tests/resilience/test_fault_injection.py`)
- [x] Cancellation/timeout → one terminal report, bounded cleanup (`tests/resilience/test_cancellation.py`, `test_timeout.py`)
- [x] Publication/report persistence gap detected (`PMEXEC410`, fault-injection tests)
- [x] Concurrent report + schema-history writers cannot corrupt stores (`tests/resilience/test_store_concurrency.py`)
- [x] Write-mode retry safety matrix passes for local and file paths (`tests/resilience/test_write_semantics_matrix.py`)
- [x] Real PySpark CI job (`real-pyspark` in `.github/workflows/checks.yml`)
- [x] Airflow import matrix green (`airflow-import` job; `airflow-runtime` dependency group)

## Residual / follow-ups (0.24+)

- **0.24** Programmatic Authoring and Lossless JSON (`PipelineDefinition`,
  `etlantic.pipeline/1`, functional builders, CLI JSON targets, visual-builder
  catalog/edit contract, and FastAPI/OpenAPI reference adapter)
- **0.25** Compatibility burn-in first slice; **0.26** second slice (dual-minor proof, freeze closure, first-wave removals); **0.27–0.98** continued burn-in
- Multi-worker control plane / distributed scheduler
- Storage / Resource / Observability protocol catalogs
- Declaring unrestricted multi-tenant enterprise production
- Full pyright fail-suite CI for `tests/typing/fail`
