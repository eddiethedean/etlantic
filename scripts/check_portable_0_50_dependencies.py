#!/usr/bin/env python3
"""Build and import every qualified portable backend in isolated environments."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    "etlantic": "etlantic",
    "etlantic-polars": "etlantic_polars",
    "etlantic-pandas": "etlantic_pandas",
    "etlantic-sql": "etlantic_sql",
    "etlantic-pyspark": "etlantic_pyspark",
    "etlantic-datafusion": "etlantic_datafusion",
    "etlantic-duckdb": "etlantic_duckdb",
}


def _run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="etlantic-0-50-dependencies-") as temp:
        root = Path(temp)
        wheels = root / "wheels"
        wheels.mkdir()
        for package in PACKAGES:
            _run(
                "uv", "build", "--package", package, "--wheel", "--out-dir", str(wheels)
            )

        for package, module in PACKAGES.items():
            environment = root / package
            _run("uv", "venv", "--python", sys.executable, str(environment))
            python = environment / (
                "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
            )
            _run(
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--find-links",
                str(wheels),
                package,
            )
            _run(str(python), "-c", f"import {module}; print({module}.__name__)")
            if package == "etlantic":
                _run(
                    str(python),
                    str(ROOT / "scripts/run_portable_0_50_canonical.py"),
                    "--engines",
                    "local",
                )
    print(
        "isolated wheel build and import checks passed for all seven portable engines"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
