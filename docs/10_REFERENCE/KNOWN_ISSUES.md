# Known Limitations

- ETLantic **0.21.x** is production/stable for documented single-tenant
  reference deployments, but 0.x releases may still introduce breaking API
  changes between minor versions until 1.0.
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
- The planned PySpark-inspired syntax will intentionally support a closed
  subset; actions, arbitrary Python tracing, raw SQL expressions, and silent
  UDF fallback are excluded.
- Advanced DTCS 3.0 families are independently claimable profiles. Facades may
  emit IR for unclaimed families; first-party compilers reject them at analyze
  until claimed.
- Local execution is in-process; ETLantic is not a distributed scheduler.
- Spark batch execution is available via `etlantic-pyspark` (0.7+). Managed
  cloud providers (Databricks/EMR/Connect) are not.
- Airflow DAG compilation is available via `etlantic-airflow` (0.8+).
  Dagster compilers are not shipped. Optional Prefect 3.x local scheduling
  ships via `etlantic-prefect` (0.16+) as an `ExecutionScheduler` (not a DAG
  compiler).
- Structured Streaming APIs are experimental in 0.7+.
- SQL plugins do not treat untrusted raw SQL as safe; use the typed expression
  model and dialect identifier/parameter APIs.
- `MERGE` / upsert is not implemented in the SQL reference plugin; requiring
  `sql_merge` fails closed at planning. Do not rely on SQL merge until a later
  release advertises and implements it.
- SQLite via `ETLANTIC_SQL_URL` is demo-only; it is not the SQL conformance
  reference (PostgreSQL via `etlantic-sql` is).
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
- Many design pages still describe intended 1.0 behavior. Check the page
  status and [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) before
  copying code.
- Process-local report history is not a durable report database.
- In-memory storage is intended for local development and tests.
- Generated plans should be regenerated after incompatible schema changes
  rather than edited by hand.
- Docs on `main` may briefly lead a published tag; pin
  `etlantic==0.21.0` (or the version you evaluated) in production installs.

Release-specific fixes and changes are recorded in the
[changelog](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md).
