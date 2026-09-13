#!/usr/bin/env python3
"""Run the phase 0.53 adaptive execution qualification campaign.

The campaign records only command results and immutable source revision data;
it never embeds pipeline rows, secrets, or process-local handles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "11_DEVELOPMENT" / "evidence" / "adaptive_0_53"
TESTS = (
    "tests/runtime/test_adaptive_execution_0_53.py",
    "tests/plan/test_adaptive_planner_0_52.py",
    "tests/runtime/test_sol_0_53_contract_rereview.py",
)
EVIDENCE_SCHEMA = "etlantic.adaptive_evidence/1"


def source_revision() -> str:
    files = subprocess.run(
        [
            "git",
            "ls-files",
            "src/etlantic",
            "tests/runtime/test_adaptive_execution_0_53.py",
            "tests/plan/test_adaptive_planner_0_52.py",
            "tests/runtime/test_sol_0_53_rereview.py",
            "tests/runtime/test_sol_0_53_contract_rereview.py",
            "scripts/check_adaptive_0_53.py",
            "docs/11_DEVELOPMENT/evidence/adaptive_0_53/README.md",
            ".github/workflows/checks.yml",
            "pyproject.toml",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    digest = hashlib.sha256()
    for name in sorted(files):
        path = ROOT / name
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _verify_committed_evidence(record: dict[str, object], revision: str) -> bool:
    """Require an existing, matching qualification record for read-only runs."""
    path = OUT / "qualification.json"
    if not path.is_file():
        return False
    try:
        committed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(committed, dict):
        return False
    required = {
        "schema": EVIDENCE_SCHEMA,
        "phase": "0.53",
        "source_revision": revision,
        "returncode": 0,
    }
    if not all(committed.get(key) == value for key, value in required.items()):
        return False
    if committed.get("command") != record.get("command"):
        return False
    for field in ("stdout_sha256", "stderr_sha256"):
        digest = committed.get(field)
        if not isinstance(digest, str) or len(digest) != 64:
            return False
    scenarios = committed.get("scenarios")
    return (
        committed.get("result") == "pass"
        and isinstance(committed.get("scenario_count"), int)
        and committed["scenario_count"] == len(TESTS)
        and committed.get("passed_scenarios") == len(TESTS)
        and isinstance(scenarios, list)
        and len(scenarios) == len(TESTS)
        and all(
            isinstance(item, dict)
            and item.get("result") == "pass"
            and item.get("executed") is True
            for item in scenarios
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write", action="store_true", help="write the observed campaign result"
    )
    args = parser.parse_args()
    command = ["uv", "run", "pytest", "-q", *TESTS]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    record = {
        "schema": EVIDENCE_SCHEMA,
        "phase": "0.53",
        "source_revision": source_revision(),
        "command": command,
        "returncode": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "observed_at": datetime.now(UTC).isoformat(),
        "result": "pass" if result.returncode == 0 else "fail",
        "scenario_count": len(TESTS),
        "passed_scenarios": len(TESTS) if result.returncode == 0 else 0,
        "scenarios": [
            {"id": test, "result": "pass", "executed": True} for test in TESTS
        ]
        if result.returncode == 0
        else [],
    }
    if not args.write and not _verify_committed_evidence(
        record, record["source_revision"]
    ):
        print(
            "committed adaptive qualification evidence is missing or stale", flush=True
        )
        return 1
    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "qualification.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(record, sort_keys=True))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
