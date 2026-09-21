#!/usr/bin/env python3
"""Validate the row-free 0.55 inference evidence manifest.

This command checks evidence shape and policy metadata without reading source
rows or changing qualification status. Use ``--run-focused`` to execute the
small review regression suite as an additional local gate.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/11_DEVELOPMENT/evidence/inference_0_55"
FORBIDDEN_KEYS = {
    "row",
    "rows",
    "record",
    "records",
    "sample",
    "samples",
    "samplerow",
    "samplerows",
    "sourcevalue",
    "sourcevalues",
    "value",
    "values",
    "data",
    "body",
    "content",
    "payload",
    "providerpayload",
    "providerdata",
}


def _key_kind(key: str) -> str | None:
    normalized = "".join(char for char in key.casefold() if char.isalnum())
    if normalized in {"rowfree", "rowsfree"}:
        return None
    if any(
        token in normalized
        for token in (
            "secret",
            "password",
            "credential",
            "authorization",
            "apikey",
            "token",
        )
    ):
        return "secret"
    if normalized in FORBIDDEN_KEYS:
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
    elif isinstance(value, str) and re.search(
        r"(?:^|[\s=])/(?:Users|home|tmp|var|Volumes)/", value
    ):
        raise ValueError(f"absolute path leaked into evidence: {path}")


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    _check_row_free(payload, path.name)
    return payload


def _check_generated_payloads() -> None:
    """Exercise public serialization paths and scan their actual payloads."""
    sys.path.insert(0, str(ROOT / "src"))
    import etlantic as etl
    from etlantic.schema_drift import json_safe_metadata

    result = etl.infer_records([{"id": 1}], identity="evidence-fixture")
    target_dataset = etl.from_records_for_target(
        [{"id": "1"}],
        {
            "revision": "evidence-r1",
            "capabilities": {"write_modes": ["append"]},
            "fields": [{"name": "id", "type": "integer"}],
        },
        name="evidence-fixture",
    )
    for name, payload in (
        ("inference observation", result.to_dict()),
        ("target observation", target_dataset.observation.to_dict()),
        ("pipeline definition", target_dataset.definition().to_dict()),
    ):
        try:
            json.dumps(payload, sort_keys=True)
        except TypeError as exc:
            raise ValueError(f"{name} is not JSON serializable") from exc
        _check_row_free(payload, name)
    safe = json_safe_metadata(
        {
            "context": {"record_hint": "alice@example.com", "source_value": 42},
            "identity": "/Users/alice/private/events",
        }
    )
    encoded = json.dumps(safe, sort_keys=True)
    if "alice@example.com" in encoded or "/Users/alice" in encoded:
        raise ValueError("shared metadata serializer retained sensitive fixture data")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-focused", action="store_true")
    args = parser.parse_args()
    index = _load(EVIDENCE / "index.json")
    matrix = _load(EVIDENCE / "capability_matrix.json")
    artifact_names = index.get("artifacts")
    if not isinstance(artifact_names, list) or not artifact_names:
        raise ValueError("evidence index must declare artifacts")
    for artifact_name in artifact_names:
        if (
            not isinstance(artifact_name, str)
            or Path(artifact_name).name != artifact_name
        ):
            raise ValueError("evidence artifact names must be local JSON filenames")
        artifact = EVIDENCE / artifact_name
        if artifact.suffix != ".json" or not artifact.is_file():
            raise ValueError(f"missing declared evidence artifact: {artifact_name}")
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
    for entry in entries:
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(key), str) and entry.get(key)
            for key in ("surface", "kind", "state")
        ):
            raise ValueError(
                "capability matrix entries require surface, kind, and state"
            )
        if entry.get("state", "").startswith("pending"):
            if entry.get("evidence") is not None:
                raise ValueError("pending matrix entries cannot claim evidence")
        elif not isinstance(entry.get("evidence"), str) or not entry.get("evidence"):
            raise ValueError("implemented matrix entries require evidence")
    surfaces = {entry.get("surface") for entry in entries if isinstance(entry, dict)}
    required = {"records", "csv", "json", "pandas", "polars"}
    if not required <= surfaces:
        raise ValueError(
            f"missing required source surfaces: {sorted(required - surfaces)}"
        )
    ledger = _load(EVIDENCE / "finding_ledger.json")
    findings = ledger.get("findings")
    if not isinstance(findings, list) or not findings:
        raise ValueError("finding ledger is empty")
    for finding in findings:
        if not isinstance(finding, dict) or not all(
            isinstance(finding.get(key), str) and finding.get(key)
            for key in ("id", "priority", "status", "code", "test", "gate")
        ):
            raise ValueError(
                "finding ledger entries require id, priority, status, code, test, and gate"
            )
        if not all(
            isinstance(finding.get(key), str) and finding.get(key)
            for key in ("implementation_commit", "evidence_artifact")
        ):
            raise ValueError(
                "finding ledger entries require implementation_commit and evidence_artifact"
            )
        evidence_path = ROOT / finding["evidence_artifact"]
        if not evidence_path.is_file() or evidence_path.suffix != ".json":
            raise ValueError(
                f"finding evidence artifact is missing: {finding['evidence_artifact']}"
            )
    required_findings = index.get("required_findings")
    finding_ids = {finding["id"] for finding in findings if isinstance(finding, dict)}
    if not isinstance(required_findings, list) or not required_findings:
        raise ValueError("evidence index must declare required findings")
    missing_findings = set(required_findings) - finding_ids
    if missing_findings:
        raise ValueError(
            f"finding ledger is missing required blockers: {sorted(missing_findings)}"
        )
    required_gates = set(index.get("required_gates") or ())
    if not required_gates:
        raise ValueError("evidence index must declare required gates")
    if any(
        finding["gate"] not in required_gates
        for finding in findings
        if isinstance(finding, dict)
    ):
        raise ValueError("finding ledger references an undeclared gate")
    _check_generated_payloads()
    if args.run_focused:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests/inference"],
            cwd=ROOT,
            check=False,
        )
        return result.returncode
    print(
        json.dumps(
            {"phase": "0.55", "status": "manifest-valid", "entries": len(entries)}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
