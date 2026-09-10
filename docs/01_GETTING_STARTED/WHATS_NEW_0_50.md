# What's New in ETLantic 0.50

> **Status: Available in ETLantic 0.50.1 (published Beta).**

ETLantic 0.50 freezes and technically qualifies the shared portable
transformation baseline across Local, Polars, Pandas, SQL (SQLite and
PostgreSQL), PySpark, DataFusion, and DuckDB. The guarantee covers the
manifested 12 actions, 30 functions, governed operators, normalized result
semantics, and each engine's declared pushdown boundaries.

## Upgrade impact

- Pin core and every first-party plugin to `0.50.1`; plugin requirements use
  `etlantic>=0.50.0,<0.51`.
- Replan stored 0.49 portable descriptors. Evidence-free or stale compiler
  support records fail runtime preflight before I/O.
- Aggregate capability booleans no longer establish eligibility. Every
  applicable required requirement needs positive requirement-level evidence.
- Native implementation bodies remain explicit escape hatches and are never a
  silent fallback for a rejected portable plan.

See [Migration 0.49 → 0.50](../11_DEVELOPMENT/evidence/portable_0_50/MIGRATION_0_49_TO_0_50.md)
and the [0.50 exit gate](../11_DEVELOPMENT/EXIT_GATE_0_50.md).

## Qualified matrix

| Engine | Qualified 0.50 baseline |
|---|---|
| Local | Dependency-free host execution |
| Polars | Eager and lazy dataframe execution |
| Pandas | Eager dataframe execution |
| SQL | SQLite and real PostgreSQL relation paths |
| PySpark | Real-JVM native logical plans |
| DataFusion | Native lazy logical plans; release classification remains Provisional (Alpha) |
| DuckDB | Native relation execution and required pushdown evidence |

0.50 does not claim a common advanced profile, adaptive execution, streaming,
remote or federated execution, identical physical plans, or unqualified
connector and sink pushdown.
