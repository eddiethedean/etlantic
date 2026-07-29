# What's New in ETLantic 0.33

> **Status: Available in ETLantic 0.33.0.** SQLAlchemy and Relational
> Differential Parity (Medallantic **M5**): dialect tiers, live
> `SqlPipelineBuilder` bridge, Moltres rules, and SQLite/PostgreSQL
> differential fixtures.

!!! tip "Local / Polars / Pandas adopters"
    If you only use core local JSON pipelines or Polars/Pandas, you can skip
    most of this page. Pin `etlantic==0.33.0` (and matching plugins) and follow
    [Quickstart](QUICKSTART.md) → [Polars tutorial](../06_EXECUTION/POLARS_TUTORIAL.md).
    The highlights below matter when you use SQL engines, Medallantic SQL
    migration, or dialect capability claims.

## Highlights

- **Dialect tiers** in `etlantic-sql`: Tier A (`sqlite`, `postgresql`) live in
  CI; Tier B dialects are detected and fail closed
- **PostgreSQL `sql_merge`** via `INSERT … ON CONFLICT`; SQLite stays
  `sql_merge=False`
- Lazy relational reuse: SQL transform compiler advertises `lazy=True`;
  planner emits `sql_fusion` / transaction-scope evidence (plugin
  `PluginCapabilities.lazy` stays false — that flag implies dataframe)
- Model-driven table create + primary-key validation
  (`create_table_from_model`, `validate_primary_keys`, sqlmodel helpers)
- Async execution path when the SQLAlchemy URL uses an async driver
- Medallantic **live `SqlPipelineBuilder` bridge**
  (`medallantic.migrate.sql.from_sql_pipeline_builder`)
- Non-portable **Moltres / SQLAlchemy rules** (`quality.moltres_expr`, `MDL132`)
- Differential suite: `etlantic.testing.run_sql_builder_differential_suite`
- [Migration 0.32 → 0.33](../11_DEVELOPMENT/MIGRATION_0_32_TO_0_33.md) and
  [Exit gate 0.33](../11_DEVELOPMENT/EXIT_GATE_0_33.md)

## Not in 0.33

- Trend / quality analytics providers (**0.34 / M6**)
- Automated SparkForge project inventory (**0.35 / M7**)
- Live MySQL / other Tier B dialect suites

## Upgrade

Pin core and plugins to the same minor:

```bash
python -m pip install --upgrade 'etlantic==0.33.0'
python -m pip install --upgrade 'medallantic==0.33.0'
```

Plugin authors: pin `etlantic>=0.33.0,<0.34`.
