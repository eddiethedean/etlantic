# Compatibility Matrix

This table describes the declared compatibility of Pipelantic 0.6.0.

| Surface | Supported range or version |
|---|---|
| Python | 3.11, 3.12, 3.13 |
| Pydantic | `>=2.12,<3` |
| ContractModel | `>=0.1.2` |
| DTCS toolkit | `>=0.11,<1` |
| DPCS toolkit | `>=0.13,<1` |
| Pipeline plan schema | `pipelantic.plan/1` |
| Dataframe protocol | `pipelantic.dataframe/1` |
| SQL protocol | `pipelantic.sql/1` |
| Polars plugin | `pipelantic-polars==0.6.0` |
| Pandas plugin | `pipelantic-pandas==0.6.0` |
| SQL plugin | `pipelantic-sql==0.6.0` |
| Package stability | Alpha |
| Plugin SDK stability | Protocol stable within 0.6; third-party SDK still evolving |

The package metadata in `pyproject.toml` is authoritative for dependency
ranges. During the 0.x series, public APIs and persistent formats may change.
Breaking changes must be called out in the changelog with an upgrade path.
