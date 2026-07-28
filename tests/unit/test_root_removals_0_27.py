#!/usr/bin/env python3
"""Tests for 0.27 root alias removals and import hygiene."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import etlantic
from etlantic import _REMOVED_0_27

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (ROOT / "tests", ROOT / "examples")


@pytest.mark.parametrize("name", sorted(_REMOVED_0_27))
def test_removed_root_alias_raises(name: str) -> None:
    with pytest.raises(
        AttributeError, match=r"removed from the etlantic root in 0\.27\.0"
    ):
        getattr(etlantic, name)


def _names_imported_from_etlantic(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "etlantic":
            for alias in node.names:
                if alias.name != "*":
                    found.add(alias.name)
    return found


def test_tests_and_examples_do_not_import_removed_root_symbols() -> None:
    removed = set(_REMOVED_0_27)
    violations: list[str] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if path.name in {
                "test_root_removals_0_26.py",
                "test_root_removals_0_27.py",
            }:
                continue
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, SyntaxError):
                continue
            bad = _names_imported_from_etlantic(tree) & removed
            if bad:
                rel = path.relative_to(ROOT)
                violations.append(f"{rel}: {sorted(bad)}")
    assert not violations, (
        "tests/examples still import 0.27-removed root symbols from etlantic:\n"
        + "\n".join(violations)
    )
