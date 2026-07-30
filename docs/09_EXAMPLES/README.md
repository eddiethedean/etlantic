# Examples

## Green path

1. Install with `pip install etlantic`
2. [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/)
3. [First Pipeline](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/FIRST_PIPELINE/)
4. Optional: [Programmatic authoring](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PROGRAMMATIC_AUTHORING/)
5. [Engine selection](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/ENGINE_SELECTION/)
6. Runnable scripts below

Aspirational design-study pages under `docs/09_EXAMPLES/` were removed in
0.34. Prefer the runnable guides below and the PyPI paths in
[Polars](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/POLARS_TUTORIAL/) /
[Pandas](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PANDAS_TUTORIAL/) /
[SQL hello](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/SQL_HELLO_PYPI/).

## Runnable guides (docs)

- [Production sample](https://etlantic.readthedocs.io/en/latest/09_EXAMPLES/PRODUCTION_SAMPLE/) — allowlist + SARIF + file I/O
- [Sample multi-file project](https://etlantic.readthedocs.io/en/latest/09_EXAMPLES/SAMPLE_PROJECT/) — `examples/sample_project/`
- [File-backed pipeline](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/FILE_STORAGE_TUTORIAL/) — JSON and CSV
- [Ops examples](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/OPS_EXAMPLES/) — secrets, schema, SARIF
- [Polars](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/POLARS_TUTORIAL/)
- [Pandas](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PANDAS_TUTORIAL/)
- [SQL hello (PyPI)](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/SQL_HELLO_PYPI/)
- [SQL](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/SQL_TUTORIAL/) (clone companion)
- [PySpark](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PYSPARK_TUTORIAL/)
- [Airflow](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/AIRFLOW_TUTORIAL/)
- [Prefect direct execution](https://etlantic.readthedocs.io/en/latest/09_EXAMPLES/PREFECT_RUN/) — `examples/prefect_run.py`
- [Airflow Compile](https://etlantic.readthedocs.io/en/latest/09_EXAMPLES/AIRFLOW_COMPILE/) — `examples/airflow_compile.py`
- [Portable transforms](https://etlantic.readthedocs.io/en/latest/09_EXAMPLES/PORTABLE_TRANSFORMS/) —
  `examples/portable_polars_kernel.py`, `portable_pandas_kernel.py`, and
  `portable_wave17.py`
- [Polars ↔ Pandas interchange](https://etlantic.readthedocs.io/en/latest/09_EXAMPLES/INTERCHANGE_POLARS_PANDAS/) —
  `examples/interchange_polars_pandas.py`
- [Medallantic](https://etlantic.readthedocs.io/en/latest/09_EXAMPLES/MEDALLANTIC/) — SparkForge IR migration adapter (planning/validate only)
- Programmatic JSON authoring — `examples/pipeline_definition_json.py` (clone; CI)

## Runnable scripts (repository `examples/`)

!!! note "Clone required"
    `examples/` is **not** installed with the PyPI wheel. Commands below need a
    git checkout (`uv run …`). Pip-only users: paste the
    [Quickstart](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/QUICKSTART/) or open scripts on GitHub.

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

See [Polars ↔ Pandas Interchange](https://etlantic.readthedocs.io/en/latest/09_EXAMPLES/INTERCHANGE_POLARS_PANDAS/).

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

Prefer the runnable guides above and the
[capabilities page](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/) /
[API reference](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/API_REFERENCE/) for the current boundary.
