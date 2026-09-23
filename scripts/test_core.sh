#!/usr/bin/env bash
# Run the strict type-check and core (non-plugin) pytest baselines used by CI
# and CONTRIBUTING.md.
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/check_pyright.sh
uv run pytest -q -m "not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion" "$@"
