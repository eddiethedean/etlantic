# Installing ETLantic 0.34.0

!!! tip "PyPI user vs contributor clone"
    | Audience | Path |
    |---|---|
    | **First-time / PyPI** | Sections below through [Quickstart](QUICKSTART.md). Use `python -m pip` and `python -m etlantic`. |
    | **Contributor / monorepo** | Skip to [Repository checkout](#repository-checkout-contributors) and use `uv sync`. Do not mix `uv run` example commands with a pip-only install. |

!!! warning "Install truth (0.34 docs train)"
    These docs describe **ETLantic 0.34.0**. As of this writing the latest
    **PyPI** wheel may still be **0.33.0**. Day-0 evaluation should install
    from `main` until `pip install etlantic==0.34.0` succeeds:

    ```bash
    # Day-0 evaluation from main (use until 0.34.0 is on PyPI)
    python -m pip install 'git+https://github.com/eddiethedean/etlantic.git@main'
    python -m etlantic --version   # expect 0.34.0

    # After the 0.34.0 PyPI release
    python -m pip install 'etlantic==0.34.0'
    ```

    Wrong-version recovery: uninstall, recreate the venv, then reinstall with
    the command that matches your target (`main` or the PyPI pin).

## Requirements

- Python 3.11, 3.12, or 3.13
- A virtual environment (strongly recommended)

## Install core (Day-0 — 2 minutes)

Use a virtual environment. Prefer `python -m pip` and `python -m etlantic` so
the interpreter you intend is the one that runs. Lead with the `main` install
until PyPI publishes `0.34.0`.

### pip (recommended)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
# Until 0.34.0 is on PyPI:
python -m pip install 'git+https://github.com/eddiethedean/etlantic.git@main'
# After publish: python -m pip install 'etlantic==0.34.0'
python -m etlantic --version
```

### uv (no existing project)

```bash
uv venv
source .venv/bin/activate
# Until 0.34.0 is on PyPI:
uv pip install 'git+https://github.com/eddiethedean/etlantic.git@main'
# After publish: uv pip install 'etlantic==0.34.0'
python -m etlantic --version
```

If you already have a uv project (`pyproject.toml`) **and** `0.34.0` is on
PyPI, you may use `uv add 'etlantic==0.34.0'` instead. Create an **empty
subdirectory** for `python -m etlantic init --with-toml`, or pass `--force` if
the directory is not empty. **`--force` can overwrite** existing `pipeline.py`
/ `pyproject.toml` scaffolding — prefer an empty subdirectory when unsure.

### Windows (pip)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.11 -m pip install --upgrade pip
# Until 0.34.0 is on PyPI:
py -3.11 -m pip install 'git+https://github.com/eddiethedean/etlantic.git@main'
# After publish: py -3.11 -m pip install 'etlantic==0.34.0'
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
# Until 0.34.0 is on PyPI, prefer pip/git into the Poetry venv, or:
poetry add 'git+https://github.com/eddiethedean/etlantic.git@main'
# After publish: poetry add 'etlantic==0.34.0'
poetry run python -m etlantic --version
# poetry new leaves a non-empty tree — init needs --force (or an empty subdir):
poetry run python -m etlantic init --with-toml --force
```

### Conda / Mamba

```bash
conda create -n etlantic python=3.12 pip -y
conda activate etlantic
# Until 0.34.0 is on PyPI:
python -m pip install 'git+https://github.com/eddiethedean/etlantic.git@main'
# After publish: python -m pip install 'etlantic==0.34.0'
python -m etlantic --version
```

---

## Optional engine plugins
Core never installs Polars, Pandas, database drivers, or PySpark. Add engines
explicitly and **match the core minor** (`0.34.0` with `0.34.0`).

**Primary install (separate packages):**

```bash
python -m pip install 'etlantic-polars==0.34.0'     # dataframe + Polars portable compiler
python -m pip install 'etlantic-pandas==0.34.0'     # dataframe + Pandas portable compiler
python -m pip install 'etlantic-sql==0.34.0'        # SQL plugin (SQLite + PostgreSQL Tier A)
python -m pip install 'etlantic-pyspark==0.34.0'    # PySpark plugin + portable compiler
python -m pip install 'etlantic-airflow==0.34.0'    # Airflow DAG compiler
python -m pip install 'etlantic-prefect==0.34.0'    # Prefect direct-execution (local MVP)
python -m pip install 'etlantic-keyring==0.34.0'    # OS keyring secret provider
python -m pip install 'etlantic-sqlmodel==0.34.0'   # SQLModel bridge helpers
python -m pip install 'medallantic==0.34.0' # SparkForge → ETLantic IR adapter
```

**Equivalent extras** (same packages, same pins):

```bash
python -m pip install 'etlantic[polars]==0.34.0'
python -m pip install 'etlantic[pandas]==0.34.0'
python -m pip install 'etlantic[dataframes]==0.34.0'   # polars + pandas
python -m pip install 'etlantic[sql]==0.34.0'          # alias: [postgresql]
python -m pip install 'etlantic[pyspark]==0.34.0'      # alias: [spark]
python -m pip install 'etlantic[airflow]==0.34.0'
python -m pip install 'etlantic[prefect]==0.34.0'
# Experimental Gate B stub (not graduated; not recommended):
python -m pip install 'etlantic[datafusion]==0.34.0'
```

Also available: `[keyring]`, `[sqlmodel]`, `[medallantic]`, `[fastapi]`,
`[otel]`, `[arrow]`.

```bash
python -m pip install 'etlantic-fastapi==0.34.0'   # thin authoring/service HTTP reference (shipped since 0.24; not the 0.40–0.44 control plane)
# or: python -m pip install 'etlantic[fastapi]==0.34.0'
```

Verify discovery after installing Polars:

```bash
python -m etlantic plugin list --kind transform_compiler --format json
```

### PySpark / JVM

`etlantic-pyspark` requires a working JVM (`JAVA_HOME`). If Spark fails at
import or session start, see [Troubleshooting](TROUBLESHOOTING.md).

### SQL connection URL

SQLite and PostgreSQL are Tier A dialects in 0.34. The PostgreSQL URL below is
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

Prefer the [Upgrade hub](UPGRADE.md). Quick pin (after PyPI publish):

```bash
python -m pip install --upgrade 'etlantic==0.34.0'
```

Until then, reinstall from `main` as in the install-truth warning above.

## Installation problems

See [Troubleshooting](TROUBLESHOOTING.md) for Python-version errors, core/plugin
minor skew, missing plugins, JVM issues, PATH/`etlantic` not found, and stale
virtual environments.

## Dependency philosophy

ETLantic keeps the core install small. Engines and orchestrators belong in
optional plugins. See [Dependency Strategy](../11_DEVELOPMENT/DEPENDENCY_STRATEGY.md).

---

## Install from source (optional)

Use a git checkout when you want mainline or editable monorepo plugins.
Until a `v0.34.0` tag/release is published, prefer `@main`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'git+https://github.com/eddiethedean/etlantic.git@main'
python -m etlantic --version
```

Optional plugins from the same monorepo (after cloning):

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
# After a release tag exists: git checkout v0.34.0
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
