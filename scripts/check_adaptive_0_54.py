#!/usr/bin/env python3
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Run local candidate checks and retain fresh, payload-free observations.

This checker never changes qualification authority or a graduation decision.
Without --write all generated artifacts are temporary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

if __package__:
    from scripts.adaptive_0_54_evidence import (
        aggregate,
        category_records,
        load,
        validate_catalogue,
        validate_observation,
        verify_index,
    )
else:
    from adaptive_0_54_evidence import (
        aggregate,
        category_records,
        load,
        validate_catalogue,
        validate_observation,
        verify_index,
    )

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "etlantic.adaptive_observation/1"
TESTS = (
    "tests/storage/test_polars_parquet_0_54.py",
    "tests/runtime/physical/test_fusion_0_54.py",
    "tests/adaptive_conformance/test_public_suite.py",
    "tests/adaptive_conformance/test_observation_0_54.py",
    "tests/runtime/test_adaptive_execution_0_53.py",
    "tests/runtime/physical/test_qualification_0_53.py",
    "tests/runtime/test_sol_0_53_rereview.py",
    "tests/runtime/test_sol_0_53_contract_rereview.py",
    "tests/runtime/test_native_execution.py",
    "tests/plan/test_adaptive_wire_0_51.py",
    "tests/plan/test_adaptive_planner_0_52.py",
    "tests/plan/test_adaptive_final_remediation_0_52.py",
    "tests/plan/test_sol_0_52_rereview.py",
    "tests/profile/test_adaptive_profile_0_51.py",
    "tests/reports/test_metadata_namespace_0_51.py",
    "tests/adaptive_conformance/test_evidence_0_54.py",
    "tests/adaptive_conformance/test_graduation_0_54.py",
    "tests/runtime/physical/test_fusion_contract_0_54.py",
    "tests/runtime/test_sol_0_53_effective_request.py",
    "tests/runtime/test_sol_0_53_explicit_override.py",
    "tests/runtime/test_sol_0_53_fallback_override.py",
    "tests/runtime/test_definition_portable_0_53.py",
    "tests/adaptive_conformance/test_operations_0_54.py",
    "tests/adaptive_conformance/test_determinism_0_54.py",
    "tests/runtime/physical/test_review_remediation_0_54.py",
    "tests/storage/test_source_safety_rereview_0_54.py",
    "tests/runtime/physical/test_rereview_lifecycle_0_54.py",
    "tests/runtime/physical/test_rereview_admission_0_54.py",
    "tests/adaptive_conformance/test_rereview_evidence_0_54.py",
)
CATALOGUE = ROOT / "docs/11_DEVELOPMENT/evidence/adaptive_0_54/case_catalogue.json"
DEPENDENCIES = (
    "etlantic",
    "etlantic-polars",
    "etlantic-pandas",
    "polars",
    "pandas",
    "pyarrow",
)


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def source_revision(root: Path = ROOT) -> str:
    """Bind code, schemas, tests, tooling and configuration, not observations."""
    paths: set[Path] = set()
    for directory in (
        "src",
        "packages",
        "tests",
        "scripts",
        ".github/workflows",
        "docs",
        "examples",
        "profiles",
    ):
        paths.update(
            path
            for path in (root / directory).rglob("*")
            if path.is_file()
            and (
                path.suffix in {".py", ".json", ".toml", ".yml", ".yaml", ".md", ".txt"}
                or path.name == "py.typed"
            )
            and "__pycache__" not in path.parts
            and ".venv" not in path.parts
            and path.name
            not in {
                "observation.json",
                "index.json",
                "adaptive_graduation.json",
                "IMPLEMENTATION_STATUS_0_54.md",
                "IMPLEMENTATION_REPORT_0_54.md",
            }
            and not ("adaptive_0_54" in path.parts and "local" in path.parts)
        )
    paths.update(
        root / name
        for name in (
            "pyproject.toml",
            "uv.lock",
            "README.md",
            "CHANGELOG.md",
            "SECURITY.md",
            "SUPPORT.md",
            "mkdocs.yml",
            "AGENTS.md",
        )
    )
    content = hashlib.sha256()
    for path in sorted(paths, key=lambda path: path.relative_to(root).as_posix()):
        content.update(path.relative_to(root).as_posix().encode() + b"\0")
        content.update(
            path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n") + b"\0"
        )
    return "sha256:" + content.hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def installed_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for dependency in DEPENDENCIES:
        try:
            result[dependency] = version(dependency)
        except PackageNotFoundError:
            result[dependency] = None
    return result


