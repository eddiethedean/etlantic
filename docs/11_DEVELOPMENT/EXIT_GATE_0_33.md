# Exit Gate 0.33 — SQLAlchemy and Relational Differential Parity (M5)

> **Status: Shipped in ETLantic 0.33.0.** Medallantic M5 SQL / SqlPipelineBuilder
> differential parity lands in **0.33.0**.

| Deliverable | Status |
|---|---|
| Dialect Tier A (SQLite + PostgreSQL) + Tier B fail-closed | Done |
| PostgreSQL `sql_merge` (ON CONFLICT); SQLite fail-closed | Done |
| Lazy SQL→SQL / fusion evidence (`sql_fusion`, transaction scopes) | Done |
| Model-driven DDL + primary-key validation | Done |
| Async SQLAlchemy path (`async_execution` when async URL) | Done |
| Live `SqlPipelineBuilder` bridge (`from_sql_pipeline_builder`) | Done |
| Moltres / SA-native rules (`MDL132`, `quality.moltres_expr`) | Done |
| SQL builder differential suite + classifications | Done |
| Docs: What's New / Migration 0.32→0.33 / this exit gate | Done |
| Core + plugins + medallantic bumped to 0.33.0 | Done |

## Engine bar

- **SQLite + PostgreSQL (Tier A):** differential corpus and SQL plugin
  conformance green in CI.
- **Other dialects (Tier B):** detected and capability-gated; reference plugin
  refuses execution.
- **MERGE:** advertised and compiled for PostgreSQL only; SQLite remains
  fail-closed (`sql_merge=False`).
- **Core remains free of SQLAlchemy / Moltres dependencies.**

## Acceptance checklist

- [x] Every in-tree SQL-builder fixture classified equivalent /
  plugin_dependent / intentionally_rejected
- [x] Live bridge extracts secret-free IR (no passwords/tokens in metadata)
- [x] Native Moltres rules fail closed (`MDL132`)
- [x] `run_sql_builder_differential_suite` green
- [x] What's New / Migration / this exit gate pass docs gates

## Residual / follow-ons (0.34+)

- Operations / observability providers (**M6 / 0.34**)
- Automated migration inventory (**M7 / 0.35**)
- Multi-dialect live suites beyond SQLite/PostgreSQL

## See also

- [ROADMAP § 0.33](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#033--sqlalchemy-and-relational-differential-parity)
- [What's New 0.33](../01_GETTING_STARTED/WHATS_NEW_0_33.md)
- [Migration 0.32 → 0.33](MIGRATION_0_32_TO_0_33.md)
- [Exit gate 0.32](EXIT_GATE_0_32.md)
- [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md)
