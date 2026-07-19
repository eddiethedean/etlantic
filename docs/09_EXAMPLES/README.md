# Examples

## Green path

1. [Installation](../01_GETTING_STARTED/INSTALLATION.md) — `pip install etlantic==0.18.0`
2. [Quickstart](../01_GETTING_STARTED/QUICKSTART.md)
3. [First Pipeline](../01_GETTING_STARTED/FIRST_PIPELINE.md)
4. [Engine selection](../01_GETTING_STARTED/ENGINE_SELECTION.md)
5. Runnable scripts below

Pages under **Design Studies** are aspirational stubs—not installable tutorials.

## Runnable guides (docs)

- [Sample multi-file project](SAMPLE_PROJECT.md) — `examples/sample_project/`
- [File-backed pipeline](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) — JSON and CSV
- [Ops examples](../01_GETTING_STARTED/OPS_EXAMPLES.md) — secrets, schema, SARIF
- [Polars](../06_EXECUTION/POLARS_TUTORIAL.md)
- [Pandas](../06_EXECUTION/PANDAS_TUTORIAL.md)
- [SQL](../06_EXECUTION/SQL_TUTORIAL.md)
- [PySpark](../06_EXECUTION/PYSPARK_TUTORIAL.md)
- [Airflow](../06_EXECUTION/AIRFLOW_TUTORIAL.md)
- [Prefect direct execution](PREFECT_RUN.md) — `examples/prefect_run.py`
- [Airflow Compile](AIRFLOW_COMPILE.md) — `examples/airflow_compile.py`
- [Portable transforms](PORTABLE_TRANSFORMS.md) —
  `examples/portable_polars_kernel.py`, `portable_pandas_kernel.py`, and
  `portable_wave17.py`
- [Polars ↔ Pandas interchange](INTERCHANGE_POLARS_PANDAS.md) —
  `examples/interchange_polars_pandas.py`
- [SparkForge Adapter](SPARKFORGE_ADAPTER.md) — `tests/sparkforge/`

## Runnable scripts (repository `examples/`)

Scripts marked **(CI)** run in `.github/workflows/checks.yml`. Others are
documented and copy-paste runnable locally. Repository index:
[examples/README.md on GitHub](https://github.com/eddiethedean/etlantic/blob/main/examples/README.md).

### In-memory quickstart (CI)

```bash
uv run python examples/quickstart.py
```

### Portable kernels and 0.17 families (docs / local)

```bash
uv sync --group dataframes
uv run python examples/portable_polars_kernel.py
uv run python examples/portable_pandas_kernel.py
uv run python examples/portable_wave17.py
```

### Polars ↔ Pandas interchange (CI)

```bash
uv sync --group dataframes
uv run python examples/interchange_polars_pandas.py
```

See [Polars ↔ Pandas Interchange](INTERCHANGE_POLARS_PANDAS.md).

### JSON and CSV storage (docs / local)

```bash
uv run python examples/file_storage.py
```

### Dataframe parity (Polars / Pandas) (CI)

```bash
uv sync --group dataframes
uv run python examples/dataframe_parity.py polars
uv run python examples/dataframe_parity.py pandas
```

### SQL to SQL (CI)

```bash
uv sync --group sql
uv run python examples/sql_to_sql.py
uv run python examples/sql_boundary_hybrid.py
uv run python examples/sql_transactional_write.py
uv run python examples/sql_failure_recovery.py
```

Defaults to in-memory SQLite for demos; set `ETLANTIC_SQL_URL` for
PostgreSQL.

### Local PySpark (CI)

```bash
uv sync --group pyspark
uv run python examples/pyspark_local.py
```

### Airflow compile (CI)

```bash
uv sync --group airflow
uv run python examples/airflow_compile.py
```

### Prefect local execution (CI)

```bash
uv sync --group prefect
uv run python examples/prefect_run.py
```

## Design studies (aspirational)

The remaining pages in this section explore intended integrations. Each page
opens with a Future design warning. They may contain APIs, packages, or
commands that go beyond the shipped surface — prefer the runnable guides and
`examples/` for installable behavior.

| Topic | Prefer instead |
|---|---|
| CSV and JSON through built-in storage | `examples/file_storage.py` |
| Pandas and Polars pipelines | `examples/dataframe_parity.py` |
| SQL execution and pushdown | `examples/sql_*.py` |
| PySpark batch | `examples/pyspark_local.py` |
| Airflow compilation | [Airflow Compile](AIRFLOW_COMPILE.md) |
| Graphviz DOT / HTML lineage | `etlantic.viz` / `etlantic viz` |
| SparkForge migration adapter | [SparkForge Adapter](SPARKFORGE_ADAPTER.md) |
| Structured Streaming | Experimental foundation only |
| Portable PySpark-style transformations | [Portable Transformation](PORTABLE_TRANSFORMS.md) |

Do not use a design study as an installation or API reference. The
[capabilities page](../01_GETTING_STARTED/CAPABILITIES.md) and
[API reference](../10_REFERENCE/API_REFERENCE.md) define the current boundary.
