# Installation

Pipelantic 0.4 provides the typed modeling kernel, contract interoperability
(ODCS/DTCS/DPCS), multi-phase validation, profiles, deterministic planning,
and a local runtime that executes plans with Python callables, in-memory
artifacts, and stdlib JSON/CSV bindings. Dataframe/SQL/Spark plugins arrive
in later milestones.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) for project and dependency management
- ContractModel as a companion package (installed automatically)

## Development Setup

```bash
git clone https://github.com/eddiethedean/pipelantic.git
cd pipelantic
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv sync` installs runtime dependencies, the editable package, and the `dev`
group (pytest, ruff). The lockfile `uv.lock` pins exact versions.

### Common commands

| Command | Purpose |
|---|---|
| `uv sync` | Create/update `.venv` from `uv.lock` |
| `uv lock` | Refresh the lockfile after dependency changes |
| `uv run pytest` | Run tests |
| `uv run ruff check .` | Lint |
| `uv run ruff check --fix .` | Lint and apply safe fixes |
| `uv run ruff format .` | Format |

## Repository Layout

```text
pyproject.toml
uv.lock
.python-version
src/pipelantic/
tests/
docs/
```

## Verification

```bash
uv run python -c "import pipelantic; print(pipelantic.__version__)"
```

## User Installation

```bash
pip install pipelantic
# or
uv add pipelantic
```

Backend plugins remain independently installable and are not required by the
core package.

## Dependency Philosophy

Pipelantic keeps the core install small. Dataframe engines, orchestrators,
and storage clients belong in optional plugins—not the base package.

See [Dependency Strategy](../11_DEVELOPMENT/DEPENDENCY_STRATEGY.md) for the
full dependency policy.

## Next Step

Continue with [Quickstart](QUICKSTART.md) or [First Pipeline](FIRST_PIPELINE.md).
