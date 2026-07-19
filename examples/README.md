# Runnable Examples

These examples use APIs and dependencies shipped in ETLantic **0.18.0**. Install
with `pip install etlantic==0.18.0` (plus matching `==0.18.0` optional engine
packages), or from a checkout with `uv sync` and `uv run python …`.

**CI vs local:** `.github/workflows/checks.yml` runs the scripts marked
**(CI)** below. Scripts marked **(docs / local)** are copy-paste runnable and
documented, but are not executed on every PR matrix job.

## Quickstart (CI)

```bash
uv run python examples/quickstart.py
# or, after pip install etlantic:
python examples/quickstart.py
```

Validates, plans, and runs with in-memory storage; prints `succeeded` and
curated records (matches [Quickstart](../docs/01_GETTING_STARTED/QUICKSTART.md)).

## Sample multi-file project (docs / local)

```bash
uv run python -m examples.sample_project.run_local
```

Same story split across `contracts.py`, `transforms.py`, `pipeline.py`, and
`run_local.py`. See [Sample project](../docs/09_EXAMPLES/SAMPLE_PROJECT.md).

## Portable Polars / Pandas (docs / local)

```bash
# requires etlantic-polars / etlantic-pandas
uv sync --group dataframes
uv run python examples/portable_polars_kernel.py
uv run python examples/portable_pandas_kernel.py
uv run python examples/portable_wave17.py
```

Authors with `@Transformation.portable`, plans with
`portable_transform_policy="require"`, and executes through the shipped Polars
or Pandas compilers (Pandas is eager-only / index-neutral). The Wave 17 example
demonstrates advanced families shipped on Polars and PySpark.

## Polars ↔ Pandas interchange (CI)

```bash
# requires etlantic-polars and etlantic-pandas
uv sync --group dataframes
uv run python examples/interchange_polars_pandas.py
```

Gate A demo: a Polars step feeds a Pandas step across a planned
`etlantic.interchange/1` boundary. See
[docs/09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md](../docs/09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md).

## JSON and CSV storage (docs / local)

```bash
python examples/file_storage.py
```

Runs tested `json_to_json()` and `csv_to_csv()` workflows using built-in
storage bindings.

## Dataframe parity (CI)

```bash
# requires etlantic-polars / etlantic-pandas
python examples/dataframe_parity.py polars
python examples/dataframe_parity.py pandas
```

Runs the same logical pipeline against either dataframe plugin via
`Profile.dataframe_engine`.

## SQL to SQL (CI)

```bash
# requires etlantic-sql
python examples/sql_to_sql.py
python examples/sql_boundary_hybrid.py
python examples/sql_transactional_write.py
python examples/sql_failure_recovery.py
```

Runs SQL-native pipelines. Defaults to in-memory SQLite for demos; set
`ETLANTIC_SQL_URL` for PostgreSQL.

## Local PySpark (CI)

```bash
# requires etlantic-pyspark
python examples/pyspark_local.py
```

Runs a batch Spark pipeline with the local provider via
`Profile.spark_engine="pyspark"`.

## Airflow compile (CI)

```bash
# requires etlantic-airflow
python examples/airflow_compile.py
```

Runs a pipeline locally, then compiles the same plan to an Airflow DAG module
via `compile_plan(..., target="airflow")`.

## Prefect local execution (CI)

```bash
# requires etlantic-prefect
python examples/prefect_run.py
```

Runs an already-resolved plan through the shipped Prefect 3
`ExecutionScheduler` local MVP.

Longer design-study pages under Documentation → Examples remain illustrative.
Structured Streaming APIs are experimental.
