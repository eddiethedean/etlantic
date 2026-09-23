#!/usr/bin/env bash
# Run the repository-wide strict Pyright gate used by local checks and CI.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python scripts/check_pyright_suppressions.py
uv run python scripts/check_pyright_strict.py
uv run pyright "$@"
