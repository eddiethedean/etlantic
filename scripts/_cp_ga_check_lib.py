"""Shared helpers for CP-GA check_* scripts (0.43)."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

DOCS = Path(__file__).resolve().parents[1] / "docs" / "11_DEVELOPMENT"


def matrix_path(name: str) -> Path:
    return DOCS / name


def run_campaign_check(
    *,
    campaign: Callable[[], dict[str, Any]],
    matrix_filename: str,
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="CP-GA qualification campaign")
    parser.add_argument("--fake", action="store_true", default=True)
    parser.add_argument("--write-matrix", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = campaign()
    path = matrix_path(matrix_filename)
    if args.write_matrix:
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    elif path.exists():
        committed = json.loads(path.read_text(encoding="utf-8"))
        if json.dumps(committed, sort_keys=True) != json.dumps(result, sort_keys=True):
            print(
                "fail: committed matrix drift; re-run with --write-matrix and commit",
                flush=True,
            )
            if args.json:
                print(json.dumps({"committed": committed, "actual": result}, indent=2))
            return 1
    if args.json or args.write_matrix:
        print(json.dumps(result, indent=2))
    else:
        print("pass" if result.get("pass") else f"fail: {result.get('failed')}")
    return 0 if result.get("pass") else 1
