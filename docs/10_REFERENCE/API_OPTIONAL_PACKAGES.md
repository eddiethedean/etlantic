---
status: available
since: "0.41.0"
current_minor: "0.41"
audience: developer
---

# API — Optional packages

> **Status: Available in ETLantic 0.41.0.** Per-package API pages for first-party
> optional packages. Install/overview hub:
> [Optional Packages](OPTIONAL_PACKAGES.md). Core symbols:
> [Python API Reference](API_REFERENCE.md).

Each package page includes a minimal setup example, a failure-mode table, and
mkdocstrings coverage of the public module tree. Package READMEs remain the
install and narrative home.

## Packages

- [etlantic-polars](api_optional/etlantic_polars.md) — Polars dataframe plugin + portable compiler
- [etlantic-pandas](api_optional/etlantic_pandas.md) — Pandas dataframe plugin + portable compiler
- [etlantic-sql](api_optional/etlantic_sql.md) — SQL plugin (SQLite + PostgreSQL)
- [etlantic-pyspark](api_optional/etlantic_pyspark.md) — PySpark plugin + portable compiler
- [etlantic-airflow](api_optional/etlantic_airflow.md) — Airflow DAG compiler
- [etlantic-prefect](api_optional/etlantic_prefect.md) — Prefect local scheduler MVP
- [etlantic-keyring](api_optional/etlantic_keyring.md) — OS keyring secret provider
- [etlantic-sqlmodel](api_optional/etlantic_sqlmodel.md) — SQLModel bridge helpers
- [etlantic-datafusion](api_optional/etlantic_datafusion.md) — Experimental DataFusion stub
- [etlantic-s3](api_optional/etlantic_s3.md) — Experimental S3-compatible connectors
- [etlantic-iceberg](api_optional/etlantic_iceberg.md) — Experimental Iceberg connectors
- [etlantic-snowflake](api_optional/etlantic_snowflake.md) — Experimental Snowflake connectors
- [etlantic-openlineage](api_optional/etlantic_openlineage.md) — Experimental outbound OpenLineage (CP2)
- [etlantic-fastapi](api_optional/etlantic_fastapi.md) — FastAPI reference adapter
- [medallantic](api_optional/medallantic.md) — Medallion facade + SparkForge migrate

## Quick module stubs (roots)

The directives below keep root-level coverage discoverable from this hub:

## etlantic-polars

::: etlantic_polars
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-pandas

::: etlantic_pandas
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-sql

::: etlantic_sql
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-pyspark

::: etlantic_pyspark
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-airflow

::: etlantic_airflow
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-prefect

::: etlantic_prefect
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-keyring

::: etlantic_keyring
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-sqlmodel

::: etlantic_sqlmodel
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-datafusion

::: etlantic_datafusion
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-s3

::: etlantic_s3
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-iceberg

::: etlantic_iceberg
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-snowflake

::: etlantic_snowflake
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## etlantic-fastapi

::: etlantic_fastapi
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"

## medallantic

::: medallantic
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"
