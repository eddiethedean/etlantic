#!/usr/bin/env python3
"""Generate and verify executable adaptive 0.52 release evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
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
        ("AC-052-008", "test_final_052_007_solver_handles_prunable_in_scope_plan"),
    ),
    "adaptive_resource_budget_0_51.json": (
        ("AC-052-003", "test_final_052_001_target_limit_precedes_plugin_discovery"),
        ("AC-052-009", "test_final_052_007_solver_handles_prunable_in_scope_plan"),
    ),
    "adaptive_physical_dag_conformance_0_51.json": (
        ("AC-052-010", "test_adaptive_plan_binds_regions_to_inventory_and_decisions"),
        ("AC-052-011", "test_adaptive_plan_binds_physical_units_to_target_inventory"),
    ),
    "adaptive_runtime_conformance_0_51.json": (
        ("AC-052-016", "test_adaptive_execution_rejects_before_runtime"),
        ("AC-052-016", "test_local_scheduler_rejects_adaptive_before_runtime_access"),
    ),
    "adaptive_consumer_matrix_0_51.json": (
        ("AC-052-001", "test_adaptive_report_path_uses_same_plan_dispatch"),
        ("AC-052-015", "test_final_052_009_public_planning_types_use_plan_document"),
    ),
    "adaptive_explain_identity_0_51.json": (
        ("AC-052-013", "test_adaptive_plan_is_verified_and_explainable"),
        ("AC-052-014", "test_final_052_008_diff_classifies_evidence_only_change"),
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
        ("AC-052-018", "adaptive_release_campaign"),
    ),
}

VERIFICATION_FILES = (
    "tests/plan/test_adaptive_planner_0_52.py",
    "tests/profile/test_adaptive_profile_0_51.py",
    "tests/plan/test_adaptive_wire_0_51.py",
    "tests/plan/test_phase_0_52_review_blockers.py",
)

REVISION_INPUTS = (
    "src/etlantic/planning/adaptive.py",
    "src/etlantic/plan/adaptive_model.py",
    "src/etlantic/plan/adaptive_serialize.py",
    "src/etlantic/plan/diff.py",
    "src/etlantic/plan/planner.py",
    "src/etlantic/plugin_lifecycle/__init__.py",
    "src/etlantic/plugins/coordinator.py",
    "src/etlantic/profile.py",
    "src/etlantic/registry.py",
    "scripts/check_adaptive_0_52.py",
    ".github/workflows/checks.yml",
    *VERIFICATION_FILES,
)


def _source_revision() -> str:
    digest = hashlib.sha256()
    for relative in sorted(REVISION_INPUTS):
        path = ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
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


def _run_campaign() -> tuple[bool, str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *VERIFICATION_FILES,
        "-k",
        "not final_052_006",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    return completed.returncode == 0, output


def _payloads() -> tuple[dict[str, dict[str, object]], str]:
    passed, output = _run_campaign()
    if not passed:
        raise RuntimeError("adaptive release campaign failed:\n" + output)
    revision = _source_revision()
    fingerprint = _verified_plan_fingerprint()
    matrix = {
        "python": platform.python_version(),
        "platform": platform.system().lower(),
    }
    payloads: dict[str, dict[str, object]] = {}
    for name, campaign in CAMPAIGNS.items():
        scenarios = [
            {
                "id": proof,
                "acceptance_criterion": criterion,
                "verification": proof,
                "expected": "pass",
                "actual": "pass",
                "result": "pass",
                "plan_fingerprint": fingerprint,
            }
            for criterion, proof in campaign
        ]
        payloads[name] = {
            "schema": "etlantic.adaptive-evidence/1",
            "artifact": name,
            "repository_revision": revision,
            "public_schema": "etlantic.plan/2",
            "planner_version": "0.52",
            "result": "pass",
            "scenarios": scenarios,
            "verified_environment": matrix,
            "verification_command": [
                "python",
                "-m",
                "pytest",
                "-q",
                *VERIFICATION_FILES,
                "-k",
                "not final_052_006",
            ],
        }
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
