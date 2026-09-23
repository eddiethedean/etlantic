#!/usr/bin/env python3
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Execute and verify source-bound, non-skipped adaptive qualification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/11_DEVELOPMENT/evidence/adaptive_0_53"
TESTS = (
    "tests/runtime/test_adaptive_execution_0_53.py",
    "tests/plan/test_adaptive_planner_0_52.py",
    "tests/runtime/test_sol_0_53_rereview.py",
    "tests/runtime/test_sol_0_53_contract_rereview.py",
    "tests/runtime/physical/test_qualification_0_53.py",
    "tests/runtime/test_native_execution.py",
)
EVIDENCE_SCHEMA = "etlantic.adaptive_evidence/2"


def installed_versions() -> dict[str, str | None]:
    """Report missing optional distributions without breaking fail-closed checks."""
    versions: dict[str, str | None] = {}
    for name in ("etlantic", "polars", "pandas", "pyarrow"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = None
    return versions


def source_revision() -> str:
    paths = set(ROOT.joinpath("src/etlantic").rglob("*.py"))
    paths.update(ROOT.joinpath("packages/etlantic-polars/src").rglob("*.py"))
    paths.update(ROOT.joinpath("packages/etlantic-pandas/src").rglob("*.py"))
    paths.update(ROOT / name for name in TESTS)
    paths.update(
        ROOT / name
        for name in (
            "src/etlantic/runtime/adaptive_support.json",
            "scripts/check_adaptive_0_53.py",
            "docs/11_DEVELOPMENT/evidence/adaptive_0_53/README.md",
            ".github/workflows/checks.yml",
            "pyproject.toml",
            "uv.lock",
        )
    )
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix()):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def scenarios_from_junit(path: Path) -> list[dict[str, Any]]:
    root = ET.parse(path).getroot()
    scenarios = []
    for case in root.iter("testcase"):
        status = "pass"
        for tag in ("skipped", "failure", "error"):
            if case.find(tag) is not None:
                status = tag
        scenarios.append(
            {
                "id": case.get("classname", "") + "::" + case.get("name", ""),
                "result": status,
                "executed": status != "skipped",
            }
        )
    return sorted(scenarios, key=lambda item: item["id"])


def redacted_junit(scenarios: list[dict[str, Any]]) -> bytes:
    """Retain executed test identities/statuses, never captured exception/log payloads."""
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", tests=str(len(scenarios)))
    for scenario in scenarios:
        classname, _, name = scenario["id"].partition("::")
        case = ET.SubElement(suite, "testcase", classname=classname, name=name)
        if scenario["result"] != "pass":
            ET.SubElement(case, scenario["result"])
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _qualified(scenarios: Any) -> bool:
    if not isinstance(scenarios, list) or not scenarios:
        return False
    if any(
        not isinstance(s, dict)
        or s.get("result") != "pass"
        or s.get("executed") is not True
        for s in scenarios
    ):
        return False
    ids = [s["id"] for s in scenarios]
    if len(set(ids)) != len(ids):
        return False
    for name in TESTS:
        prefix = name.removesuffix(".py").replace("/", ".") + "::"
        if not any(identity.startswith(prefix) for identity in ids):
            return False
    # Every empty/nullable baseline and each directional multi-port row must execute.
    for row in range(2):
        for family in range(5):
            if not any(
                identity.endswith(
                    f"test_five_family_stored_differential[rows{row}-families{family}]"
                )
                for identity in ids
            ):
                return False
    return True


def _verify_committed_evidence(record: dict[str, Any], revision: str) -> bool:
    try:
        committed = json.loads((OUT / "qualification.json").read_text())
        if not isinstance(committed, dict):
            return False
        if any(
            committed.get(k) != v
            for k, v in {
                "schema": EVIDENCE_SCHEMA,
                "phase": "0.53",
                "source_revision": revision,
                "returncode": 0,
                "result": "pass",
                "source_changed": False,
            }.items()
        ):
            return False
        if (
            committed.get("environment") != record.get("environment")
            or committed.get("command") != record.get("command")
            or not _qualified(committed.get("scenarios"))
        ):
            return False
        stored = scenarios_from_junit(OUT / "qualification.xml")
        if stored != committed["scenarios"] or record.get("scenarios") != stored:
            return False
        for field, filename in (
            ("stdout_sha256", "qualification.stdout.txt"),
            ("stderr_sha256", "qualification.stderr.txt"),
            ("junit_sha256", "qualification.xml"),
        ):
            if hashlib.sha256(
                (OUT / filename).read_bytes()
            ).hexdigest() != committed.get(field):
                return False
        return committed.get("scenario_count") == len(stored) and committed.get(
            "passed_scenarios"
        ) == len(stored)
    except (OSError, ValueError, ET.ParseError, KeyError, TypeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="record the observed result, including failures",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT,
        help="output directory for environment-specific CI proof",
    )
    args = parser.parse_args()
    command = ["uv", "run", "--no-sync", "pytest", "-q", *TESTS]
    revision_before = source_revision()
    with tempfile.TemporaryDirectory(prefix="etlantic053-") as temporary:
        junit = Path(temporary) / "qualification.xml"
        result = subprocess.run(
            [*command, f"--junitxml={junit}"], cwd=ROOT, text=True, capture_output=True
        )
        try:
            scenarios = scenarios_from_junit(junit)
        except (OSError, ET.ParseError):
            scenarios = []
        source_changed = revision_before != source_revision()
        qualified = (
            result.returncode == 0 and _qualified(scenarios) and not source_changed
        )
        safe_junit = redacted_junit(scenarios)
        safe_stdout = (
            json.dumps(
                {
                    "returncode": result.returncode,
                    "scenario_count": len(scenarios),
                    "passed": sum(s["result"] == "pass" for s in scenarios),
                },
                sort_keys=True,
            )
            + "\n"
        )
        safe_stderr = (
            json.dumps({"stderr_present": bool(result.stderr)}, sort_keys=True) + "\n"
        )
        record = {
            "schema": EVIDENCE_SCHEMA,
            "phase": "0.53",
            "source_revision": revision_before,
            "source_changed": source_changed,
            "command": command,
            "returncode": result.returncode,
            "stdout_sha256": hashlib.sha256(safe_stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(safe_stderr.encode()).hexdigest(),
            "junit_sha256": hashlib.sha256(safe_junit).hexdigest(),
            "observed_at": datetime.now(UTC).isoformat(),
            "environment": {
                "os": platform.system(),
                "python": platform.python_version(),
                "machine": platform.machine(),
                "versions": installed_versions(),
            },
            "result": "pass" if qualified else "fail",
            "scenario_count": len(scenarios),
            "passed_scenarios": sum(s["result"] == "pass" for s in scenarios),
            "scenarios": scenarios,
        }
        if args.write:
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "qualification.json").write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n"
            )
            (args.output / "qualification.stdout.txt").write_bytes(safe_stdout.encode())
            (args.output / "qualification.stderr.txt").write_bytes(safe_stderr.encode())
            (args.output / "qualification.xml").write_bytes(safe_junit)
        elif not _verify_committed_evidence(record, str(record["source_revision"])):
            print(
                "committed adaptive qualification evidence is missing, stale, skipped or unsubstantiated"
            )
            return 1
        print(json.dumps(record, sort_keys=True))
        return 0 if qualified else 1


if __name__ == "__main__":
    raise SystemExit(main())
