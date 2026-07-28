#!/usr/bin/env python3
"""Fail when tests/ or examples/ import removed root symbols from etlantic."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (ROOT / "tests", ROOT / "examples")
SKIP_FILES = {"test_root_removals_0_26.py", "test_root_removals_0_27.py"}


def _load_removed_names() -> set[str]:
    sys.path.insert(0, str(ROOT / "src"))
    from etlantic import _REMOVED_0_26, _REMOVED_0_27

    return set(_REMOVED_0_26) | set(_REMOVED_0_27)


def _names_imported_from_etlantic(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "etlantic":
            for alias in node.names:
                if alias.name != "*":
                    found.add(alias.name)
    return found


def main() -> int:
    removed = _load_removed_names()
    violations: list[str] = []
    parse_failures: list[str] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if path.name in SKIP_FILES:
                continue
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, SyntaxError) as exc:
                rel = path.relative_to(ROOT)
                parse_failures.append(f"{rel}: {exc}")
                continue
            bad = _names_imported_from_etlantic(tree) & removed
            if bad:
                rel = path.relative_to(ROOT)
                violations.append(f"{rel}: {sorted(bad)}")
    if parse_failures:
        print("Removed root import guard FAILED (unparseable files):")
        for item in parse_failures:
            print(f"  - {item}")
        return 1
    if violations:
        print("Removed root import guard FAILED:")
        for item in violations:
            print(f"  - {item}")
        return 1
    print("Removed root import guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
