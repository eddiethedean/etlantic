# Performance envelope

> **Status: Available in ETLantic 0.34.0.** Coordination microbenchmarks only—
> not warehouse throughput or SLA claims.

## Residual evaluation lead

| Topic | 0.34 |
|---|---|
| Maturity | Beta |
| Support | Community; **no SLA** |
| Scale claim | Measured **framework overhead** envelopes only |
| Engine sizing | Adopter-owned (measure Polars/Pandas/SQL/Spark yourself) |
| Multi-tenant / HA | Not included in 0.34; multi-tenancy is [planned first-class](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md), HA claims remain separately gated |

## What ETLantic claims

ETLantic publishes measured p95 envelopes for modeling, validation, planning,
plugin discovery, and interchange reconciliation. CI fails when those budgets
regress. See [Performance guidance](../11_DEVELOPMENT/PERFORMANCE.md) and
[`benchmarks/baselines/core.json`](https://github.com/eddiethedean/etlantic/blob/main/benchmarks/baselines/core.json).

## What ETLantic does not claim

- Rows/second or warehouse sizing for Polars, Pandas, SQL, or Spark
- End-to-end SLA, capacity, or noisy-neighbor guarantees
- That coordination p95 predicts production pipeline wall time

## How to measure for your pilot

1. Run `uv run python scripts/check_benchmarks.py` from a checkout (optional).
2. Measure your own graph on the chosen engine with representative data.
3. Include failure, cancellation, and interchange paths from the resilience
   work (0.23+)—not only happy-path throughput.
4. Record accepted residual risks in your deployment review
   ([Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md)).

## Related

- [Performance guidance](../11_DEVELOPMENT/PERFORMANCE.md)
- [Performance baselines](../11_DEVELOPMENT/PERFORMANCE_RESULTS.md)
- [Capabilities](CAPABILITIES.md)
- [Evaluator brief](EVALUATOR.md)
