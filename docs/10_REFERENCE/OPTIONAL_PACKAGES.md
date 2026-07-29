# Optional Packages

> **Status: Available in ETLantic 0.34.0.** Core `etlantic` does not install
> engines. Install only the plugins you need, pinned to the same minor line.

## Install pins

Prefer exact pins for a controlled pilot:

```bash
pip install 'etlantic==0.34.0'
pip install 'etlantic-polars==0.34.0'
pip install 'etlantic-pandas==0.34.0'
pip install 'etlantic-sql==0.34.0'
pip install 'etlantic-pyspark==0.34.0'
pip install 'etlantic-airflow==0.34.0'
pip install 'etlantic-prefect==0.34.0'
pip install 'etlantic-keyring==0.34.0'
pip install 'etlantic-sqlmodel==0.34.0'
pip install 'medallantic==0.34.0'
# optional compatibility redirect (deprecated):
pip install 'etlantic-sparkforge==0.34.0'
```

Official first-party plugins declare `etlantic>=0.34.0,<0.35`.
Keep core and plugins on the same minor (pin all to `0.34.0` for pilots).
Cross-minor mixes are unsupported and commonly fail plugin discovery.

Experimental (not recommended): `pip install 'etlantic[datafusion]==0.34.0'`
or `etlantic-datafusion==0.34.0` — Gate B stub; no graduated claims.

Optional reference adapter: `pip install 'etlantic-fastapi==0.34.0'` or
`etlantic[fastapi]==0.34.0` — thin authoring/service HTTP adapter (shipped since
0.24; not the
[planned first-class control plane](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)).

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
| [`medallantic`](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/README.md) | `medallantic` | **Facade** — medallion vocabulary and SparkForge migration adapter |
| [`etlantic-sparkforge`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-sparkforge/README.md) | `etlantic_sparkforge` | **Redirect** (deprecated) — re-exports `medallantic` |
| [`etlantic-fastapi`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-fastapi/README.md) | `etlantic_fastapi` | Thin FastAPI authoring/service reference adapter (shipped since 0.24; pin `==0.34.0`) |
| [`etlantic-datafusion`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-datafusion/README.md) | `etlantic_datafusion` | **Experimental** DataFusion stub (Gate B; not graduated) |

MkDocs API generation scans core `src/` (plus Medallantic where linked). The
docs site **API Reference** is therefore **core-first**, not a complete catalog
of every optional-package constructor. For plugin factories, registration,
protocol versions, and failure modes, use the linked package README and the
corresponding engine tutorial.

## Related

- [Compatibility](COMPATIBILITY.md)
- [Portable compiler matrix](PORTABLE_COMPILER_MATRIX.md)
- [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
- [Third-party compiler tutorial](../07_PLUGIN_SDK/THIRD_PARTY_COMPILER_TUTORIAL.md)
