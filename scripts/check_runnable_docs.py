"""Validate the source files promised by runnable documentation pages."""

from __future__ import annotations

import py_compile
from pathlib import Path

ROOT = Path(__file__).parents[1]

RUNNABLE_PAGES = {
    "docs/06_EXECUTION/FILE_STORAGE_TUTORIAL.md": "examples/file_storage.py",
    "docs/06_EXECUTION/POLARS_TUTORIAL.md": "examples/dataframe_parity.py",
    "docs/06_EXECUTION/PANDAS_TUTORIAL.md": "examples/dataframe_parity.py",
    "docs/06_EXECUTION/SQL_TUTORIAL.md": "examples/sql_to_sql.py",
    "docs/06_EXECUTION/SQL_HELLO_PYPI.md": "examples/sql_hello_pypi.py",
    "docs/06_EXECUTION/PYSPARK_TUTORIAL.md": "examples/pyspark_local.py",
    "docs/06_EXECUTION/AIRFLOW_TUTORIAL.md": "examples/airflow_compile.py",
    "docs/09_EXAMPLES/PREFECT_RUN.md": "examples/prefect_run.py",
    "docs/09_EXAMPLES/AIRFLOW_COMPILE.md": "examples/airflow_compile.py",
    "docs/09_EXAMPLES/PORTABLE_TRANSFORMS.md": "examples/portable_polars_kernel.py",
    "docs/09_EXAMPLES/PRODUCTION_SAMPLE.md": "examples/sample_pilot/run_pilot.py",
    "docs/05_PIPELINES/PROGRAMMATIC_AUTHORING.md": "examples/pipeline_definition_json.py",
}


def main() -> None:
    for page_name, source_name in RUNNABLE_PAGES.items():
        page = ROOT / page_name
        source = ROOT / source_name
        if not page.exists():
            raise SystemExit(f"Runnable documentation page is missing: {page_name}")
        text = page.read_text(encoding="utf-8")
        if "Status: Available" not in text:
            raise SystemExit(f"Runnable page lacks Available status: {page_name}")
        if source.name not in text:
            raise SystemExit(
                f"Runnable page does not name companion {source.name}: {page_name}"
            )
        if not source.exists():
            raise SystemExit(f"Runnable companion is missing: {source_name}")
        py_compile.compile(str(source), doraise=True)

    print(f"Validated {len(RUNNABLE_PAGES)} runnable documentation companions.")


if __name__ == "__main__":
    main()
