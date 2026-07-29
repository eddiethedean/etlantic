# Known Limitations

- ETLantic **0.34.x** is a **Beta** (PyPI) release suitable for documented single-tenant
  reference deployments, but 0.x releases may still introduce breaking API
  changes between minor versions until the 0.38 stable-foundation freeze.
- Portable `@Transformation.portable` definitions and
  `etlantic.transform/1` authoring are available since 0.11. **0.13** shipped
  Polars and PySpark compilers for `portable-relational/1`; **0.14** shipped
  the eager Pandas compiler; **0.15** shipped Safe SQL portable lowering for
  that baseline. **0.17** graduates Wave 1/2 families on Polars and PySpark:
  `portable-string-advanced/1`, `portable-conversion/1`,
  `portable-statistics/1`, `portable-window/1`, `portable-complex-values/1`,
  `portable-complex-types/1`, and `portable-reshape/1`. Pandas and SQL remain
  baseline-only (kernel + relational `/1`).
- Explicit window frames (`rowsBetween` / `rangeBetween`) fail closed in 0.17;
  `first_value` / `last_value` use ordered partition semantics until frames
  land. Continuation families (`portable-window/2`, temporal-iana,
  nondeterministic, relational-extended) remain unclaimed.
- Distinct `missing` / `invalid` three-state literals fail closed unless a
  compiler advertises `semantic_mode:three_state_distinct` (not claimed in
  0.17). Polars does not claim `dtcs:map` (use `dtcs:object`); PySpark does.
- The shipped PySpark-inspired portable syntax intentionally supports a closed
  subset; actions, arbitrary Python tracing, raw SQL expressions, and silent
  UDF fallback are excluded.
- Advanced [DTCS](../04_TRANSFORMATIONS/DTCS.md) 3.0 families are independently claimable profiles. Facades may
  emit IR for unclaimed families; first-party compilers reject them at analyze
  until claimed.
- Local execution is in-process; ETLantic is not a distributed scheduler.
- Spark batch execution is available via `etlantic-pyspark` (0.7+). Managed
  cloud providers (Databricks/EMR/Connect) are not in 0.34. Reference proof is
  planned for 0.48 and supported provider packs for 0.52.
- Airflow DAG compilation is available via `etlantic-airflow` (0.8+).
  Dagster and expanded Prefect compilers are planned for 0.50, not shipped.
  Optional Prefect 3.x local scheduling ships via `etlantic-prefect` (0.16+)
  as an `ExecutionScheduler` (not a DAG compiler).
- Structured Streaming APIs are experimental in 0.7+.
- SQL plugins do not treat untrusted raw SQL as safe; use the typed expression
  model and dialect identifier/parameter APIs.
- `MERGE` / upsert is implemented for **PostgreSQL** in the SQL reference plugin
  (`sql_merge=True`). SQLite and other dialects remain fail-closed when
  `sql_merge` is required.
- SQLite and PostgreSQL are Tier A SQL dialects in 0.34. SQLite does not
  advertise merge; PostgreSQL does. An in-memory SQLite run is useful for
  local verification but is not evidence of PostgreSQL-specific behavior.
- Cross-database joins and distributed transactions are not supported.
- Polars LazyFrames are collected only at plan-declared boundaries; durable
  JSON workspace materialization requires collection to records first.
- Durable workspace storage rejects native frames/LazyFrames (fail closed);
  there is no durable LazyFrame workspace format yet.
- Pandas does not support lazy execution; requiring `lazy` fails at planning.
- Arrow interchange requires an optional PyArrow install; without it,
  cross-engine transfers use a documented copy fallback.
- Not every Polars/Pandas dtype maps losslessly; ambiguous or unsupported
  mappings produce structured diagnostics.
- Cancellation and thread-safety capability flags are not fully enforced by
  the reference plugins.
- Many design pages describe intended later-0.x behavior. Check the page
  status and [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) before
  copying code.
- Process-local report history is not a durable report database.
- In-memory storage is intended for local development and tests.
- Generated plans should be regenerated after incompatible schema changes
  rather than edited by hand.
- Docs on `main` may briefly lead a published tag; pin
  `etlantic==0.34.0` (or the version you evaluated) in production installs.

Release-specific fixes and changes are recorded in the
[changelog](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md).
