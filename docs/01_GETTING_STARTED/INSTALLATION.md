# Installing ETLantic 0.18.0

## Requirements

- Python 3.11, 3.12, or 3.13
- ContractModel (installed automatically with ETLantic)

## Install core (2 minutes)

Pin the published release for reproducible evaluation. Prefer `python -m pip`
so you use the interpreter you intend (any supported 3.11+):

```bash
python -m pip install --upgrade pip
python -m pip install 'etlantic==0.18.0'
python -m etlantic --version
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add 'etlantic==0.18.0'
uv run etlantic --version
```

```bash
python -c "import etlantic; print(etlantic.__version__)"
```

### Windows

```powershell
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install 'etlantic==0.18.0'
py -3.11 -m etlantic --version
```

## Next Step

Continue with [Quickstart](QUICKSTART.md). Optional engines and contributor
checkout are below—skip them until after first success.

---

## Optional engine plugins

Core never installs Polars, Pandas, database drivers, or PySpark. Add engines
explicitly and **match the core minor** (`0.18.0` with `0.18.0`).

**Primary install (separate packages):**

```bash
pip install 'etlantic-polars==0.18.0'     # dataframe + Polars portable compiler
pip install 'etlantic-pandas==0.18.0'     # dataframe + Pandas portable compiler
pip install 'etlantic-sql==0.18.0'        # PostgreSQL SQL reference plugin
pip install 'etlantic-pyspark==0.18.0'    # PySpark plugin + portable compiler
pip install 'etlantic-airflow==0.18.0'    # Airflow DAG compiler
pip install 'etlantic-prefect==0.18.0'    # Prefect direct-execution scheduler
pip install 'etlantic-keyring==0.18.0'    # OS keyring secret provider
pip install 'etlantic-sqlmodel==0.18.0'   # SQLModel bridge helpers
pip install 'etlantic-sparkforge==0.18.0' # SparkForge → ETLantic IR adapter
```

**Equivalent extras** (same packages, same pins):

```bash
pip install 'etlantic[polars]==0.18.0'
pip install 'etlantic[pandas]==0.18.0'
pip install 'etlantic[dataframes]==0.18.0'   # polars + pandas
pip install 'etlantic[sql]==0.18.0'          # alias: [postgresql]
pip install 'etlantic[pyspark]==0.18.0'      # alias: [spark]
pip install 'etlantic[airflow]==0.18.0'
pip install 'etlantic[prefect]==0.18.0'
```

Also available: `[keyring]`, `[sqlmodel]`, `[sparkforge]`, `[otel]`, `[arrow]`.

Verify discovery after installing Polars:

```bash
etlantic plugin list --kind transform_compiler --format json
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

Airflow: `etlantic compile … --target airflow` via `etlantic-airflow`.
Prefect: direct execution via `etlantic-prefect` (local MVP). Dagster remains
future.

## Repository checkout (contributors)

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync
uv run python -c "import etlantic; print(etlantic.__version__)"
uv run python examples/quickstart.py
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
uv sync --group sparkforge
uv sync --group keyring
uv sync --group sqlmodel
```

### Editable install with pip (no uv)

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Upgrade

Prefer the [Upgrade hub](UPGRADE.md). Quick pin:

```bash
python -m pip install --upgrade 'etlantic==0.18.0'
```

## Development commands

| Command | Purpose |
|---|---|
| `uv sync` | Create/update `.venv` from `uv.lock` |
| `uv run pytest` | Run tests |
| `uv run ruff check .` | Lint |
| `uv run python scripts/check_docs.py` | Docs consistency gate |
| `uv run python scripts/build_docs.py` | Build docs (`--strict`) |
| `uv run mkdocs serve` | Preview docs locally |

## Repository layout

```text
pyproject.toml
uv.lock
src/etlantic/
packages/etlantic-polars/
packages/etlantic-pandas/
packages/etlantic-sql/
packages/etlantic-pyspark/
packages/etlantic-airflow/
packages/etlantic-prefect/
packages/etlantic-keyring/
packages/etlantic-sqlmodel/
packages/etlantic-sparkforge/
tests/
examples/
docs/
```

## Installation problems

See [Troubleshooting](TROUBLESHOOTING.md) for Python-version errors, core/plugin
minor skew, missing plugins, JVM issues, and stale virtual environments.

## Dependency philosophy

ETLantic keeps the core install small. Engines and orchestrators belong in
optional plugins. See [Dependency Strategy](../11_DEVELOPMENT/DEPENDENCY_STRATEGY.md).
