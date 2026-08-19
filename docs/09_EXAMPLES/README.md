# Examples

## Green path

1. Install with `pip install etlantic`
2. [Quickstart](../01_GETTING_STARTED/QUICKSTART.md)
3. [First Pipeline](../01_GETTING_STARTED/FIRST_PIPELINE.md)
4. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
5. [Engine selection](../01_GETTING_STARTED/ENGINE_SELECTION.md)
6. Runnable scripts below

Aspirational design-study pages under `docs/09_EXAMPLES/` were removed in
0.34. Prefer the runnable guides below and the PyPI paths in
[Polars](../06_EXECUTION/POLARS_TUTORIAL.md) /
[Pandas](../06_EXECUTION/PANDAS_TUTORIAL.md) /
[SQL hello](../06_EXECUTION/SQL_HELLO_PYPI.md).

## Runnable guides (docs)

- [Production sample](PRODUCTION_SAMPLE.md) — allowlist + SARIF + file I/O
- [Sample multi-file project](SAMPLE_PROJECT.md) — `examples/sample_project/`
- [File-backed pipeline](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) — JSON and CSV
- [Landing zone](../06_EXECUTION/LANDING_ZONE.md) —
  `examples/landing_zone_watch_submitter.py` (continuous submitter)
- [Embeddable HTTP API](../06_EXECUTION/CONTROL_PLANE.md) — embeddable FastAPI
- [Ops examples](../01_GETTING_STARTED/OPS_EXAMPLES.md) — secrets, schema, SARIF
- [Polars](../06_EXECUTION/POLARS_TUTORIAL.md)
- [Pandas](../06_EXECUTION/PANDAS_TUTORIAL.md)
- [SQL hello (PyPI)](../06_EXECUTION/SQL_HELLO_PYPI.md)
- [SQL](../06_EXECUTION/SQL_TUTORIAL.md) (clone companion)
- [PySpark](../06_EXECUTION/PYSPARK_TUTORIAL.md)
- [Airflow](../06_EXECUTION/AIRFLOW_TUTORIAL.md)
- [Prefect direct execution](PREFECT_RUN.md) — `examples/prefect_run.py`
- [Airflow Compile](AIRFLOW_COMPILE.md) — `examples/airflow_compile.py`
- [Portable transforms](PORTABLE_TRANSFORMS.md) —
  `examples/portable_polars_kernel.py`, `portable_pandas_kernel.py`, and
  `portable_wave17.py`
- [Polars ↔ Pandas interchange](INTERCHANGE_POLARS_PANDAS.md) —
  `examples/interchange_polars_pandas.py`
- [Medallantic](MEDALLANTIC.md) — SparkForge IR migration adapter (planning/validate only)
- Programmatic JSON authoring — `examples/pipeline_definition_json.py` (clone; CI)

## Runnable scripts (repository `examples/`)

!!! note "Clone required"
    `examples/` is **not** installed with the PyPI wheel. Commands below need a
    git checkout (`uv run …`). Pip-only users: paste the
    [Quickstart](../01_GETTING_STARTED/QUICKSTART.md) or open scripts on GitHub.

Scripts marked **(CI)** run in `.github/workflows/checks.yml`. Others are
documented and copy-paste runnable locally. Repository index:
[examples/README.md on GitHub](https://github.com/eddiethedean/etlantic/blob/main/examples/README.md).

### In-memory companion demo (clone / CI)

Not the Quickstart — requires a git checkout (`examples/` is not on the PyPI wheel):

```bash
uv run python examples/memory_customers.py
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

### Landing-zone watch submitter (docs / local)

```bash
# requires etlantic-fastapi and a running CP1 app
uv sync --extra fastapi
uv run python examples/landing_zone_watch_submitter.py \
  --watch ./inbox --definition landing_pipe --base-url http://127.0.0.1:8000
```

See [Landing zone](../06_EXECUTION/LANDING_ZONE.md) and
[Embeddable HTTP API](../06_EXECUTION/CONTROL_PLANE.md).

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

Prefer the runnable guides above and the
[capabilities page](../01_GETTING_STARTED/CAPABILITIES.md) /
[API reference](../10_REFERENCE/API_REFERENCE.md) for the current boundary.
