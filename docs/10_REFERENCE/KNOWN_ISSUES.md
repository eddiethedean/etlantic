# Known Limitations

- The project is alpha and does not promise 1.0 API stability.
- Portable `@Transformation.portable` definitions and
  `etlantic.transform/1` authoring are available since 0.11. **0.13** adds
  Polars and PySpark compilers for `portable-relational/1` (joins, aggregates,
  unions, sort/dedupe/limit). Richer profiles (windows, complex values,
  Pandas/SQL compilers) remain native-or-later until 0.14–0.15.
- The planned PySpark-inspired syntax will intentionally support a closed
  subset; actions, arbitrary Python tracing, raw SQL expressions, and silent
  UDF fallback are excluded.
- Advanced DTCS 3.0 families (string/regex, statistics, reshape, etc.) are
  published as independently claimable profiles. ETLantic **authors** those
  facade methods in 0.11 for IR emission, but plugins must not **execute** them
  via portable compilation until a compiler claims the matching profile.
  Raw `F.expr()` SQL text remains permanently non-portable.
- Local execution is in-process; ETLantic is not a distributed scheduler.
- Spark batch execution is available via `etlantic-pyspark` (0.7+). Managed
  cloud providers (Databricks/EMR/Connect) are not.
- Airflow DAG compilation is available via `etlantic-airflow` (0.8+).
  Dagster and Prefect compilers are not.
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
  `etlantic==0.13.0` (or the version you evaluated) in production installs.

Release-specific fixes and changes are recorded in the
[changelog](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md).
