#!/usr/bin/env python3
"""Validate the row-free 0.55 inference evidence manifest.

This command checks evidence shape and policy metadata without reading source
rows or changing qualification status. Use ``--run-focused`` to execute the
small review regression suite as an additional local gate.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/11_DEVELOPMENT/evidence/inference_0_55"
FORBIDDEN_KEY_TOKENS = (
    "row",
    "record",
    "sample",
    "payload",
    "sourcevalue",
    "providerdata",
)


def _key_kind(key: str) -> str | None:
    normalized = "".join(char for char in key.casefold() if char.isalnum())
    if normalized in {"rowfree", "rowsfree"}:
        return None
    if any(token in normalized for token in ("secret", "password", "credential", "authorization", "apikey", "token")):
        return "secret"
    if any(token in normalized for token in FORBIDDEN_KEY_TOKENS) or normalized in {"value", "values", "data"}:
        return "row"
    return None


def _check_row_free(value: Any, path: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            kind = _key_kind(str(key))
            if kind is not None:
                raise ValueError(f"{kind} evidence key is forbidden: {path}.{key}")
            _check_row_free(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_row_free(item, f"{path}[{index}]")


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    _check_row_free(payload, path.name)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-focused", action="store_true")
    args = parser.parse_args()
    index = _load(EVIDENCE / "index.json")
    matrix = _load(EVIDENCE / "capability_matrix.json")
    for artifact in sorted(EVIDENCE.glob("*.json")):
        _load(artifact)
    if index.get("schema") != "etlantic.inference-evidence/1":
        raise ValueError("unknown inference evidence schema")
    if index.get("phase") != "0.55" or index.get("qualified") is not False:
        raise ValueError("0.55 evidence must remain unqualified")
    if matrix.get("schema") != "etlantic.inference-capability-matrix/1":
        raise ValueError("unknown capability matrix schema")
    entries = matrix.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("capability matrix is empty")
    surfaces = {entry.get("surface") for entry in entries if isinstance(entry, dict)}
    required = {"records", "csv", "json", "pandas", "polars"}
    if not required <= surfaces:
        raise ValueError(f"missing required source surfaces: {sorted(required - surfaces)}")
    ledger = _load(EVIDENCE / "finding_ledger.json")
    findings = ledger.get("findings")
    if not isinstance(findings, list) or not findings:
        raise ValueError("finding ledger is empty")
    for finding in findings:
        if not isinstance(finding, dict) or not all(
            isinstance(finding.get(key), str) and finding.get(key)
            for key in ("id", "priority", "status", "code", "test", "gate")
        ):
            raise ValueError("finding ledger entries require id, priority, status, code, test, and gate")
    if args.run_focused:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests/inference"],
            cwd=ROOT,
            check=False,
        )
        return result.returncode
    print(json.dumps({"phase": "0.55", "status": "manifest-valid", "entries": len(entries)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
