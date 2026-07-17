# Compatibility Matrix

This table describes the declared compatibility of ETLantic 0.10.0.

| Surface | Supported range or version |
|---|---|
| Python | 3.11, 3.12, 3.13 |
| Pydantic | `>=2.12,<3` |
| ContractModel | `>=0.1.2` |
| DTCS toolkit | `>=0.11,<1` |
| DPCS toolkit | `>=0.13,<1` |
| Pipeline plan schema | `etlantic.plan/1` |
| Dataframe protocol | `etlantic.dataframe/1` |
| SQL protocol | `etlantic.sql/1` |
| Polars plugin | `etlantic-polars==0.10.0` |
| Pandas plugin | `etlantic-pandas==0.10.0` |
| SQL plugin | `etlantic-sql==0.10.0` |
| PySpark plugin | `etlantic-pyspark==0.10.0` |
| Airflow plugin | `etlantic-airflow==0.10.0` |
| Keyring provider | `etlantic-keyring==0.10.0` |
| SQLModel bridge | `etlantic-sqlmodel==0.10.0` |
| SparkForge adapter | `etlantic-sparkforge==0.10.0` |
| Orchestration protocol | `etlantic.orchestration/1` |
| DTCS Transformation Plan protocol | Not shipped; proposed `dtcs.transform-plan/1` for 0.11+ |
| Portable authoring profile | Not shipped; proposed `etlantic.transform/1` |
| Portable compiler protocol | Not shipped; proposed `etlantic.transform-compiler/1` for 0.12+ |
| Package stability | Alpha |
| Plugin SDK stability | Protocol stable within 0.8; third-party SDK still evolving |

The package metadata in `pyproject.toml` is authoritative for dependency
ranges. During the 0.x series, public APIs and persistent formats may change.
Breaking changes must be called out in the changelog with an upgrade path.

Portable compiler compatibility will be tracked independently across core,
Pipeline Plan schema, DTCS plan/package version, ETLantic authoring profile,
compiler protocol/package, and advertised operation/function versions.
