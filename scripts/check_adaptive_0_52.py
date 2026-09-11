#!/usr/bin/env python3
"""Generate and verify executable adaptive 0.52 release evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "11_DEVELOPMENT" / "evidence" / "adaptive_0_51"

CAMPAIGNS: dict[str, tuple[tuple[str, str], ...]] = {
    "adaptive_inventory_conformance_0_51.json": (
        ("AC-052-004", "test_final_052_001_missing_target_reference_is_negative"),
        (
            "AC-052-005",
            "test_final_052_002_generic_engine_pair_is_not_handoff_evidence",
        ),
    ),
    "adaptive_solver_conformance_0_51.json": (
        ("AC-052-006", "test_candidate_matrix_is_canonical_node_then_target_order"),
        ("AC-052-006", "test_adaptive_candidate_analysis_is_analyze_only"),
        ("AC-052-008", "test_adaptive_solver_matches_seeded_oracle_corpus"),
        ("AC-052-008", "test_adaptive_solver_oracle_rejects_a_nonoptimal_assignment"),
    ),
    "adaptive_resource_budget_0_51.json": (
        ("AC-052-003", "test_final_052_001_target_limit_precedes_plugin_discovery"),
        ("AC-052-009", "test_adaptive_resource_limits_fail_before_crossing"),
        ("AC-052-009", "test_adaptive_bytes_ignore_target_mapping_insertion_order"),
    ),
    "adaptive_physical_dag_conformance_0_51.json": (
        ("AC-052-010", "test_adaptive_regions_are_maximal_and_unfused_without_proof"),
        ("AC-052-011", "test_adaptive_logical_path_can_cross_all_boundary_unit_kinds"),
        (
            "AC-052-012",
            "test_final_052_012_logical_edge_path_cannot_be_hidden_by_metadata",
        ),
    ),
    "adaptive_runtime_conformance_0_51.json": (
        ("AC-052-016", "test_adaptive_release_side_effect_sentinels"),
    ),
    "adaptive_consumer_matrix_0_51.json": (
        ("AC-052-001", "test_adaptive_report_path_uses_same_plan_dispatch"),
        ("AC-052-015", "test_adaptive_surface_projections_share_plan_identity"),
    ),
    "adaptive_explain_identity_0_51.json": (
        ("AC-052-013", "test_adaptive_explain_uses_the_bounded_summary"),
        ("AC-052-014", "test_adaptive_diff_covers_semantic_and_cross_schema_changes"),
    ),
    "adaptive_security_matrix_0_51.json": (
        (
            "AC-052-005",
            "test_adaptive_cross_target_requires_directional_handoff_evidence",
        ),
        ("AC-052-017", "test_adaptive_artifacts_redact_absolute_target_resources"),
    ),
    "adaptive_e2e_0_51.json": (
        ("AC-052-002", "test_explicit_plan_snapshot_omits_dormant_adaptive_policy"),
        ("AC-052-007", "test_final_052_003_fallback_report_and_integrity"),
        ("AC-052-012", "test_adaptive_wire_round_trip_and_dispatch"),
        ("AC-052-018", "test_adaptive_release_evidence_contract_is_ci_gated"),
    ),
}

VERIFICATION_FILES = (
    "tests/plan/test_adaptive_planner_0_52.py",
    "tests/profile/test_adaptive_profile_0_51.py",
    "tests/plan/test_adaptive_wire_0_51.py",
    "tests/plan/test_phase_0_52_review_blockers.py",
)

REVISION_FILES = (
    ".github/workflows/checks.yml",
    "docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_52.md",
    "mkdocs.yml",
    "pyproject.toml",
    "scripts/check_adaptive_0_52.py",
    "uv.lock",
)
REVISION_TREES = ("src/etlantic", "packages", "tests")
REVISION_SUFFIXES = {".json", ".py", ".pyi", ".toml", ".yaml", ".yml"}


def _source_revision() -> str:
    digest = hashlib.sha256()
    inputs = {Path(relative) for relative in REVISION_FILES}
    tracked = subprocess.run(
        ["git", "ls-files", "--", *REVISION_TREES],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    inputs.update(
        Path(relative)
        for relative in tracked
        if Path(relative).suffix in REVISION_SUFFIXES
    )
    for relative_path in sorted(inputs, key=lambda path: path.as_posix()):
        relative = relative_path.as_posix()
        path = ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        source = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        digest.update(source)
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _verified_plan_fingerprint() -> str:
    from etlantic import Data, Extract, Load, Pipeline
    from etlantic.plan import plan_pipeline, verify_plan_fingerprint
    from etlantic.profile import PlacementTarget, Profile

    class EvidenceRow(Data):
        value: int

    class EvidencePipeline(Pipeline):
        __module__ = "etlantic.evidence.adaptive_0_52"
        source: Extract[EvidenceRow] = Extract(asset="evidence-source")
        sink: Load[EvidenceRow] = Load(input=source, asset="evidence-sink")

    profile = Profile(
        name="adaptive-evidence",
        execution_strategy="adaptive",
        portable_transform_policy="require",
        placement_targets={"local": PlacementTarget(engine="local")},
        eligible_targets=("local",),
    )
    plan = plan_pipeline(EvidencePipeline, profile=profile)
    verify_plan_fingerprint(plan)
    return plan.fingerprint


def _run_campaign() -> tuple[bool, str, set[str], dict[str, int]]:
    with tempfile.TemporaryDirectory(prefix="etlantic-adaptive-evidence-") as temp:
        report = Path(temp) / "pytest.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-vv",
            "-s",
            *VERIFICATION_FILES,
            "-k",
            "not final_052_006",
            f"--junitxml={report}",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        passed = set()
        if report.exists():
            for case in ET.parse(report).iter("testcase"):
                if not any(
                    case.find(outcome) is not None
                    for outcome in ("failure", "error", "skipped")
                ):
                    passed.add(str(case.attrib.get("name", "")).split("[", 1)[0])
    output = completed.stdout + completed.stderr
    marker = re.findall(r"ETLANTIC_ADAPTIVE_SIDE_EFFECT_COUNTS=(\{[^\n]+\})", output)
    counts = json.loads(marker[-1]) if marker else {}
    return completed.returncode == 0, output, passed, counts


def _supported_platforms() -> list[dict[str, str]]:
    workflow = (ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8")
    os_match = re.search(r"os:\s*\[([^]]+)\]", workflow)
    python_match = re.search(r"python-version:\s*\[([^]]+)\]", workflow)
    if os_match is None or python_match is None:
        raise RuntimeError("adaptive CI platform matrix is not an inline list")
    step = workflow.split("- name: Adaptive 0.52 evidence verifier", 1)[1].split(
        "- name:", 1
    )[0]
    if "if:" in step:
        raise RuntimeError(
            "adaptive evidence verifier is not enabled on every matrix row"
        )
    operating_systems = [item.strip(" \"'") for item in os_match.group(1).split(",")]
    python_versions = [item.strip(" \"'") for item in python_match.group(1).split(",")]
    return [
        {
            "os": operating_system,
            "python": python_version,
            "verification": "github-actions:checks/adaptive-evidence",
        }
        for operating_system in operating_systems
        for python_version in python_versions
    ]


def _scan_payload(payload: dict[str, object]) -> dict[str, bool]:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    secret_value = re.search(
        r'"(?:api[_-]?key|authorization|password|secret|token)"\s*:\s*"(?!\*\*\*)[^\"]+"',
        encoded,
        re.IGNORECASE,
    )
    source_rows = re.search(
        r'"(?:preview_rows|sample_rows|source_rows)"\s*:', encoded, re.IGNORECASE
    )
    return {
        "absolute_repository_path": str(ROOT) in encoded,
        "source_rows": source_rows is not None,
        "secrets": secret_value is not None,
    }


def _payloads() -> tuple[dict[str, dict[str, object]], str]:
    passed, output, passed_tests, side_effect_counts = _run_campaign()
    if not passed:
        raise RuntimeError("adaptive release campaign failed:\n" + output)
    if side_effect_counts != {"compile": 0, "execute": 0, "io": 0}:
        raise RuntimeError(
            "adaptive side-effect evidence missing or non-zero: "
            + repr(side_effect_counts)
        )
    revision = _source_revision()
    fingerprint = _verified_plan_fingerprint()
    supported_platforms = _supported_platforms()
    payloads: dict[str, dict[str, object]] = {}
    for name, campaign in CAMPAIGNS.items():
        scenarios = []
        for criterion, proof in campaign:
            scenario_passed = proof in passed_tests
            scenarios.append(
                {
                    "id": proof,
                    "acceptance_criterion": criterion,
                    "verification": proof,
                    "expected": "pass",
                    "actual": "pass" if scenario_passed else "not_observed",
                    "result": "pass" if scenario_passed else "fail",
                    "executed": True,
                    "plan_fingerprint": fingerprint,
                }
            )
        if not all(item["result"] == "pass" for item in scenarios):
            missing = [
                item["verification"] for item in scenarios if item["result"] != "pass"
            ]
            raise RuntimeError(
                "adaptive evidence proof was not observed: " + ", ".join(missing)
            )
        payload: dict[str, object] = {
            "schema": "etlantic.adaptive-evidence/1",
            "artifact": name,
            "repository_revision": revision,
            "public_schema": "etlantic.plan/2",
            "planner_version": "0.52",
            "result": "pass",
            "scenario_count": len(scenarios),
            "passed_scenarios": sum(item["result"] == "pass" for item in scenarios),
            "supported_platforms": supported_platforms,
            "side_effect_counts": side_effect_counts,
            "scenarios": scenarios,
            "verification_command": [
                "python",
                "-m",
                "pytest",
                "-q",
                "-vv",
                "-s",
                *VERIFICATION_FILES,
                "-k",
                "not final_052_006",
            ],
        }
        payload["source_scan"] = _scan_payload(payload)
        if any(payload["source_scan"].values()):  # type: ignore[union-attr]
            raise RuntimeError(f"adaptive evidence scan failed for {name}")
        payloads[name] = payload
    findings = (
        "# Adaptive 0.52 Evidence\n\n"
        "**Status:** Generated executable release evidence.\n\n"
        f"Repository input revision: `{revision}`.\n\n"
        "The adaptive release campaign passed and covers AC-052-001 through "
        "AC-052-018. Artifacts are regenerated only after the referenced public "
        "behavior and blocker regression tests pass.\n"
    )
    return payloads, findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        payloads, findings_text = _payloads()
    except RuntimeError as exc:
        print(exc)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    expected = {
        name: json.dumps(payload, sort_keys=True, indent=2) + "\n"
        for name, payload in payloads.items()
    }
    expected["FINDINGS.md"] = findings_text
    root_text = str(ROOT)
    for name, text in expected.items():
        if root_text in text:
            print(f"adaptive evidence contains absolute repository path: {name}")
            return 1

    mismatches: list[str] = []
    for name, text in expected.items():
        path = OUT / name
        if args.write:
            path.write_text(text, encoding="utf-8")
        elif not path.exists() or path.read_text(encoding="utf-8") != text:
            mismatches.append(name)
    if mismatches:
        print("adaptive evidence differs:", ", ".join(mismatches))
        return 1
    print(
        f"adaptive evidence verified ({len(expected)} artifacts; "
        "18 acceptance criteria)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
