#!/usr/bin/env python3
"""Verify optional-package API docs include mkdocstrings ::: directives."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_MODULES = (
    "etlantic_polars",
    "etlantic_pandas",
    "etlantic_sql",
    "etlantic_pyspark",
    "etlantic_airflow",
    "etlantic_prefect",
    "etlantic_keyring",
    "etlantic_sqlmodel",
    "etlantic_datafusion",
    "etlantic_fastapi",
    "medallantic",
)

REQUIRED_PACKAGE_PAGES = tuple(
    ROOT / "docs/10_REFERENCE/api_optional" / f"{mod}.md" for mod in REQUIRED_MODULES
)

CANDIDATE_DOCS = (
    ROOT / "docs/10_REFERENCE/API_OPTIONAL_PACKAGES.md",
    ROOT / "docs/10_REFERENCE/OPTIONAL_PACKAGES.md",
    *REQUIRED_PACKAGE_PAGES,
)


def _directive_present(text: str, module: str) -> bool:
    needle = f"::: {module}"
    for line in text.splitlines():
        if line.strip().startswith(needle):
            remainder = line.strip()[len(needle) :]
            if remainder == "" or remainder[0].isspace():
                return True
    return False


def main() -> int:
    missing_pages = [p for p in REQUIRED_PACKAGE_PAGES if not p.exists()]
    if missing_pages:
        print(
            "check_api_docs_coverage: missing per-package API pages: "
            + ", ".join(str(p.relative_to(ROOT)) for p in missing_pages),
            file=sys.stderr,
        )
        return 1

    existing = [path for path in CANDIDATE_DOCS if path.exists()]
    if not existing:
        print(
            "check_api_docs_coverage: missing both "
            "API_OPTIONAL_PACKAGES.md and OPTIONAL_PACKAGES.md",
            file=sys.stderr,
        )
        return 1

    combined = "\n".join(path.read_text(encoding="utf-8") for path in existing)
    missing = [
        module
        for module in REQUIRED_MODULES
        if not _directive_present(combined, module)
    ]
    if missing:
        searched = ", ".join(path.name for path in existing)
        print(
            "check_api_docs_coverage: missing mkdocstrings ::: directives for: "
            + ", ".join(missing)
            + f" (searched {searched})",
            file=sys.stderr,
        )
        return 1

    print("check_api_docs_coverage: ok (" + ", ".join(REQUIRED_MODULES) + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
