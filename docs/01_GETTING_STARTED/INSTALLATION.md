# Installation

Pipelantic 0.6.0 provides the typed modeling kernel, contract interoperability
(ODCS/DTCS/DPCS), multi-phase validation, profiles, deterministic planning,
a local runtime that executes plans with Python callables, in-memory
artifacts, and stdlib JSON/CSV bindings, plus optional Polars, Pandas, and
SQL plugins. Spark/orchestration plugins arrive in later milestones.

## Requirements

- Python 3.11 or newer
- ContractModel as a companion package (installed automatically with Pipelantic)

[uv](https://docs.astral.sh/uv/) is recommended for contributors and lockfile
workflows. Adopters can install with plain `pip`.

## User Installation

```bash
python3.11 -m pip install --upgrade pip
python3.11 -m pip install pipelantic
```

Or with uv:

```bash
uv add pipelantic
```

Verify the installed version matches these docs (0.6.0 or newer):

```bash
python -c "import pipelantic; print(pipelantic.__version__)"
```

### Optional dataframe and SQL plugins

Core never installs Polars, Pandas, or database drivers. Add engines
explicitly:

```bash
pip install pipelantic-polars    # Polars reference plugin
pip install pipelantic-pandas    # Pandas compatibility plugin
pip install pipelantic-sql       # PostgreSQL SQL reference plugin
# or extras:
pip install 'pipelantic[polars]'
pip install 'pipelantic[pandas]'
pip install 'pipelantic[dataframes]'
```

For SQL, set a connection URL:

```bash
export PIPELANTIC_SQL_URL=postgresql+psycopg://user:pass@localhost:5432/pipelantic
```

Spark and Airflow plugins are not part of 0.6. Do not install undocumented
extras expecting those backends.

## Upgrade

```bash
python -m pip install --upgrade pipelantic
# or
uv lock --upgrade-package pipelantic
```

Review the
[changelog](https://github.com/eddiethedean/pipelantic/blob/main/CHANGELOG.md)
and [Migration 0.5 → 0.6](../11_DEVELOPMENT/MIGRATION_0_5_TO_0_6.md) before
upgrading between 0.x releases because breaking changes remain possible.

## Development Setup

Contributors need [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/eddiethedean/pipelantic.git
cd pipelantic
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv sync` installs runtime dependencies, the editable package, and the `dev`
group (pytest, ruff, mkdocs). The lockfile `uv.lock` pins exact versions.

### Common commands

| Command | Purpose |
|---|---|
| `uv sync` | Create/update `.venv` from `uv.lock` |
| `uv sync --group dataframes` | Also install Polars and Pandas plugins |
| `uv lock` | Refresh the lockfile after dependency changes |
| `uv run pytest` | Run tests |
| `uv run ruff check .` | Lint |
| `uv run ruff format .` | Format |
| `uv run python scripts/check_docs.py` | Docs consistency gate |
| `uv run mkdocs build --strict` | Build the documentation site |

## Repository Layout

```text
pyproject.toml
uv.lock
.python-version
src/pipelantic/
packages/pipelantic-polars/
packages/pipelantic-pandas/
packages/pipelantic-sql/
tests/
examples/
docs/
```

## Installation Problems

See [Troubleshooting](TROUBLESHOOTING.md) for Python-version errors, version
mismatches with the docs, missing plugins, stale virtual environments, and
unsupported backend examples.

## Dependency Philosophy

Pipelantic keeps the core install small. Dataframe engines, SQL drivers,
orchestrators, and storage clients belong in optional plugins—not the base
package.

See [Dependency Strategy](../11_DEVELOPMENT/DEPENDENCY_STRATEGY.md) for the
full dependency policy.

## Next Step

Continue with [Capabilities](CAPABILITIES.md), then
[Quickstart](QUICKSTART.md).
