#!/usr/bin/env python3
"""Run and verify the phase 0.55 inference evidence campaign.

The checked-in manifest describes the qualification decision. This command
also records the evidence needed to make that decision reproducible: every
gate result is bound to a commit and tree, a clean worktree, the command that
ran, the environment, and hashes of bounded command output. Gate output is
never copied into the evidence bundle because it may contain provider data.

Examples::

    uv run python scripts/check_inference_0_55.py --run-focused
    uv run python scripts/check_inference_0_55.py --run-gates --output /tmp/etlantic-055
    uv run python scripts/check_inference_0_55.py --verify /tmp/etlantic-055
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/11_DEVELOPMENT/evidence/inference_0_55"
GATES = (
    "wire_security",
    "bounded_materialization",
    "lineage_solver",
    "target_revision",
    "durable_definition",
    "optional_dependency_matrix",
    "differential_fixtures",
    "race_tests",
    "full_regression",
)
QUALIFICATION_STATES = {"planned", "in_progress", "blocked", "qualified", "unsupported"}
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
OPTIONAL_SURFACES = {
    "pyspark": ("etlantic_pyspark", "pyspark"),
    "datafusion": ("etlantic_datafusion", "datafusion"),
    "sql-duckdb": ("etlantic_duckdb", "duckdb"),
    "parquet": ("pyarrow",),
    "schema-registry": ("etlantic_schemaregistry",),
}
GATE_TESTS: dict[str, tuple[str, ...]] = {
    "bounded_materialization": (
        "tests/inference/test_inference.py",
        "tests/inference/test_phase_055_blockers.py",
        "tests/inference/test_review_fixes.py",
        "-k",
        "bound or materializ or preview or iterator",
    ),
    "lineage_solver": (
        "tests/inference/test_inference.py",
        "tests/inference/test_review_fixes.py",
        "-k",
        "lineage or solver or target_guidance or backward",
    ),
    "target_revision": (
        "tests/inference/test_phase_055_blockers.py",
        "tests/inference/test_review_fixes.py",
        "-k",
        "revision or existence or publication or stale",
    ),
    "durable_definition": (
        "tests/inference/test_review_fixes.py",
        "-k",
        "definition or binding or rebind",
    ),
    "differential_fixtures": ("tests/portable_differential",),
    "race_tests": (
        "tests/inference/test_phase_055_blockers.py",
        "tests/inference/test_review_fixes.py",
        "-k",
        "race or concurrent or revision or publication",
    ),
    "full_regression": (),
}


def _key_kind(key: str, *, literal_node: bool = False) -> str | None:
    normalized = "".join(char for char in key.casefold() if char.isalnum())
    if normalized in {"rowfree", "rowsfree"}:
        return None
    if literal_node and normalized in {"value", "values"}:
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


def _check_row_free(
    value: Any, path: str = "manifest", *, literal_node: bool = False
) -> None:
    if isinstance(value, dict):
        is_literal_node = value.get("kind") == "literal"
        for key, item in value.items():
            kind = _key_kind(str(key), literal_node=literal_node or is_literal_node)
            if kind is not None:
                raise ValueError(f"{kind} evidence key is forbidden: {path}.{key}")
            _check_row_free(
                item, f"{path}.{key}", literal_node=literal_node or is_literal_node
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_row_free(item, f"{path}[{index}]")
    elif isinstance(value, str) and any(
        marker in value
        for marker in ("/Users/", "/home/", "/tmp/", "/var/", "/Volumes/")
    ):
        raise ValueError(f"absolute path leaked into evidence: {path}")


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    _check_row_free(payload, path.name)
    return payload


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def _git_identity() -> dict[str, Any]:
    return {
        "commit": _git("rev-parse", "HEAD"),
        "tree": _git("rev-parse", "HEAD^{tree}"),
        "dirty": bool(_git("status", "--porcelain")),
    }


def _is_commit(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        check=False,
    )
    return result.returncode == 0


def _installed_versions() -> dict[str, str | None]:
    names = ("etlantic", "pandas", "polars", "pyarrow", "pytest", "ruff", "pyright")
    found: dict[str, str | None] = {}
    for name in names:
        try:
            found[name] = version(name)
        except PackageNotFoundError:
            found[name] = None
    return found


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


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


def _validate_capability_matrix(matrix: dict[str, Any]) -> None:
    if matrix.get("schema") != "etlantic.inference-capability-matrix/1":
        raise ValueError("unknown capability matrix schema")
    entries = matrix.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("capability matrix is empty")
    surfaces: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(key), str) and entry.get(key)
            for key in ("surface", "kind", "state")
        ):
            raise ValueError(
                "capability matrix entries require surface, kind, and state"
            )
        surface = entry["surface"]
        state = entry["state"]
        surfaces.add(surface)
        if state.startswith("pending"):
            raise ValueError(
                f"capability matrix surface remains silently pending: {surface}"
            )
        if not isinstance(entry.get("evidence"), str) or not entry["evidence"]:
            raise ValueError(f"capability matrix surface lacks evidence: {surface}")
        if state == "unsupported" and not isinstance(entry.get("reason"), str):
            raise ValueError(f"unsupported capability lacks a reason: {surface}")
        if state == "implemented-with-fakes":
            raise ValueError(
                f"fake adapter cannot be a qualified capability: {surface}"
            )
    required = {"records", "csv", "json", "pandas", "polars"}
    if not required <= surfaces:
        raise ValueError(
            f"missing required source surfaces: {sorted(required - surfaces)}"
        )


def _validate_manifest(
    index: dict[str, Any], matrix: dict[str, Any], ledger: dict[str, Any]
) -> None:
    if index.get("schema") != "etlantic.inference-evidence/1":
        raise ValueError("unknown inference evidence schema")
    if index.get("phase") != "0.55":
        raise ValueError("inference evidence has the wrong phase")
    if index.get("status") not in QUALIFICATION_STATES:
        raise ValueError("inference evidence has an invalid qualification state")
    if not isinstance(index.get("qualified"), bool):
        raise ValueError("inference evidence must declare qualified as a boolean")
    if index["qualified"] != (index["status"] == "qualified"):
        raise ValueError("qualified must agree with the manifest status")
    artifacts = index.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("evidence index must declare artifacts")
    for artifact_name in artifacts:
        if (
            not isinstance(artifact_name, str)
            or Path(artifact_name).name != artifact_name
        ):
            raise ValueError("evidence artifact names must be local JSON filenames")
        artifact = EVIDENCE / artifact_name
        if artifact.suffix != ".json" or not artifact.is_file():
            raise ValueError(f"missing declared evidence artifact: {artifact_name}")
        _load(artifact)
    required_gates = index.get("required_gates")
    if required_gates != list(GATES):
        raise ValueError(
            "evidence gates do not match the authoritative phase gate list"
        )
    required_findings = index.get("required_findings")
    if not isinstance(required_findings, list) or not required_findings:
        raise ValueError("evidence index must declare required findings")
    _validate_capability_matrix(matrix)
    if ledger.get("schema") != "etlantic.inference-finding-ledger/1":
        raise ValueError("unknown inference finding ledger schema")
    findings = ledger.get("findings")
    if not isinstance(findings, list) or not findings:
        raise ValueError("finding ledger is empty")
    current_commit = _git_identity()["commit"]
    finding_ids: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict) or not all(
            isinstance(finding.get(key), str) and finding.get(key)
            for key in ("id", "priority", "status", "code", "test", "gate")
        ):
            raise ValueError(
                "finding ledger entries require id, priority, status, code, test, and gate"
            )
        finding_ids.add(finding["id"])
        implementation_commit = finding.get("implementation_commit")
        if not isinstance(implementation_commit, str) or not _is_commit(
            implementation_commit
        ):
            raise ValueError(f"finding {finding['id']} is not pinned to a commit")
        if not _is_ancestor(implementation_commit, current_commit):
            raise ValueError(
                f"finding {finding['id']} points outside the evaluated history"
            )
        evidence_artifact = finding.get("evidence_artifact")
        if (
            not isinstance(evidence_artifact, str)
            or not (ROOT / evidence_artifact).is_file()
        ):
            raise ValueError(
                f"finding evidence artifact is missing: {evidence_artifact}"
            )
        if finding["gate"] not in GATES:
            raise ValueError(f"finding {finding['id']} references an undeclared gate")
        if index["qualified"] and finding["status"] != "verified":
            raise ValueError(
                f"qualified evidence contains an unverified finding: {finding['id']}"
            )
    missing_findings = set(required_findings) - finding_ids
    if missing_findings:
        raise ValueError(
            f"finding ledger is missing required blockers: {sorted(missing_findings)}"
        )


def _evidence_payloads_are_safe() -> None:
    for path in sorted(EVIDENCE.rglob("*.json")):
        _load(path)


def _check_optional_dependency_gate(matrix: dict[str, Any]) -> None:
    _validate_capability_matrix(matrix)
    entries = {entry["surface"]: entry for entry in matrix["entries"]}
    for surface, modules in OPTIONAL_SURFACES.items():
        entry = entries.get(surface)
        if entry is None:
            raise ValueError(
                f"optional surface is missing from the capability matrix: {surface}"
            )
        if entry["state"] == "unsupported":
            continue
        if not any(importlib.util.find_spec(module) is not None for module in modules):
            raise ValueError(f"advertised optional surface is unavailable: {surface}")


def _actual_command(gate: str) -> list[str]:
    if gate in {"wire_security", "optional_dependency_matrix"}:
        return ["python", "scripts/check_inference_0_55.py", "--gate", gate]
    if gate == "full_regression":
        return ["python", "-m", "pytest", "-q"]
    return ["python", "-m", "pytest", "-q", *GATE_TESTS[gate]]


def _runtime_command(gate: str) -> list[str]:
    display = _actual_command(gate)
    if display[1] == "scripts/check_inference_0_55.py":
        return [sys.executable, str(Path(__file__)), "--gate", gate]
    return [sys.executable, *display[1:]]


def _run_gate_action(gate: str, matrix: dict[str, Any]) -> int:
    if gate == "wire_security":
        _check_generated_payloads()
        _evidence_payloads_are_safe()
        return 0
    if gate == "optional_dependency_matrix":
        _check_optional_dependency_gate(matrix)
        return 0
    completed = subprocess.run(_runtime_command(gate), cwd=ROOT, check=False)
    return completed.returncode


def _gate_record(
    gate: str,
    identity: dict[str, Any],
    started_at: str,
    finished_at: str,
    completed: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {
        "schema": "etlantic.inference-gate-result/1",
        "phase": "0.55",
        "gate": gate,
        "result": "pass" if completed.returncode == 0 else "fail",
        "commit": identity["commit"],
        "tree": identity["tree"],
        "dirty": identity["dirty"],
        "started_at": started_at,
        "finished_at": finished_at,
        "command": _actual_command(gate),
        "environment": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "dependencies": _installed_versions(),
        },
        "returncode": completed.returncode,
        "stdout_bytes": len(stdout.encode()),
        "stderr_bytes": len(stderr.encode()),
        "stdout_sha256": _digest(stdout.encode()),
        "stderr_sha256": _digest(stderr.encode()),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _run_campaign(output: Path) -> tuple[int, dict[str, Any]]:
    output.mkdir(parents=True, exist_ok=True)
    gate_dir = output / "gates"
    gate_dir.mkdir(parents=True, exist_ok=True)
    identity = _git_identity()
    started = datetime.now(UTC).isoformat()
    results: dict[str, str] = {}
    passed = True
    for gate in GATES:
        gate_started = datetime.now(UTC).isoformat()
        completed = subprocess.run(
            _runtime_command(gate),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        gate_finished = datetime.now(UTC).isoformat()
        record = _gate_record(gate, identity, gate_started, gate_finished, completed)
        _write_json(gate_dir / f"{gate}.json", record)
        results[gate] = f"gates/{gate}.json"
        passed = passed and completed.returncode == 0
    campaign = {
        "schema": "etlantic.inference-gate-campaign/1",
        "phase": "0.55",
        "evaluated_commit": identity["commit"],
        "evaluated_tree": identity["tree"],
        "dirty": identity["dirty"],
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "required_gates": list(GATES),
        "results": results,
        "result": "pass" if passed and not identity["dirty"] else "fail",
    }
    _write_json(output / "index.json", campaign)
    return (0 if campaign["result"] == "pass" else 1), campaign


def _verify_campaign(
    output: Path,
    index: dict[str, Any],
    matrix: dict[str, Any],
    ledger: dict[str, Any],
) -> None:
    campaign = _load(output / "index.json")
    if campaign.get("schema") != "etlantic.inference-gate-campaign/1":
        raise ValueError("unknown gate campaign schema")
    if campaign.get("phase") != "0.55" or campaign.get("required_gates") != list(GATES):
        raise ValueError("gate campaign does not cover the authoritative phase gates")
    evaluated_commit = campaign.get("evaluated_commit")
    evaluated_tree = campaign.get("evaluated_tree")
    current = _git_identity()
    if not _is_commit(evaluated_commit) or not _is_commit(evaluated_tree):
        raise ValueError("gate campaign is not pinned to immutable git identities")
    if current["dirty"]:
        raise ValueError("current worktree is dirty; gate evidence cannot be verified")
    if evaluated_commit != current["commit"] or evaluated_tree != current["tree"]:
        raise ValueError(
            "gate campaign is stale or does not match the evaluated revision"
        )
    if campaign.get("dirty") is not False:
        raise ValueError("gate campaign was produced from a dirty worktree")
    if campaign.get("result") != "pass":
        raise ValueError("gate campaign contains a failed gate")
    results = campaign.get("results")
    if not isinstance(results, dict) or set(results) != set(GATES):
        raise ValueError("gate campaign is missing a required gate result")
    for gate in GATES:
        path_value = results[gate]
        if not isinstance(path_value, str) or not path_value.startswith("gates/"):
            raise ValueError(f"invalid result path for gate: {gate}")
        record = _load(output / path_value)
        if record.get("schema") != "etlantic.inference-gate-result/1":
            raise ValueError(f"unknown result schema for gate: {gate}")
        if (
            record.get("phase") != "0.55"
            or record.get("gate") != gate
            or record.get("result") != "pass"
        ):
            raise ValueError(f"gate did not pass: {gate}")
        if (
            record.get("commit") != evaluated_commit
            or record.get("tree") != evaluated_tree
        ):
            raise ValueError(f"gate result is stale or mismatched: {gate}")
        if record.get("dirty") is not False:
            raise ValueError(f"gate result was produced from a dirty worktree: {gate}")
    _validate_manifest(index, matrix, ledger)


def _focused() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/inference"],
        cwd=ROOT,
        check=False,
    )
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-focused", action="store_true")
    parser.add_argument("--run-gates", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--gate", choices=GATES)
    args = parser.parse_args()
    selected = sum(
        bool(value)
        for value in (args.run_focused, args.run_gates, args.verify, args.gate)
    )
    if selected > 1:
        parser.error(
            "choose only one of --run-focused, --run-gates, --verify, or --gate"
        )
    if args.run_gates and args.output is None:
        parser.error("--run-gates requires --output")
    try:
        index = _load(EVIDENCE / "index.json")
        matrix = _load(EVIDENCE / "capability_matrix.json")
        ledger = _load(EVIDENCE / "finding_ledger.json")
        if args.gate:
            return _run_gate_action(args.gate, matrix)
        if args.run_focused:
            return _focused()
        _validate_manifest(index, matrix, ledger)
        if args.run_gates:
            code, campaign = _run_campaign(args.output)
            print(json.dumps({"phase": "0.55", "status": "gate-campaign", **campaign}))
            return code
        if args.verify:
            _verify_campaign(args.verify, index, matrix, ledger)
            status = (
                "qualified" if index["qualified"] else "gates-valid-phase-unqualified"
            )
            print(
                json.dumps(
                    {"phase": "0.55", "status": status, "qualified": index["qualified"]}
                )
            )
            return 0 if index["qualified"] else 1
        checked_in = EVIDENCE / "gates"
        if not checked_in.is_dir():
            raise ValueError(
                "required gate campaign is missing; run --run-gates and preserve its output"
            )
        _verify_campaign(checked_in.parent, index, matrix, ledger)
        print(json.dumps({"phase": "0.55", "status": "qualified", "qualified": True}))
        return 0
    except (
        OSError,
        subprocess.CalledProcessError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"0.55 evidence check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
