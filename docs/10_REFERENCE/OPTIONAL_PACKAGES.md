# Optional Packages

> **Status: Available in ETLantic 0.43.0.** Core `etlantic` does not install
> engines. Install only the plugins you need, pinned to the same minor line.

!!! warning "Maturity vs PyPI classifiers"
    Official engine packages declare **Beta** PyPI classifiers that match the
    **ETLantic 0.40 Beta** pilot envelope (single-tenant, no SLA). Treat that
    envelope as authoritative for readiness claims. **CP1 ≠ production
    multi-tenant GA** (graduation remains **0.43**). See
    [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md).

## Install pins

Prefer exact pins for a controlled pilot:

```bash
pip install 'etlantic==0.43.0'
pip install 'etlantic-polars==0.43.0'
pip install 'etlantic-pandas==0.43.0'
pip install 'etlantic-sql==0.43.0'
pip install 'etlantic-pyspark==0.43.0'
pip install 'etlantic-airflow==0.43.0'
pip install 'etlantic-prefect==0.43.0'
pip install 'etlantic-keyring==0.43.0'
pip install 'etlantic-sqlmodel==0.43.0'
pip install 'medallantic==0.43.0'
# optional compatibility redirect (deprecated):
pip install 'etlantic-sparkforge==0.43.0'
# experimental connectors (fake/CI; Alpha — not Supported):
pip install 'etlantic-s3==0.43.0'
pip install 'etlantic-iceberg==0.43.0'
pip install 'etlantic-snowflake==0.43.0'
```

Official first-party plugins declare `etlantic>=0.43.0,<0.44`.
Keep core and plugins on the same minor (pin all to `0.43.0` for pilots).
Cross-minor mixes are unsupported and commonly fail plugin discovery.

Experimental (not recommended): `pip install 'etlantic[datafusion]==0.43.0'`
or `etlantic-datafusion==0.43.0` — Gate B stub; no graduated claims.

Optional FastAPI package: `pip install 'etlantic-fastapi==0.43.0'` or
`etlantic[fastapi]==0.43.0` — **dual surface**: CP1 (`ETLanticAPI` /
`include_router` / `create_app`) plus thin non-CP `create_reference_app`
(authoring demo since 0.24). CP1 is control-plane incubation, **not**
production multi-tenant GA
([plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md)).

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
| [`etlantic-s3`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-s3/README.md) | `etlantic_s3` | **Experimental** S3 JSON connector (fake/CI; Alpha) |
| [`etlantic-iceberg`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-iceberg/README.md) | `etlantic_iceberg` | **Experimental** Iceberg connector (fake/CI; Alpha) |
| [`etlantic-snowflake`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-snowflake/README.md) | `etlantic_snowflake` | **Experimental** Snowflake connector (fake/CI; Alpha) |
| [`medallantic`](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/README.md) | `medallantic` | **Facade** — medallion vocabulary and SparkForge migration adapter |
| [`etlantic-sparkforge`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-sparkforge/README.md) | `etlantic_sparkforge` | **Redirect** (deprecated) — re-exports `medallantic` |
| [`etlantic-fastapi`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-fastapi/README.md) | `etlantic_fastapi` | Dual surface: CP1 `ETLanticAPI` + thin `create_reference_app` (pin `==0.43.0`; CP1 ≠ multi-tenant GA) |
| [`etlantic-datafusion`](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-datafusion/README.md) | `etlantic_datafusion` | **Experimental** DataFusion stub (Gate B; not graduated) |

MkDocs API generation includes core `src/` and first-party plugin package
paths. Shallow module-level stubs for optional packages live in
[API — Optional packages](API_OPTIONAL_PACKAGES.md). For plugin factories,
registration, protocol versions, and failure modes, also use the linked package
README and the corresponding engine tutorial.

## Related

- [API — Optional packages](API_OPTIONAL_PACKAGES.md)
- [Compatibility](COMPATIBILITY.md)
- [Portable compiler matrix](PORTABLE_COMPILER_MATRIX.md)
- [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
- [Third-party compiler tutorial](../07_PLUGIN_SDK/THIRD_PARTY_COMPILER_TUTORIAL.md)
