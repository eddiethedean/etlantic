# Optional Packages

> **Status: Available in ETLantic 0.18.0.** Core `etlantic` does not install
> engines. Install only the plugins you need, pinned to the same minor line.

## Install pins

Prefer exact pins for a controlled pilot:

```bash
pip install 'etlantic==0.18.0'
pip install 'etlantic-polars==0.18.0'
pip install 'etlantic-pandas==0.18.0'
pip install 'etlantic-sql==0.18.0'
pip install 'etlantic-pyspark==0.18.0'
pip install 'etlantic-airflow==0.18.0'
pip install 'etlantic-prefect==0.18.0'
pip install 'etlantic-keyring==0.18.0'
pip install 'etlantic-sqlmodel==0.18.0'
pip install 'etlantic-sparkforge==0.18.0'
```

Official first-party plugins declare `etlantic>=0.18.0,<0.19`.
Keep core and plugins on the same minor (for 0.18.x pilots, pin all to
`0.18.0`). Cross-minor mixes are unsupported and commonly fail plugin
discovery.

## Package API index

| Package guide | Public entry | Role |
|---|---|---|
| [`etlantic-polars`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-polars/README.md) | `etlantic_polars` | Polars dataframe engine + portable compiler |
| [`etlantic-pandas`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-pandas/README.md) | `etlantic_pandas` | Pandas dataframe engine + eager portable compiler |
| [`etlantic-sql`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-sql/README.md) | `etlantic_sql` | Native SQL engine + portable SQL lowering |
| [`etlantic-pyspark`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-pyspark/README.md) | `etlantic_pyspark` | PySpark engine + portable compiler |
| [`etlantic-airflow`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-airflow/README.md) | `etlantic_airflow` | Airflow DAG compiler (`etlantic compile --target airflow`) |
| [`etlantic-prefect`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-prefect/README.md) | `etlantic_prefect` | Prefect direct-execution scheduler (`Profile(orchestrator="prefect")`) |
| [`etlantic-keyring`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-keyring/README.md) | `etlantic_keyring` | OS keyring secret provider |
| [`etlantic-sqlmodel`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-sqlmodel/README.md) | `etlantic_sqlmodel` | SQLModel ↔ contract bridge |
| [`etlantic-sparkforge`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-sparkforge/README.md) | `etlantic_sparkforge` | SparkForge adapter (medallion stays here, not in core) |

MkDocs API generation scans core `src/` only. For optional-package constructors,
registration, protocol versions, and failure modes, use the linked package
README and the corresponding engine tutorial.

## Related

- [Compatibility](COMPATIBILITY.md)
- [Portable compiler matrix](PORTABLE_COMPILER_MATRIX.md)
- [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
- [Third-party compiler tutorial](../07_PLUGIN_SDK/THIRD_PARTY_COMPILER_TUTORIAL.md)
