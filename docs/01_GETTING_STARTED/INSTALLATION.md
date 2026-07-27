# Installing ETLantic 0.24.0

!!! tip "PyPI user vs contributor clone"
    | Audience | Path |
    |---|---|
    | **First-time / PyPI** | Sections below through [Quickstart](QUICKSTART.md). Use `python -m pip` and `python -m etlantic`. |
    | **Contributor / monorepo** | Skip to [Repository checkout](#repository-checkout-contributors) and use `uv sync`. Do not mix `uv run` example commands with a pip-only install. |

## Requirements

- Python 3.11, 3.12, or 3.13
- A virtual environment (strongly recommended)

## Install core (2 minutes)

Pin the published **0.24.0** release for reproducible evaluation. Use a virtual
environment. Prefer `python -m pip` and `python -m etlantic` so the interpreter
you intend is the one that runs.

### pip

```bash
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.24.0'
python -m etlantic --version
```

### uv (no existing project)

```bash
uv venv
source .venv/bin/activate
uv pip install 'etlantic==0.24.0'
uv run etlantic --version
```

If you already have a uv project (`pyproject.toml`), you may use
`uv add 'etlantic==0.24.0'` instead.

### Poetry

```bash
poetry new my-pipeline && cd my-pipeline
poetry add 'etlantic==0.24.0'
poetry run etlantic --version
```

### Conda / Mamba

```bash
conda create -n etlantic python=3.12 pip -y
conda activate etlantic
python -m pip install 'etlantic==0.24.0'
python -m etlantic --version
```

### Windows (pip)

```powershell
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install 'etlantic==0.24.0'
py -3.11 -m etlantic --version
```

Verify the import:

```bash
python -c "import etlantic; print(etlantic.__version__)"
```

## Next Step

Continue with [Quickstart](QUICKSTART.md). `etlantic init` requires an **empty
directory** (or pass `--force`). Optional engines are below—skip them until
after first success. Contributor checkout lives at the end of this page.

---

## Optional engine plugins

Core never installs Polars, Pandas, database drivers, or PySpark. Add engines
explicitly and **match the core minor** (`0.24.0` with `0.24.0`).

**Primary install (separate packages):**

```bash
python -m pip install 'etlantic-polars==0.24.0'     # dataframe + Polars portable compiler
python -m pip install 'etlantic-pandas==0.24.0'     # dataframe + Pandas portable compiler
python -m pip install 'etlantic-sql==0.24.0'        # PostgreSQL SQL reference plugin
python -m pip install 'etlantic-pyspark==0.24.0'    # PySpark plugin + portable compiler
python -m pip install 'etlantic-airflow==0.24.0'    # Airflow DAG compiler
python -m pip install 'etlantic-prefect==0.24.0'    # Prefect direct-execution (local MVP)
python -m pip install 'etlantic-keyring==0.24.0'    # OS keyring secret provider
python -m pip install 'etlantic-sqlmodel==0.24.0'   # SQLModel bridge helpers
python -m pip install 'etlantic-sparkforge==0.24.0' # SparkForge → ETLantic IR adapter
```

**Equivalent extras** (same packages, same pins):

```bash
python -m pip install 'etlantic[polars]==0.24.0'
python -m pip install 'etlantic[pandas]==0.24.0'
python -m pip install 'etlantic[dataframes]==0.24.0'   # polars + pandas
python -m pip install 'etlantic[sql]==0.24.0'          # alias: [postgresql]
python -m pip install 'etlantic[pyspark]==0.24.0'      # alias: [spark]
python -m pip install 'etlantic[airflow]==0.24.0'
python -m pip install 'etlantic[prefect]==0.24.0'
# Experimental Gate B stub (not graduated; not recommended):
python -m pip install 'etlantic[datafusion]==0.24.0'
```

Also available: `[keyring]`, `[sqlmodel]`, `[sparkforge]`, `[fastapi]`,
`[otel]`, `[arrow]`.

```bash
python -m pip install 'etlantic-fastapi==0.24.0'   # thin 0.24 authoring HTTP reference
# or: python -m pip install 'etlantic[fastapi]==0.24.0'
```

Verify discovery after installing Polars:

```bash
python -m etlantic plugin list --kind transform_compiler --format json
```

### PySpark / JVM

`etlantic-pyspark` requires a working JVM (`JAVA_HOME`). If Spark fails at
import or session start, see [Troubleshooting](TROUBLESHOOTING.md).

### SQL connection URL

PostgreSQL is the reference; SQLite is demo-only. The URL below is a
**placeholder**—do not commit real credentials:

```bash
export ETLANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/etlantic
# local demo:
export ETLANTIC_SQL_URL=sqlite+pysqlite:///:memory:
```

Select SQL with `Profile(sql_engine="sql")`. The reference plugin does not
implement `MERGE` (`sql_merge=False`). Select Spark with
`Profile(spark_engine="pyspark")`.

Airflow: `etlantic compile … --target airflow` via `etlantic-airflow` (compile
only; does not install Apache Airflow). Prefect: direct execution via
`etlantic-prefect` (local MVP; deployment/serve remain future).

## Upgrade

Prefer the [Upgrade hub](UPGRADE.md). Quick pin:

```bash
python -m pip install --upgrade 'etlantic==0.24.0'
```

## Installation problems

See [Troubleshooting](TROUBLESHOOTING.md) for Python-version errors, core/plugin
minor skew, missing plugins, JVM issues, PATH/`etlantic` not found, and stale
virtual environments.

## Dependency philosophy

ETLantic keeps the core install small. Engines and orchestrators belong in
optional plugins. See [Dependency Strategy](../11_DEVELOPMENT/DEPENDENCY_STRATEGY.md).

---

## Install from source (optional)

Use a git checkout when you want mainline or editable monorepo plugins:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'git+https://github.com/eddiethedean/etlantic.git@v0.24.0'
python -m etlantic --version
```

Optional plugins from the same monorepo (after cloning):

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
git checkout v0.24.0
uv sync --locked
uv sync --extra fastapi   # optional reference adapter
uv run python -m etlantic --version
```

## Repository checkout (contributors)

Prefer `uv sync` for editable core + dev tools:

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync --locked
uv run python -c "import etlantic; print(etlantic.__version__)"
uv run python examples/memory_customers.py
```

`uv sync` creates `.venv`, installs editable core, and the `dev` group.
Editable `pip install -e .` alone does **not** install optional plugins or
dev tools—prefer `uv sync` or add groups explicitly:

```bash
uv sync --group dataframes   # polars + pandas
uv sync --group sql
uv sync --group pyspark
uv sync --group airflow
uv sync --group prefect
```

If you must use pip for an editable install:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Install pytest, ruff, and mkdocs manually or switch to `uv sync --locked`. Full
contributor workflow: [Contributing](../11_DEVELOPMENT/CONTRIBUTING.md).
