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
            "scripts/check_adaptive_0_53.py",
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
    return all(committed.get(key) == value for key, value in required.items()) and (
        committed.get("command") == record.get("command")
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
