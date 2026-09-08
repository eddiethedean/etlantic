#!/usr/bin/env python3
"""Fail-closed validation for the checked-in 0.50 portable contract artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/11_DEVELOPMENT/evidence/portable_0_50"
REQUIRED = {
    "portable_evidence_index_0_50.json",
    "portable_baseline_contract_0_50.json",
    "portable_requirement_support_0_50.json",
    "portable_pushdown_contract_0_50.json",
    "portable_claim_coverage_0_50.json",
    "portable_local_conformance_0_50.json",
    "portable_polars_conformance_0_50.json",
    "portable_pandas_conformance_0_50.json",
    "portable_sql_conformance_0_50.json",
    "portable_pyspark_conformance_0_50.json",
    "portable_datafusion_conformance_0_50.json",
    "portable_duckdb_pushdown_0_50.json",
    "portable_cross_engine_0_50.json",
    "portable_canonical_pipeline_0_50.json",
    "portable_adaptive_handoff_0_50.json",
    "portable_dependency_security_0_50.json",
    "FINDINGS_0_50.md",
    "MIGRATION_0_49_TO_0_50.md",
    "WHATS_NEW_0_50.md",
}


def main() -> int:
    missing = sorted(name for name in REQUIRED if not (EVIDENCE / name).is_file())
    if missing:
        raise SystemExit("missing 0.50 contract artifacts: " + ", ".join(missing))
    baseline = json.loads(
        (EVIDENCE / "portable_baseline_contract_0_50.json").read_text()
    )
    if baseline.get("schema") != "etlantic.portable-baseline/1":
        raise SystemExit("invalid baseline schema")
    manifest = baseline.get("manifest") or {}
    if len(manifest.get("actions", [])) != 12:
        raise SystemExit("baseline must enumerate exactly 12 actions")
    if (
        len(manifest.get("scalar_functions", [])) != 23
        or len(manifest.get("aggregate_functions", [])) != 7
    ):
        raise SystemExit("baseline function inventory is incomplete")
    index = json.loads((EVIDENCE / "portable_evidence_index_0_50.json").read_text())
    listed = set(index.get("artifacts") or [])
    if listed != REQUIRED - {"portable_evidence_index_0_50.json"}:
        raise SystemExit("evidence index does not enumerate the frozen artifact set")
    if len(index.get("artifacts") or []) != len(listed):
        raise SystemExit("evidence index contains duplicate artifacts")
    if any(Path(name).is_absolute() or ".." in Path(name).parts for name in listed):
        raise SystemExit("evidence index contains an absolute or escaping path")
    digests = index.get("digests")
    if not isinstance(digests, dict) or set(digests) != listed:
        raise SystemExit("evidence index must provide one digest per artifact")
    for name in REQUIRED - {"portable_evidence_index_0_50.json"}:
        artifact = EVIDENCE / name
        if artifact.suffix == ".json":
            payload = json.loads(artifact.read_text())
            if (
                not payload.get("schema")
                or "repository_commit" not in payload
                or "result" not in payload
            ):
                raise SystemExit(f"artifact metadata is incomplete: {name}")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digests.get(name) != digest:
            raise SystemExit(f"evidence digest mismatch: {name}")
    print("0.50 evidence artifact set is complete and structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
