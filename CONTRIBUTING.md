# Contributing

Thank you for your interest in ETLantic.

Full contributor guidance lives in the documentation:

**[docs/11_DEVELOPMENT/CONTRIBUTING.md](docs/11_DEVELOPMENT/CONTRIBUTING.md)**

## Quick start

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync --locked
```

### Docs-only / minimal first PR

```bash
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_docs.py
uv run python scripts/check_agent_guidance.py
```

## CI-equivalent local checks

Baseline:

```bash
uv run ruff check .
uv run ruff format --check .
./scripts/test_core.sh
uv run python scripts/check_docs.py
uv run python scripts/check_agent_guidance.py
uv run python scripts/check_release.py
uv run python scripts/check_surface_inventory.py
uv run --group polars --group pandas --group sql --group pyspark --group datafusion python scripts/check_transform_compiler_drift.py
uv run etlantic validate examples/memory_customers.py:CustomerPipeline --format sarif > /tmp/etlantic.sarif
uv run python examples/memory_customers.py
uv run python scripts/build_docs.py
```

`./scripts/test_core.sh` runs the same non-plugin pytest marker expression CI uses for the core job.

Portable dataframe examples (requires the dataframes group):

```bash
uv sync --locked --group dataframes
uv run python examples/portable_polars_kernel.py
uv run python examples/portable_pandas_kernel.py
```

Prefect direct execution (optional):

```bash
uv sync --locked --group prefect
uv run pytest -q tests/prefect -m prefect
uv run python examples/prefect_run.py
```

SparkForge (optional):

```bash
uv sync --locked --group sparkforge
uv run pytest -q tests/sparkforge -m sparkforge
```

Fork the repository, branch from `main`, and open a pull request against
`main`. Please report security issues privately per [SECURITY.md](SECURITY.md).
Do not open public issues that include credentials or production data.

Participation is governed by the
[Code of Conduct](docs/11_DEVELOPMENT/CODE_OF_CONDUCT.md), and project decisions
follow the [Governance guide](docs/11_DEVELOPMENT/GOVERNANCE.md). Maintainers
are listed in [MAINTAINERS.md](MAINTAINERS.md).
