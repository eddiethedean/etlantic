# Runnable Examples

These examples use APIs and dependencies shipped in ETLantic **0.13.0**. Install
with `pip install etlantic==0.13.0` (plus optional engine packages), or from a
checkout with `uv sync` and `uv run python …`.

## Quickstart

```bash
uv run python examples/quickstart.py
# or, after pip install etlantic:
python examples/quickstart.py
```

The example defines contracts, registers a local Python implementation, runs
the pipeline with in-memory storage, prints the run report, and prints the
curated records.

## Portable Polars kernel (no native implementation)

```bash
# requires etlantic-polars
python examples/portable_polars_kernel.py
```

Authors with `@Transformation.portable`, plans with
`portable_transform_policy="require"`, and executes on Polars through the
shipped kernel compiler.

## JSON and CSV storage

```bash
python examples/file_storage.py
```

Runs tested `json_to_json()` and `csv_to_csv()` workflows using built-in
storage bindings.

## Dataframe parity (Polars / Pandas)

```bash
# requires etlantic-polars / etlantic-pandas
python examples/dataframe_parity.py polars
python examples/dataframe_parity.py pandas
```

Runs the same logical pipeline against either dataframe plugin via
`Profile.dataframe_engine`.

## SQL to SQL

```bash
# requires etlantic-sql
python examples/sql_to_sql.py
python examples/sql_boundary_hybrid.py
python examples/sql_transactional_write.py
python examples/sql_failure_recovery.py
```

Runs SQL-native pipelines. Defaults to in-memory SQLite for demos; set
`ETLANTIC_SQL_URL` for PostgreSQL.

## Local PySpark

```bash
# requires etlantic-pyspark
python examples/pyspark_local.py
```

Runs a batch Spark pipeline with the local provider via
`Profile.spark_engine="pyspark"`.

## Airflow compile

```bash
# requires etlantic-airflow
python examples/airflow_compile.py
```

Runs a pipeline locally, then compiles the same plan to an Airflow DAG module
via `compile_plan(..., target="airflow")`.

Longer design-study pages under Documentation → Examples remain illustrative.
Structured Streaming APIs are experimental.
