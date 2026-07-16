# Known Limitations

- The project is alpha and does not promise 1.0 API stability.
- Local execution is in-process; Pipelantic is not a distributed scheduler.
- SQL, Spark, Airflow, and other non-dataframe backends are not included in
  0.5.
- Polars LazyFrames are collected only at plan-declared boundaries; durable
  JSON workspace materialization requires collection to records.
- Pandas does not support lazy execution; requiring `lazy` fails at planning.
- Arrow interchange requires an optional PyArrow install; without it,
  cross-engine transfers use a documented copy fallback.
- Not every Polars/Pandas dtype maps losslessly; ambiguous or unsupported
  mappings produce structured diagnostics.
- Many design pages still describe intended 1.0 behavior. Check the page
  status before copying code.
- Process-local report history is not a durable report database.
- In-memory storage is intended for local development and tests.
- Generated plans should be regenerated after incompatible schema changes
  rather than edited by hand.

Release-specific fixes and changes are recorded in the
[changelog](https://github.com/eddiethedean/pipelantic/blob/main/CHANGELOG.md).
