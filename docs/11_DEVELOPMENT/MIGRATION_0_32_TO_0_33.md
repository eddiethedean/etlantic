# Migration 0.32 → 0.33

> **Status: Available in ETLantic 0.33.0.** SQLAlchemy / relational differential
> parity (M5); **no wire-schema reset** (`etlantic.plan/1` / `pipeline/1`
> unchanged).

## Summary

| Area | Change |
|---|---|
| Wire schemas | Still `pipeline/1`, `plan/1`, … |
| Package pin | `etlantic==0.33.0`; plugins / `medallantic==0.33.0` |
| SQL plugin | Tier A/B dialect matrix; PG `sql_merge`; lazy transform claim |
| Diagnostics | `MDL132` for required Moltres rules; `PMSQ350+` live SQL bridge |
| Medallantic | Live `from_sql_pipeline_builder`; Moltres rules fail closed |
| Testing | `run_sql_builder_differential_suite` |

## Upgrade steps

1. Pin core and matching plugins:

   ```bash
   python -m pip install --upgrade 'etlantic==0.33.0'
   python -m pip install --upgrade 'medallantic==0.33.0'
   ```

2. If you require SQL `MERGE` / upsert, use PostgreSQL and advertise
   `sql_merge` (or expect plan fail-closed on SQLite).

3. Prefer `medallantic.migrate.sql.from_sql_pipeline_builder(...)` for live SQL
   builders; keep frozen IR fixtures for CI without Moltres /
   SqlPipelineBuilder installed.

4. Moltres / SQLAlchemy-native rules are **not** portable
   `etlantic.quality/1` — they require `quality.moltres_expr` and fail with
   `MDL132` until an evaluator exists.

5. Tier B dialects (MySQL, MSSQL, …) are detected but the reference plugin
   refuses execution; use a dedicated dialect plugin or stay on Tier A.

## Breaking / behavior notes

- Default SQLite plugin still does **not** advertise `sql_merge` (unchanged
  fail-closed for merge-required profiles).
- PostgreSQL now **does** advertise `sql_merge` when the URL is PostgreSQL.
- `SqlTransformCompiler` advertises `lazy=True` (relational handles). SQL
  plugin `PluginCapabilities.lazy` remains false (dataframe implication).

## See also

- [What's New 0.33](../01_GETTING_STARTED/WHATS_NEW_0_33.md)
- [Exit gate 0.33](EXIT_GATE_0_33.md)
- [SQL dialect guide](../07_PLUGIN_SDK/SQL_DIALECT.md)
