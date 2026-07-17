# Installation

ETLantic 0.10.0 provides the typed modeling kernel, contract interoperability
(ODCS/DTCS/DPCS), multi-phase validation, profiles, deterministic planning,
a local runtime that executes plans with Python callables, in-memory
artifacts, and stdlib JSON/CSV bindings, plus optional Polars, Pandas, SQL,
PySpark, and Airflow plugins. Structured Streaming APIs are experimental.

!!! warning "PyPI may not have 0.10.0 yet"
    Until a matching `v0.10.0` release is published to PyPI, **install from
    source** (recommended path below). Anonymous `pip install etlantic` can
    fail with “No matching distribution.” See
    [Troubleshooting](TROUBLESHOOTING.md).

## Requirements

- Python 3.11 or newer
- ContractModel as a companion package (installed automatically with ETLantic)

[uv](https://docs.astral.sh/uv/) is recommended. Adopters can also use plain
`pip` once wheels are on PyPI.

## Recommended: install from source

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync
uv run python -c "import etlantic; print(etlantic.__version__)"
uv run python examples/quickstart.py
```

`uv sync` creates `.venv`, installs the package in editable mode, and installs
the `dev` group (pytest, ruff, mkdocs).

### Editable install with pip (no uv)

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -e .
python -c "import etlantic; print(etlantic.__version__)"
```

## When wheels are on PyPI

```bash
python3.11 -m pip install --upgrade pip
python3.11 -m pip install 'etlantic>=0.10.0'
```

Or with uv:

```bash
uv add 'etlantic>=0.10.0'
```

Verify:

```bash
python -c "import etlantic; print(etlantic.__version__)"
```

### Optional engine plugins

Core never installs Polars, Pandas, database drivers, or PySpark. Add engines
explicitly (from a checkout use `uv sync --group …`; from PyPI use pip):

```bash
pip install etlantic-polars    # Polars reference plugin
pip install etlantic-pandas    # Pandas compatibility plugin
pip install etlantic-sql       # PostgreSQL SQL reference plugin
pip install etlantic-pyspark   # PySpark reference plugin + local provider
pip install etlantic-airflow   # Airflow DAG compiler
pip install etlantic-keyring   # OS keyring secret provider
pip install etlantic-sqlmodel  # SQLModel bridge helpers
pip install etlantic-sparkforge  # SparkForge → ETLantic IR adapter
# or extras:
pip install 'etlantic[polars]'
pip install 'etlantic[pandas]'
pip install 'etlantic[dataframes]'   # polars + pandas
pip install 'etlantic[sql]'          # alias: postgresql
pip install 'etlantic[pyspark]'      # alias: spark
pip install 'etlantic[airflow]'
pip install 'etlantic[keyring]'
pip install 'etlantic[sqlmodel]'
pip install 'etlantic[sparkforge]'
pip install 'etlantic[otel]'         # alias: observability
pip install 'etlantic[arrow]'
```

For SQL, set a connection URL (PostgreSQL is the reference; SQLite is demo-only):

```bash
export ETLANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/etlantic
# or for a local demo:
export ETLANTIC_SQL_URL=sqlite+pysqlite:///:memory:
```

Select SQL with `Profile(sql_engine="sql")`. The SQL reference plugin does not
implement `MERGE` (`sql_merge=False`).

Select Spark with `Profile(spark_engine="pyspark")` and
`@Transformation.implementation("pyspark")`. See
[Migration 0.6 → 0.7](../11_DEVELOPMENT/MIGRATION_0_6_TO_0_7.md).

Airflow compilation is available via `etlantic-airflow` (`compile_plan` /
`etlantic compile … --target airflow`). Dagster and Prefect remain future
plugins.

## Upgrade

Prefer a git checkout and `uv sync` until PyPI carries 0.10.0. When wheels
exist:

```bash
python -m pip install --upgrade 'etlantic>=0.10.0'
# or
uv lock --upgrade-package etlantic
```

Review the
[changelog](https://github.com/eddiethedean/etlantic/blob/main/CHANGELOG.md)
and migration guides under
[Development](../11_DEVELOPMENT/README.md) before upgrading between 0.x
releases because breaking changes remain possible.

## Development Setup

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

### Common commands

| Command | Purpose |
|---|---|
| `uv sync` | Create/update `.venv` from `uv.lock` |
| `uv sync --group dataframes` | Also install Polars and Pandas plugins |
| `uv sync --group pyspark` | Also install the PySpark plugin + sparkless |
| `uv sync --group airflow` | Also install the Airflow orchestrator plugin |
| `uv sync --group sql` | Also install the SQL plugin |
| `uv sync --group sparkforge` | Also install the SparkForge adapter |
| `uv sync --group keyring` | Also install the keyring provider |
| `uv sync --group sqlmodel` | Also install the SQLModel bridge |
| `uv lock` | Refresh the lockfile after dependency changes |
| `uv run pytest` | Run tests |
| `uv run ruff check .` | Lint |
| `uv run python scripts/check_docs.py` | Docs consistency gate |
| `NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict` | Build the documentation site |
| `uv run mkdocs serve` | Preview docs locally |

## Repository Layout

```text
pyproject.toml
uv.lock
.python-version
src/etlantic/
packages/etlantic-polars/
packages/etlantic-pandas/
packages/etlantic-sql/
packages/etlantic-pyspark/
packages/etlantic-airflow/
packages/etlantic-sparkforge/
tests/
examples/
docs/
```

## Installation Problems

See [Troubleshooting](TROUBLESHOOTING.md) for Python-version errors, missing
PyPI wheels, version mismatches, missing plugins, and stale virtual
environments.

## Dependency Philosophy

ETLantic keeps the core install small. Dataframe engines, SQL drivers,
orchestrators, and storage clients belong in optional plugins—not the base
package.

See [Dependency Strategy](../11_DEVELOPMENT/DEPENDENCY_STRATEGY.md).

## Next Step

Continue with [Capabilities](CAPABILITIES.md), then
[Quickstart](QUICKSTART.md).
