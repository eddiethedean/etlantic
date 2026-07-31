#!/usr/bin/env python3
"""CI gate: 0.37 stable-foundation acceptance suite coverage (items 1-21).

Scans ``tests/stable_foundation/`` for ``test_sf_NN_`` functions and optionally
runs the suite. Item 15 (DataFusion) may be covered by an explicit N/A
disposition when the package is experimental / non-blocking.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = ROOT / "tests" / "stable_foundation"
TEST_PATTERN = re.compile(r"^test_sf_(\d+)_")

# Roadmap 0.37 stable-foundation acceptance suite (items 1-21).
ACCEPTANCE_ITEMS: dict[int, str] = {
    1: "Code-first pipeline generates ODCS, DTCS, and DPCS",
    2: "Contract-first pipeline normalizes to the same logical model",
    3: "Direct consumption of a prior step's named result",
    4: "Selective local execution with dependency closure and run report",
    5: "Equivalent Polars and Pandas transformations",
    6: "SQL-native pipeline with safe pushdown",
    7: "PySpark batch pipeline with lazy-region preservation",
    8: "Airflow compilation of the same logical plan",
    9: "Lifecycle, middleware, resource, callback, outbound, logging, redaction",
    10: "Plugin conformance and production trust-policy enforcement",
    11: "Security-boundary preservation through planning and optimization",
    12: "Representative SparkForge/Medallantic pipeline on ETLantic",
    13: "Portable definition across Polars/PySpark/Pandas/SQL intersection",
    14: "Gate A Polars↔Pandas Arrow interchange + diagnosed fallback",
    15: "DataFusion experimental / no foundation obligation",
    16: "Reject bad plans before plugin loading",
    17: "Allowlist authorize/reject without importing disallowed entry points",
    18: "Durable CLI workflow; later-process report; diagnostic identity",
    19: "Failure injection across boundaries without duplicate effects",
    20: "Third-party/public conformance without private core imports",
    21: "Application pipeline via public etlantic.testing only",
}

# Explicit non-blocking dispositions when a dedicated test is absent.
# Item 15 always has a test_sf_15_* that asserts experimental status or skips
# with the same disposition; this table documents the gate policy.
DISPOSITIONS: dict[int, str] = {
    15: (
        "N/A — DataFusion remains experimental; no stable-foundation "
        "compatibility obligation (EXIT_GATE_0_37 / ROADMAP item 15)"
    ),
}


def discover_sf_tests(suite_dir: Path = SUITE_DIR) -> dict[int, list[str]]:
    """AST-scan suite modules for ``test_sf_NN_*`` function definitions."""
    found: dict[int, list[str]] = {n: [] for n in ACCEPTANCE_ITEMS}
    if not suite_dir.is_dir():
        return found
    for path in sorted(suite_dir.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            match = TEST_PATTERN.match(node.name)
            if not match:
                continue
            number = int(match.group(1))
            if number in found:
                rel = path.relative_to(ROOT)
                found[number].append(f"{rel}::{node.name}")
    return found


def print_scorecard(found: dict[int, list[str]]) -> tuple[int, int]:
    """Print coverage scorecard; return (covered, total)."""
    covered = 0
    print("Stable-foundation acceptance scorecard (items 1-21)", flush=True)
    print("-" * 72, flush=True)
    for number, title in ACCEPTANCE_ITEMS.items():
        tests = found.get(number) or []
        disposition = DISPOSITIONS.get(number)
        if tests:
            status = "PASS"
            detail = ", ".join(tests)
            covered += 1
        elif disposition:
            status = "N/A"
            detail = disposition
            covered += 1
        else:
            status = "MISS"
            detail = f"no test_sf_{number:02d}_* and no disposition"
        print(f"  [{status:4}] {number:02d}  {title}", flush=True)
        print(f"           {detail}", flush=True)
    print("-" * 72, flush=True)
    print(f"Coverage: {covered}/{len(ACCEPTANCE_ITEMS)}", flush=True)
    return covered, len(ACCEPTANCE_ITEMS)


def run_pytest(extra_args: list[str] | None = None) -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        str(SUITE_DIR),
        *(extra_args or []),
    ]
    print("Running:", " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(completed.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory-only",
        action="store_true",
        help="Only AST-scan for coverage; do not run pytest",
    )
    parser.add_argument(
        "--pytest-arg",
        action="append",
        default=[],
        help="Extra argument forwarded to pytest (repeatable)",
    )
    args = parser.parse_args(argv)

    if not SUITE_DIR.is_dir():
        print(
            f"MISSING suite directory: {SUITE_DIR.relative_to(ROOT)}", file=sys.stderr
        )
        return 1

    found = discover_sf_tests()
    covered, total = print_scorecard(found)
    if covered < total:
        print("Stable-foundation gate FAILED: incomplete acceptance coverage")
        return 1

    if args.inventory_only:
        print("Inventory-only: coverage complete.")
        return 0

    code = run_pytest(args.pytest_arg)
    if code != 0:
        print("Stable-foundation gate FAILED: pytest reported failures")
        return code
    print("Stable-foundation gate passed (coverage + pytest).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
