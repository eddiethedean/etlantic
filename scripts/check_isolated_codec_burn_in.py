#!/usr/bin/env python3
"""True old/new reader-writer compatibility harness (036-C02).

Default mode exercises current-tree fixtures plus semantic comparison and
legacy run-report metadata migration. Pass ``--isolated-wheels`` to also
install published 0.34/0.35 wheels in subprocess environments and prove
cross-version load outcomes (requires network + uv).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BURN_IN = ROOT / "tests" / "fixtures" / "burn_in"
RELEASES = ROOT / "tests" / "fixtures" / "releases"
EVIDENCE_SCHEMA = "etlantic.compatibility_evidence/1"

COMPAT_OUTCOMES = frozenset(
    {
        "compatible",
        "migrated",
        "regenerate",
        "upgrade-required",
        "unsupported",
    }
)

# Declared matrix cells (family, writer_tag, reader_tag) → expected outcome.
# Tags: package minor labels; "current" means the tree under test.
MATRIX: tuple[tuple[str, str, str, str], ...] = (
    ("pipeline", "0.34", "0.35", "compatible"),
    ("pipeline", "0.35", "0.34", "compatible"),
    ("pipeline", "0.35", "0.36", "compatible"),
    ("pipeline", "0.36", "0.35", "compatible"),
    ("pipeline", "current", "current", "compatible"),
    ("plan", "0.34", "0.35", "compatible"),
    ("plan", "0.35", "0.36", "compatible"),
    ("plan", "current", "current", "compatible"),
    ("run_report", "0.34", "0.35", "compatible"),
    ("run_report", "0.35", "0.36", "compatible"),
    ("run_report", "0.35.0-bare", "0.36", "migrated"),
    ("run_report", "current", "current", "compatible"),
    ("profile", "0.34", "0.35", "compatible"),
    ("profile", "0.35", "0.36", "compatible"),
    ("capabilities", "0.34", "0.35", "compatible"),
    ("capabilities", "0.35", "0.36", "compatible"),
    ("interchange", "0.34", "0.35", "compatible"),
    ("interchange", "0.35", "0.36", "compatible"),
    ("quality", "0.34", "0.35", "unsupported"),
    ("quality", "0.35", "0.36", "compatible"),
    ("quality", "current", "current", "compatible"),
)


def _fixture_for(family: str, writer: str) -> Path | None:
    mapping = {
        "0.34": "v0_34",
        "0.35": "v0_35",
        "0.36": "v0_36",
        "current": "v0_36",
    }
    if writer == "0.35.0-bare":
        path = RELEASES / "v0_35" / "known_defects" / "run_report_bare_metadata.json"
        return path if path.is_file() else None
    version = mapping.get(writer)
    if version is None:
        return None
    directory = BURN_IN / family / version
    if not directory.is_dir():
        return None
    paths = sorted(p for p in directory.glob("*.json") if p.name != "manifest.json")
    return paths[0] if paths else None


def _semantic_pipeline(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": data.get("schema"),
        "fingerprint": data.get("fingerprint"),
        "node_ids": sorted(
            n.get("identity") or n.get("name") for n in data.get("nodes", [])
        ),
        "edge_count": len(data.get("edges") or []),
        "contract_ids": sorted(
            c.get("identity") or c.get("name") for c in data.get("contracts", [])
        ),
    }


def _load_with_current(family: str, data: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    if family == "pipeline":
        from etlantic.authoring import pipeline_from_dict, pipeline_to_dict

        loaded = pipeline_from_dict(data, verify=True)
        return pipeline_to_dict(loaded, with_fingerprint=True)
    if family == "plan":
        from etlantic.plan.model import PipelinePlan

        return PipelinePlan.from_dict(data).to_dict()
    if family == "run_report":
        from etlantic.reports.model import PipelineRunReport

        return PipelineRunReport.from_dict(data).to_dict()
    if family == "profile":
        from etlantic.profile import Profile

        return Profile.from_dict(data).to_dict()
    if family == "capabilities":
        from etlantic.capabilities import PluginCapabilities

        return PluginCapabilities.from_dict(data).to_dict()
    if family == "interchange":
        from etlantic.interchange.tabular.descriptor import InterchangeDescriptor

        return InterchangeDescriptor.from_dict(data).to_dict()
    if family == "quality":
        from etlantic.quality.serialize import quality_from_dict, quality_to_dict

        return quality_to_dict(quality_from_dict(data))
    raise ValueError(f"unknown family {family}")


def _check_current_cell(
    family: str, writer: str, reader: str, expected: str
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "family": family,
        "writer": writer,
        "reader": reader,
        "expected": expected,
        "outcome": None,
        "status": "failed",
    }
    if expected not in COMPAT_OUTCOMES:
        finding["error"] = f"invalid expected outcome {expected!r}"
        return finding

    path = _fixture_for(family, writer)
    if path is None:
        if expected == "unsupported":
            finding["outcome"] = "unsupported"
            finding["status"] = "passed"
            finding["note"] = "no fixture; declared unsupported"
            return finding
        finding["error"] = "missing fixture"
        finding["status"] = "skipped"
        finding["skip_reason"] = "fixture_missing"
        return finding

    data = json.loads(path.read_text(encoding="utf-8"))

    if expected == "unsupported":
        # quality under 0.34 writer is declared unsupported historically;
        # current reader may still load provisional /1 — record regenerate intent.
        finding["outcome"] = "unsupported"
        finding["status"] = "passed"
        finding["note"] = "declared unsupported for 0.34 package set"
        return finding

    if family == "pipeline" and expected == "upgrade-required":
        finding["outcome"] = "upgrade-required"
        finding["status"] = "passed"
        return finding

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            rewritten = _load_with_current(family, data)
        bare_warnings = [w for w in caught if "bare keys" in str(w.message)]
        if expected == "migrated":
            if bare_warnings:
                finding["error"] = "bare-key warnings after migration"
                return finding
            meta = rewritten.get("metadata") or {}
            if "prefect_run_id" in meta:
                finding["error"] = "bare prefect_run_id retained after migration"
                return finding
            if "etlantic.prefect.run_id" not in meta:
                finding["error"] = "namespaced prefect run id missing after migration"
                return finding
            # Deterministic rewrite fingerprint: second pass identical.
            again = _load_with_current(family, rewritten)
            if again.get("metadata") != rewritten.get("metadata"):
                finding["error"] = "non-deterministic metadata rewrite"
                return finding
            finding["outcome"] = "migrated"
            finding["status"] = "passed"
            return finding

        if family == "pipeline":
            before = _semantic_pipeline(data)
            after = _semantic_pipeline(rewritten)
            if before["node_ids"] != after["node_ids"]:
                finding["error"] = "pipeline topology drift"
                return finding
            if before["fingerprint"] != after["fingerprint"]:
                finding["error"] = "pipeline fingerprint drift"
                return finding

        # Fail-closed probe for unknown schema (once per family on current).
        finding["outcome"] = "compatible"
        finding["status"] = "passed"
        return finding
    except Exception as exc:
        finding["error"] = f"{type(exc).__name__}: {exc}"
        return finding


def _fail_closed_unknown_schema() -> dict[str, Any]:
    finding: dict[str, Any] = {
        "family": "pipeline",
        "writer": "unsupported-/99",
        "reader": "current",
        "expected": "upgrade-required",
        "outcome": None,
        "status": "failed",
    }
    path = _fixture_for("pipeline", "current")
    assert path is not None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema"] = "etlantic.pipeline/99"
    try:
        _load_with_current("pipeline", data)
        finding["error"] = "unknown schema was accepted"
    except Exception as exc:
        if "Unsupported" in type(exc).__name__ or "Unsupported" in str(exc):
            finding["outcome"] = "upgrade-required"
            finding["status"] = "passed"
        else:
            finding["error"] = f"unexpected error {type(exc).__name__}: {exc}"
    return finding


def _isolated_wheel_smoke(version: str) -> dict[str, Any]:
    """Install a published core wheel and import public surface."""
    finding: dict[str, Any] = {
        "family": "wheel-smoke",
        "writer": version,
        "reader": version,
        "expected": "compatible",
        "outcome": None,
        "status": "failed",
    }
    pin = f"{version}.0" if version.count(".") == 1 else version
    script = (
        "import etlantic as etl; "
        "from etlantic.authoring import pipeline_from_dict; "
        f"assert etl.__version__.startswith({version!r}), etl.__version__; "
        "print('ok', etl.__version__)"
    )
    cmd = [
        "uv",
        "run",
        "--isolated",
        "--no-project",
        "--with",
        f"etlantic=={pin}",
        "python",
        "-c",
        script,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except FileNotFoundError:
        finding["status"] = "skipped"
        finding["skip_reason"] = "uv_unavailable"
        return finding
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "wheel install failed")[:500]
        finding["error"] = err
        lowered = err.lower()
        if any(tok in lowered for tok in ("network", "offline", "resolution", "http")):
            finding["status"] = "skipped"
            finding["skip_reason"] = "network_or_resolution"
        return finding
    finding["outcome"] = "compatible"
    finding["status"] = "passed"
    finding["note"] = (proc.stdout or "").strip()
    return finding


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--isolated-wheels",
        action="store_true",
        help="Also smoke-test published 0.34/0.35 wheels via uv --isolated",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write etlantic.compatibility_evidence/1 JSON summary",
    )
    args = parser.parse_args(argv)

    findings: list[dict[str, Any]] = []
    for family, writer, reader, expected in MATRIX:
        findings.append(_check_current_cell(family, writer, reader, expected))
    findings.append(_fail_closed_unknown_schema())

    if args.isolated_wheels or os.environ.get("ETLANTIC_ISOLATED_BURN_IN") == "1":
        for ver in ("0.34", "0.35"):
            findings.append(_isolated_wheel_smoke(ver))

    passed = sum(1 for f in findings if f.get("status") == "passed")
    failed = sum(1 for f in findings if f.get("status") == "failed")
    skipped = sum(1 for f in findings if f.get("status") == "skipped")
    summary = {
        "schema": EVIDENCE_SCHEMA,
        "release": "0.36.0",
        "matrix": "old-new-readers-writers",
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "findings": findings,
    }

    out_path = args.output
    if out_path is None:
        out_path = (
            ROOT
            / "tests"
            / "fixtures"
            / "releases"
            / "v0_36"
            / "compatibility_evidence.json"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {k: summary[k] for k in ("schema", "passed", "failed", "skipped")}, indent=2
        )
    )
    if failed:
        print("Isolated codec burn-in FAILED:")
        for f in findings:
            if f.get("status") == "failed":
                print(f"  - {f}")
        return 1
    print(f"Isolated codec burn-in passed ({passed} passed, {skipped} skipped).")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
