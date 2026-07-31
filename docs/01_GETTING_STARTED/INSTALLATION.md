# Installing ETLantic 0.40.0

> **Status: Available in ETLantic 0.40.0.**

ETLantic **0.40.0** supports Python 3.11–3.13 and is published on
[PyPI](https://pypi.org/project/etlantic/0.39.0/).

!!! tip "PyPI user vs contributor clone"
    | Audience | Path |
    |---|---|
    | **First-time / PyPI** | Sections below through [Quickstart](QUICKSTART.md). Use `python -m pip` and `python -m etlantic`. |
    | **Contributor / monorepo** | Skip to [Repository checkout](#repository-checkout-contributors) and use `uv sync`. Do not mix `uv run` example commands with a pip-only install. |

## Requirements

- Python 3.11, 3.12, or 3.13
- A virtual environment (strongly recommended)

## Install core (Day-0 — 2 minutes)

Use a virtual environment. Prefer `python -m pip` and `python -m etlantic` so
the interpreter you intend is the one that runs. Pin **0.39.0** for
reproducible evaluation.

### pip (recommended)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.40.0'
python -m etlantic --version
```

Expected output:

```text
0.39.0
```

### uv (no existing project)

```bash
uv venv
source .venv/bin/activate
uv pip install 'etlantic==0.40.0'
python -m etlantic --version
```

If you already have a uv project (`pyproject.toml`), you may use
`uv add 'etlantic==0.40.0'` instead. Create an **empty subdirectory** for
`python -m etlantic init --with-toml`, or pass `--force` if the directory is
not empty. **`--force` overwrites** scaffolded files such as `pipeline.py`,
`profiles/development.json`, and (with `--with-toml`) `pyproject.toml` /
`etlantic.toml` — prefer an empty subdirectory when unsure.

### Windows (pip)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install 'etlantic==0.40.0'
py -3.11 -m etlantic --version
```

Verify the import:

```bash
python -c "import etlantic; print(etlantic.__version__)"
```

## Next Step

Continue with [Quickstart](QUICKSTART.md). `python -m etlantic init` requires an **empty
directory** (or `--force`). After first success, see [Engine selection](ENGINE_SELECTION.md)
and the [Learning path](LEARNING_PATH.md).

---

## Advanced installers (optional)

Use these only if your org already standardizes on Poetry or Conda. They are
**not** required for first success.

### Poetry

```bash
poetry new my-pipeline && cd my-pipeline
poetry add 'etlantic==0.40.0'
poetry run python -m etlantic --version
# poetry new leaves a non-empty tree — init needs --force (or an empty subdir):
poetry run python -m etlantic init --with-toml --force
```

### Conda / Mamba

```bash
conda create -n etlantic python=3.12 pip -y
conda activate etlantic
python -m pip install 'etlantic==0.40.0'
python -m etlantic --version
```

---

## Optional engine plugins
Core never installs Polars, Pandas, database drivers, or PySpark. Add engines
explicitly and **match the core minor** (`0.40.0` with `0.40.0`).

**Primary install (separate packages):**

```bash
python -m pip install 'etlantic-polars==0.40.0'     # dataframe + Polars portable compiler
python -m pip install 'etlantic-pandas==0.40.0'     # dataframe + Pandas portable compiler
python -m pip install 'etlantic-sql==0.40.0'        # SQL plugin (SQLite + PostgreSQL Tier A)
python -m pip install 'etlantic-pyspark==0.40.0'    # PySpark plugin + portable compiler
python -m pip install 'etlantic-airflow==0.40.0'    # Airflow DAG compiler
python -m pip install 'etlantic-prefect==0.40.0'    # Prefect direct-execution (local MVP)
python -m pip install 'etlantic-keyring==0.40.0'    # OS keyring secret provider
python -m pip install 'etlantic-sqlmodel==0.40.0'   # SQLModel bridge helpers
python -m pip install 'medallantic==0.40.0' # SparkForge → ETLantic IR adapter
```

**Equivalent extras** (same packages, same pins):

```bash
python -m pip install 'etlantic[polars]==0.40.0'
python -m pip install 'etlantic[pandas]==0.40.0'
python -m pip install 'etlantic[dataframes]==0.40.0'   # polars + pandas
python -m pip install 'etlantic[sql]==0.40.0'          # alias: [postgresql]
python -m pip install 'etlantic[pyspark]==0.40.0'      # alias: [spark]
python -m pip install 'etlantic[airflow]==0.40.0'
python -m pip install 'etlantic[prefect]==0.40.0'
# Experimental Gate B stub (not graduated; not recommended):
python -m pip install 'etlantic[datafusion]==0.40.0'
```

Also available: `[keyring]`, `[sqlmodel]`, `[medallantic]`, `[fastapi]`,
`[otel]`, `[arrow]`.

```bash
python -m pip install 'etlantic-fastapi==0.40.0'   # dual surface: CP1 ETLanticAPI + thin create_reference_app (non-CP); CP1 ≠ multi-tenant GA
# or: python -m pip install 'etlantic[fastapi]==0.40.0'
```

Verify discovery after installing Polars:

```bash
python -m etlantic plugin list --kind transform_compiler --format json
```

### PySpark / JVM

`etlantic-pyspark` requires a working JVM (`JAVA_HOME`). If Spark fails at
import or session start, see [Troubleshooting](TROUBLESHOOTING.md).

### SQL connection URL

SQLite and PostgreSQL have been Tier A dialects since 0.34. The URL below is
a **placeholder**—do not commit real credentials:

```bash
export ETLANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/etlantic
# or local SQLite:
export ETLANTIC_SQL_URL=sqlite+pysqlite:///:memory:
```

Select SQL with `Profile(sql_engine="sql")`. PostgreSQL advertises
`sql_merge=True` (`INSERT … ON CONFLICT`). SQLite remains
`sql_merge=False` and fails closed if merge is required. Select Spark with
`Profile(spark_engine="pyspark")`.

Airflow: `etlantic compile … --target airflow` via `etlantic-airflow` (compile
only; does not install Apache Airflow). Prefect: direct execution via
`etlantic-prefect` (local MVP; deployment/serve remain future).

## Upgrade

Prefer the [Upgrade hub](UPGRADE.md). Quick pin:

```bash
python -m pip install --upgrade 'etlantic==0.40.0'
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

Install from source only when contributing or testing unreleased changes.
Day-0 evaluation should use the PyPI pin above.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'git+https://github.com/eddiethedean/etlantic.git@v0.40.0'
python -m etlantic --version
```

Optional plugins from the same monorepo (after cloning):

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
git checkout v0.40.0
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
