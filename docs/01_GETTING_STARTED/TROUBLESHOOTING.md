# Troubleshooting

## `pip install pipelantic` rejects my Python version

Pipelantic requires Python 3.11 or newer. Check with:

```bash
python --version
```

## Installed version is older than the docs

These docs describe Pipelantic **0.6.0**. Confirm what you installed:

```bash
python -c "import pipelantic; print(pipelantic.__version__)"
```

If the version is older, upgrade:

```bash
python -m pip install --upgrade 'pipelantic>=0.6.0'
```

If pip still resolves an older release, you may be on a mirror or pin. Check
`pip index versions pipelantic` (or visit
[PyPI](https://pypi.org/project/pipelantic/)) and clear conflicting constraints
in your environment.

## `pip install pipelantic-polars` / `pipelantic-pandas` / `pipelantic-sql` fails

Those packages ship with Pipelantic 0.6.0. They are separate distributions:

```bash
python -m pip install --upgrade pipelantic-polars
python -m pip install --upgrade pipelantic-pandas
python -m pip install --upgrade pipelantic-sql
```

If pip reports no matching distribution:

1. Confirm core is already at 0.6.0 or newer.
2. Confirm Python is 3.11+.
3. Confirm the package name uses a hyphen (`pipelantic-polars`), not an
   underscore.

Until 0.6.0 is on PyPI, install from a git checkout with
`uv sync --group dataframes` (and install `pipelantic-sql` from the workspace)
instead.

## A transformation has no implementation

Declaring a `Transformation` defines its contract, not its executable code.
Register a local implementation before running:

```python
@MyTransformation.implementation("local")
def run_locally(rows):
    return rows
```

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

Use `local` for plan-oriented examples or `development` for the built-in local
runtime examples. Do not silently switch profile names within one workflow.

## A Pandas, Polars, SQL, Spark, or Airflow example fails

Install the matching plugin for dataframe engines
(`pipelantic-polars` / `pipelantic-pandas`) and set `Profile.dataframe_engine`,
or install `pipelantic-sql` and set `Profile.sql_engine="sql"`. Spark and
Airflow remain design material for later milestones. Start with the runnable
examples under `examples/` (including `examples/sql_to_sql.py`).

## Commands in a design page do not exist

The current CLI supports `validate`, `inspect`, `plan`, `plan explain`, `run`,
and `report show|export`. See the [CLI reference](../10_REFERENCE/CLI.md).

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

Include the Pipelantic version, Python version, command, complete traceback or
diagnostic code, and a minimal pipeline definition in the issue report. Never
include credentials or production data.