class Outcomes:
    """Pytest plugin retaining exact node IDs and statuses, never test payloads."""

    def __init__(self) -> None:
        self.collected: list[str] = []
        self.results: dict[str, dict[str, str]] = {}
        self.collection_failed = False

    def pytest_collection_finish(self, session: Any) -> None:
        self.collected = sorted(item.nodeid for item in session.items)

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed:
            self.collection_failed = True

    def pytest_runtest_logreport(self, report: Any) -> None:
        status = report.outcome
        if hasattr(report, "wasxfail"):
            status = "xpass" if report.passed else "xfail"
        self.results.setdefault(report.nodeid, {})[report.when] = status

    def records(self) -> list[dict[str, str]]:
        records = []
        for identity in self.collected:
            phases = self.results.get(identity, {})
            status = (
                "pass"
                if phases == {"setup": "passed", "call": "passed", "teardown": "passed"}
                else "not-passed"
            )
            records.append({"id": identity, "status": status})
        return records


def execute(output: Path | None = None) -> tuple[int, dict[str, Any]]:
    import pytest

    before = source_revision()
    catalogue = load(CATALOGUE)
    expected = validate_catalogue(catalogue)
    started = datetime.now(UTC).isoformat()
    plugin = Outcomes()
    command = ["-q", *TESTS]
    returncode = int(pytest.main(command, plugins=[plugin]))
    finished = datetime.now(UTC).isoformat()
    after = source_revision()
    cases = plugin.records()
    categories = category_records(catalogue, cases, source=before)
    passed = (
        returncode == 0
        and not plugin.collection_failed
        and bool(cases)
        and len({case["id"] for case in cases}) == len(cases)
        and all(case["status"] == "pass" for case in cases)
        and before == after
        and {case["id"] for case in cases} == expected
    )
    record = {
        "schema": SCHEMA,
        "phase": "0.54",
        "started_at": started,
        "finished_at": finished,
        "commit": _git("rev-parse", "HEAD"),
        "tree": _git("rev-parse", "HEAD^{tree}"),
        "dirty": bool(_git("status", "--porcelain")),
        "source_before": before,
        "source_after": after,
        "environment": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "dependencies": installed_versions(),
        },
        "command": [sys.executable, *sys.argv],
        "ci": {
            name: os.environ.get(name)
            for name in (
                "GITHUB_RUN_ID",
                "GITHUB_RUN_ATTEMPT",
                "GITHUB_JOB",
                "GITHUB_SHA",
            )
        },
        "returncode": returncode,
        "result": "pass" if passed else "fail",
        "collection_failed": plugin.collection_failed,
        "cases": cases,
        "cases_sha256": digest(json.dumps(cases, sort_keys=True).encode()),
        "catalogue_sha256": digest(
            json.dumps(catalogue, sort_keys=True, separators=(",", ":")).encode()
        ),
        "artifacts": {name: digest(content) for name, content in categories.items()},
    }
    if passed:
        try:
            validate_observation(record, catalogue, source=before)
        except (ValueError, TypeError, KeyError):
            passed = False
            record["result"] = "fail"
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        for name, content in categories.items():
            with (output / name).open("xb") as artifact:
                artifact.write(content)
        destination = output / "observation.json"
        with destination.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, indent=2) + "\n")
    return (0 if passed else 1), record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-index", type=Path)
    parser.add_argument("--aggregate", type=Path)
    arguments = parser.parse_args()
    if arguments.verify_index is not None or arguments.aggregate is not None:
        if (
            arguments.write
            or arguments.output is not None
            or (arguments.verify_index is not None and arguments.aggregate is not None)
        ):
            parser.error("index operations cannot execute or write observations")
        try:
            catalogue = load(CATALOGUE)
            if arguments.aggregate is not None:
                destination = arguments.aggregate / "index.json"
                index = aggregate(
                    arguments.aggregate, catalogue, source=source_revision()
                )
                with destination.open("x", encoding="utf-8") as handle:
                    handle.write(json.dumps(index, sort_keys=True, indent=2) + "\n")
            else:
                destination = arguments.verify_index
            assert destination is not None
            verify_index(destination, catalogue, source=source_revision())
        except (OSError, ValueError, KeyError, TypeError):
            print("0.54 evidence index: failed integrity/completeness validation")
            return 1
        print(
            "0.54 evidence index: nine actual same-candidate CI cells verified; no approval granted"
        )
        return 0
    if arguments.write != (arguments.output is not None):
        parser.error("--write and --output must be supplied together")
    if (
        arguments.output is not None
        and arguments.output.exists()
        and any(arguments.output.iterdir())
    ):
        parser.error("refusing to overwrite an existing observation directory")
    if arguments.write:
        status, record = execute(arguments.output)
    else:
        with tempfile.TemporaryDirectory(prefix="etlantic-observation-") as directory:
            status, record = execute(Path(directory))
    print(f"0.54 local observation: {record['result']} ({len(record['cases'])} cases)")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
