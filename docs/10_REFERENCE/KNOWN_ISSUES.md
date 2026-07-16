# Known Limitations

- The project is alpha and does not promise 1.0 API stability.
- Local execution is in-process; Pipelantic is not a distributed scheduler.
- Spark, Airflow, and other non-SQL distributed backends are not included in
  0.6.
- SQL plugins do not treat untrusted raw SQL as safe; use the typed expression
  model and dialect identifier/parameter APIs.
- `MERGE` / upsert requires PostgreSQL (or another dialect that advertises
  merge) and explicit keys; unsupported merge requests fail closed at planning.
- SQLite via `PIPELANTIC_SQL_URL` is demo-only; it is not the SQL conformance
  reference (PostgreSQL via `pipelantic-sql` is).
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
  status before copying code.
- Process-local report history is not a durable report database.
- In-memory storage is intended for local development and tests.
- Generated plans should be regenerated after incompatible schema changes
  rather than edited by hand.

Release-specific fixes and changes are recorded in the
[changelog](https://github.com/eddiethedean/pipelantic/blob/main/CHANGELOG.md).
