"""Validate the source files promised by runnable documentation pages."""

from __future__ import annotations

import py_compile
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parents[1]

EXPECTED_OUTPUT = re.compile(r"(?ms)^## Expected output\s*$\n(?P<body>.*?)(?=^## |\Z)")
OUTPUT_FENCE = re.compile(r"(?ms)^```(?:console|json|text|yaml)\s*$.*?^```\s*$")


@dataclass(frozen=True, slots=True)
class RunnableEntry:
    """One documentation page with a companion script."""

    page: str
    companion: str
    syntax_checked: bool = True
    executed_in_ci: str | None = None
    external_dependency: str | None = None
    illustrative: bool = False


# executed_in_ci names the checks.yml job (or step group) that runs the companion.
RUNNABLE_ENTRIES: tuple[RunnableEntry, ...] = (
    RunnableEntry(
        "docs/06_EXECUTION/FILE_STORAGE_TUTORIAL.md",
        "examples/file_storage.py",
        executed_in_ci=None,
    ),
    RunnableEntry(
        "docs/06_EXECUTION/POLARS_TUTORIAL.md",
        "examples/dataframe_parity.py",
        executed_in_ci="dataframes",
        external_dependency="polars",
    ),
    RunnableEntry(
        "docs/06_EXECUTION/PANDAS_TUTORIAL.md",
        "examples/dataframe_parity.py",
        executed_in_ci="dataframes",
        external_dependency="pandas",
    ),
    RunnableEntry(
        "docs/06_EXECUTION/SQL_TUTORIAL.md",
        "examples/sql_to_sql.py",
        executed_in_ci="sql",
        external_dependency="sql",
    ),
    RunnableEntry(
        "docs/06_EXECUTION/SQL_HELLO_PYPI.md",
        "examples/sql_hello_pypi.py",
        executed_in_ci=None,
        external_dependency="sql",
    ),
    RunnableEntry(
        "docs/06_EXECUTION/PYSPARK_TUTORIAL.md",
        "examples/pyspark_local.py",
        executed_in_ci="spark",
        external_dependency="pyspark",
    ),
    RunnableEntry(
        "docs/06_EXECUTION/AIRFLOW_TUTORIAL.md",
        "examples/airflow_compile.py",
        executed_in_ci="airflow",
        external_dependency="airflow",
    ),
    RunnableEntry(
        "docs/09_EXAMPLES/PREFECT_RUN.md",
        "examples/prefect_run.py",
        executed_in_ci="prefect",
        external_dependency="prefect",
    ),
    RunnableEntry(
        "docs/09_EXAMPLES/AIRFLOW_COMPILE.md",
        "examples/airflow_compile.py",
        executed_in_ci="airflow",
        external_dependency="airflow",
    ),
    RunnableEntry(
        "docs/09_EXAMPLES/PORTABLE_TRANSFORMS.md",
        "examples/portable_polars_kernel.py",
        executed_in_ci=None,
        external_dependency="polars",
    ),
    RunnableEntry(
        "docs/09_EXAMPLES/PRODUCTION_SAMPLE.md",
        "examples/sample_pilot/run_pilot.py",
        executed_in_ci=None,
    ),
    RunnableEntry(
        "docs/05_PIPELINES/PROGRAMMATIC_AUTHORING.md",
        "examples/pipeline_definition_json.py",
        executed_in_ci="checks",
    ),
    RunnableEntry(
        "docs/09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md",
        "examples/interchange_polars_pandas.py",
        executed_in_ci="portable-differentials",
        external_dependency="dataframes",
    ),
)


def main() -> None:
    for entry in RUNNABLE_ENTRIES:
        page = ROOT / entry.page
        source = ROOT / entry.companion
        if not page.exists():
            raise SystemExit(f"Runnable documentation page is missing: {entry.page}")
        text = page.read_text(encoding="utf-8")
        if entry.illustrative:
            if "illustrative" not in text.lower():
                raise SystemExit(
                    f"Illustrative page must say so explicitly: {entry.page}"
                )
            continue
        if "Status: Available" not in text:
            raise SystemExit(f"Runnable page lacks Available status: {entry.page}")
        if source.name not in text:
            raise SystemExit(
                f"Runnable page does not name companion {source.name}: {entry.page}"
            )
        output_section = EXPECTED_OUTPUT.search(text)
        if output_section is None:
            raise SystemExit(
                f"Runnable page lacks an 'Expected output' section: {entry.page}"
            )
        if not OUTPUT_FENCE.search(output_section.group("body")):
            raise SystemExit(
                f"Runnable page lacks a fenced output example: {entry.page}"
            )
        if not source.exists():
            raise SystemExit(f"Runnable companion is missing: {entry.companion}")
        if entry.syntax_checked:
            py_compile.compile(str(source), doraise=True)

    executed = sum(1 for e in RUNNABLE_ENTRIES if e.executed_in_ci)
    print(
        f"Validated {len(RUNNABLE_ENTRIES)} runnable documentation companions "
        f"({executed} with executed_in_ci)."
    )


if __name__ == "__main__":
    main()
