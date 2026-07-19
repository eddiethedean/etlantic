# Troubleshooting

## `pip install etlantic` rejects my Python version

ETLantic requires Python 3.11 or newer. Check with:

```bash
python --version
# Windows:
py -3.11 --version
```

## Installed version is older than the docs

These docs describe ETLantic **0.14.0**. Confirm what you installed:

```bash
python -c "import etlantic; print(etlantic.__version__)"
etlantic --version
```

Upgrade from PyPI:

```bash
python -m pip install --upgrade 'etlantic>=0.14.0'
```

From a checkout, prefer `uv sync` / `git pull`.

## Plugin install fails (`etlantic-polars`, `etlantic-pyspark`, …)

Those packages ship with ETLantic 0.14.0 as separate distributions.

From PyPI:

```bash
python -m pip install --upgrade etlantic-polars etlantic-pandas
python -m pip install --upgrade etlantic-sql etlantic-pyspark
python -m pip install --upgrade etlantic-airflow etlantic-sparkforge
```

From a checkout:

```bash
uv sync --group dataframes   # polars + pandas
uv sync --group sql
uv sync --group pyspark
uv sync --group airflow
uv sync --group sparkforge
uv sync --group keyring
uv sync --group sqlmodel
```

Confirm Python is 3.11+ and the package name uses a hyphen
(`etlantic-pyspark`), not an underscore.

## A transformation has no implementation

Declaring a `Transformation` defines its contract, not its executable code.
Either register a native implementation:

```python
@MyTransformation.implementation("local")
def run_locally(rows):
    return rows
```

…or, for Polars/PySpark/Pandas portable relational plans in 0.13–0.14, author with
`@MyTransformation.portable`, install `etlantic-polars`, and set
`Profile(dataframe_engine="polars", portable_transform_policy="require")`.
See `examples/portable_polars_kernel.py`.

## Portable compiler not discovered / `PMXFORM302`

```bash
python -c "from etlantic.transform.discovery import discover_transform_compilers; print(discover_transform_compilers())"
```

If the map is empty, install a matching `etlantic-polars==0.14.0` into the
same environment as core and reinstall if you changed Python interpreters.

## `PMXFORM301` unsupported action or function

The Polars kernel claim rejects joins, windows, and conversion-profile ops such
as `dtcs:cast`. Narrow the portable definition, add a native
`@implementation(...)`, or use `portable_transform_policy="prefer"` /
`"native"`.

## My memory source returns no records

Seed the exact binding name used by the pipeline:

```python
runtime.memory.seed("customer_source", records)
```

Read sink output using its binding:

```python
runtime.memory.get("customer_sink")
```

## Planning and execution use different profiles

Use one profile name for the whole workflow. The built-in local runtime
examples in these docs use `development`. The CLI `plan` command defaults to
`local` and `run` defaults to `development`—pass `--profile development`
explicitly when you want them to match.

Do not silently switch profile names within one workflow.

## A Pandas, Polars, SQL, Spark, or Airflow example fails

Install the matching plugin and set the corresponding profile engine
(`dataframe_engine`, `sql_engine`, `spark_engine`, or `orchestrator`).

| Need | Install | Example |
|---|---|---|
| Polars portable kernel | `pip install etlantic-polars` or `uv sync --group dataframes` | `examples/portable_polars_kernel.py` |
| Polars / Pandas native | `pip install etlantic-polars etlantic-pandas` or `uv sync --group dataframes` | `examples/dataframe_parity.py` |
| SQL | `pip install etlantic-sql` or `uv sync --group sql` | `examples/sql_to_sql.py` |
| PySpark | `pip install etlantic-pyspark` or `uv sync --group pyspark` | `examples/pyspark_local.py` |
| Airflow compile | `pip install etlantic-airflow` or `uv sync --group airflow` | `examples/airflow_compile.py` |
| SparkForge adapter | `pip install etlantic-sparkforge` or `uv sync --group sparkforge` | `tests/sparkforge/` |

Airflow compilation is **available** via `etlantic-airflow` (0.8+). Dagster
and Prefect compilers are not shipped.

## Commands in a design page do not exist

The shipped CLI includes:

`validate`, `inspect`, `plan`, `run`, `compile`, `generate`, `diff`,
`plugin`, `schema`, `reliability`, `viz`, `report`

See the [CLI reference](../10_REFERENCE/CLI.md). Pages marked **Future
design** may show commands that are not shipped—check
[Capabilities](CAPABILITIES.md) first.

## A virtual environment breaks after moving the repository

Virtual-environment entry points contain absolute paths. Delete and recreate
the environment after moving or renaming a checkout:

```bash
rm -rf .venv
uv sync --locked
```

Only run the removal command from the repository root after confirming
`.venv` is the project environment.

## Where to report a problem

Include the ETLantic version, Python version, command, complete traceback or
diagnostic code, and a minimal pipeline definition in the issue report. Never
include credentials or production data.
