#!/usr/bin/env python3
"""Fail-closed validation for the checked-in 0.50 portable contract artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, cast

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

EXPECTED_SCHEMAS = {
    "portable_evidence_index_0_50.json": "etlantic.portable-evidence-index/1",
    "portable_baseline_contract_0_50.json": "etlantic.portable-baseline/1",
    "portable_requirement_support_0_50.json": "etlantic.portable-requirement-support/1",
    "portable_pushdown_contract_0_50.json": "etlantic.portable-pushdown/1",
    "portable_claim_coverage_0_50.json": "etlantic.portable-claim-coverage/1",
    "portable_local_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_polars_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_pandas_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_sql_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_pyspark_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_datafusion_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_duckdb_pushdown_0_50.json": "etlantic.portable-pushdown-evidence/1",
    "portable_cross_engine_0_50.json": "etlantic.portable-cross-engine/1",
    "portable_canonical_pipeline_0_50.json": "etlantic.portable-canonical-pipeline/1",
    "portable_adaptive_handoff_0_50.json": "etlantic.portable-adaptive-handoff/1",
    "portable_dependency_security_0_50.json": "etlantic.portable-dependency-security/1",
    "FINDINGS_0_50.md": "markdown/1",
    "MIGRATION_0_49_TO_0_50.md": "markdown/1",
    "WHATS_NEW_0_50.md": "markdown/1",
}

EXPECTED_SOL_FINDINGS = frozenset(f"SOL-050-{index:03d}" for index in range(1, 21))
EXPECTED_FINAL_FINDINGS = frozenset(f"FINAL-050-{index:03d}" for index in range(1, 7))


def validate_findings_ledger(findings_doc: str) -> None:
    """Require every known review finding to have an explicit resolution."""
    expected = EXPECTED_SOL_FINDINGS | EXPECTED_FINAL_FINDINGS
    found = set(re.findall(r"(?:SOL|FINAL)-050-\d{3}", findings_doc))
    if found != expected:
        raise SystemExit("findings ledger is incomplete")
    for finding_id in sorted(expected):
        row = next(
            (line for line in findings_doc.splitlines() if f"| {finding_id} |" in line),
            "",
        )
        if not row or "resolved" not in row.lower():
            raise SystemExit(f"findings ledger does not resolve {finding_id}")
    if "Sol re-review pending" not in findings_doc:
        raise SystemExit("findings ledger must retain the independent review status")


def validate_artifact_schema(name: str, schema: object) -> None:
    """Require the frozen schema assigned to an evidence artifact."""
    expected = EXPECTED_SCHEMAS.get(name)
    if expected is None or schema != expected:
        raise SystemExit(f"invalid evidence schema: {name}")


def validate_cross_engine_digests(payload: dict[str, object]) -> None:
    """Require normalized, PostgreSQL, and SQLite canonical results to agree."""
    normalized = payload.get("normalized_result_digest")
    if not re.fullmatch(r"[0-9a-f]{64}", str(normalized or "")):
        raise SystemExit("cross-engine digest must be derived from canonical output")
    canonical = payload.get("canonical_result_digests")
    if (
        not isinstance(canonical, dict)
        or set(canonical) != {"postgresql", "sqlite"}
        or any(
            not re.fullmatch(r"[0-9a-f]{64}", str(value))
            for value in canonical.values()
        )
        or normalized != canonical["postgresql"]
        or canonical["postgresql"] != canonical["sqlite"]
    ):
        raise SystemExit("cross-engine canonical digests are incomplete")


def validate_adaptive_lowering_binding(
    candidate: dict[str, object],
    requirements: dict[str, Any],
    support_findings: dict[str, dict[str, Any]],
    resolved: dict[str, str | None],
) -> None:
    """Require lowering records to match the candidate's support findings exactly."""
    lowered = sorted(
        key for key, value in requirements.items() if value == "supported_with_lowering"
    )
    expected_groups: dict[
        tuple[str, str, tuple[object, ...], tuple[object, ...]], list[str]
    ] = {}
    for requirement in lowered:
        finding_id = resolved.get(requirement)
        finding = (
            support_findings.get(str(finding_id)) if finding_id is not None else None
        )
        if not isinstance(finding, dict):
            raise SystemExit("adaptive lowering evidence is incomplete")
        lowering_id = str(finding.get("lowering_id") or "")
        proof = str(finding.get("proof_reference") or "")
        conditions = tuple(finding.get("conditions") or ())
        effects = tuple(finding.get("physical_effects") or ())
        if not lowering_id or not proof or not effects:
            raise SystemExit("adaptive lowering evidence is incomplete")
        expected_groups.setdefault(
            (lowering_id, proof, conditions, effects), []
        ).append(requirement)
    expected = [
        {
            "id": lowering_id,
            "requirements": sorted(group_requirements),
            "proof": proof,
            "conditions": list(conditions),
            "physical_effects": list(effects),
        }
        for (lowering_id, proof, conditions, effects), group_requirements in sorted(
            expected_groups.items(), key=lambda item: item[0]
        )
    ]
    raw_lowerings = candidate.get("lowerings")
    if raw_lowerings is None:
        singular = candidate.get("lowering")
        raw_lowerings = [] if singular is None else [singular]
    if not isinstance(raw_lowerings, list) or any(
        not isinstance(item, dict) for item in raw_lowerings
    ):
        raise SystemExit("adaptive lowering evidence is incomplete")
    actual = [dict(item) for item in cast(list[dict[str, object]], raw_lowerings)]
    if candidate.get("lowering") is not None and len(expected) != 1:
        raise SystemExit("adaptive lowering evidence is not evidence-backed")
    if candidate.get("lowering") is not None and len(expected) == 1:
        singular = candidate.get("lowering")
        if not isinstance(singular, dict) or not actual or singular != actual[0]:
            raise SystemExit("adaptive lowering evidence is not evidence-backed")
    if sorted(actual, key=lambda item: json.dumps(item, sort_keys=True)) != sorted(
        expected, key=lambda item: json.dumps(item, sort_keys=True)
    ):
        raise SystemExit("adaptive lowering evidence is not evidence-backed")


def validate_adaptive_target_binding(
    candidate: dict[str, object],
    *,
    node: str,
    seen_targets: set[tuple[str, str]],
) -> str:
    """Require each candidate to bind to one unique support-report target."""
    support_report = candidate.get("support_report")
    target = candidate.get("target")
    report_target = (
        support_report.get("target") if isinstance(support_report, dict) else None
    )
    if (
        not isinstance(target, dict)
        or not isinstance(report_target, dict)
        or target != report_target
    ):
        raise SystemExit("adaptive candidate target is not evidence-backed")
    target_key = json.dumps(target, sort_keys=True, separators=(",", ":"))
    target_identity = (node, target_key)
    if target_identity in seen_targets:
        raise SystemExit("adaptive placement target is ambiguous")
    seen_targets.add(target_identity)
    return target_key


def validate_adaptive_target_matrix(
    targets_by_node: dict[str, set[str]], nodes: list[object]
) -> None:
    """Require every logical node to retain the same target inventory."""
    node_ids = {str(node) for node in nodes if isinstance(node, str) and node}
    if not node_ids or node_ids != set(targets_by_node):
        raise SystemExit("adaptive target matrix does not cover every node")
    inventories = [targets_by_node[node] for node in sorted(node_ids)]
    if not inventories[0] or any(
        inventory != inventories[0] for inventory in inventories[1:]
    ):
        raise SystemExit("adaptive target matrix does not cover every node and target")


def validate_adaptive_selection(evaluation: dict[str, Any]) -> None:
    """Require recorded selections to reference the evaluated candidates.

    The handoff is evidence, so checking only the selected value's JSON type is
    insufficient: a fabricated candidate id (or an ineligible candidate) would
    otherwise pass the release verifier after the artifact digest is updated.
    """
    candidates = evaluation.get("candidates")
    nodes = evaluation.get("nodes")
    if not isinstance(candidates, list) or not isinstance(nodes, list):
        raise SystemExit("adaptive candidate selection is incomplete")
    node_ids = [node for node in nodes if isinstance(node, str) and node]
    if len(node_ids) != len(nodes) or len(set(node_ids)) != len(node_ids):
        raise SystemExit("adaptive candidate selection has duplicate or invalid nodes")

    by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise SystemExit("adaptive candidate selection is incomplete")
        node = candidate.get("node")
        candidate_id = candidate.get("id")
        if not isinstance(node, str) or not isinstance(candidate_id, str):
            raise SystemExit("adaptive candidate selection is incomplete")
        identity = (node, candidate_id)
        if identity in by_identity:
            raise SystemExit("adaptive candidate selection has duplicate ids")
        by_identity[identity] = candidate

    selected = evaluation.get("selected")
    if len(node_ids) == 1 and not isinstance(selected, dict):
        selected_by_node: dict[str, object] = {node_ids[0]: selected}
    elif isinstance(selected, dict):
        if set(selected) != set(node_ids):
            raise SystemExit("adaptive candidate selection is invalid")
        selected_by_node = selected
    else:
        raise SystemExit("adaptive candidate selection is invalid")

    graph_valid = evaluation.get("graph_valid")
    graph_failures = evaluation.get("graph_failures")
    if graph_valid is True and graph_failures:
        raise SystemExit("graph-valid adaptive selection records graph failures")
    for node in node_ids:
        candidate_id = selected_by_node.get(node)
        if candidate_id is None:
            if graph_valid is True:
                raise SystemExit("graph-valid adaptive selection is incomplete")
            continue
        if not isinstance(candidate_id, str):
            raise SystemExit("adaptive candidate selection is invalid")
        candidate = by_identity.get((node, candidate_id))
        if candidate is None:
            raise SystemExit("adaptive selection references an unknown candidate")
        if graph_valid is True and candidate.get("eligible") is not True:
            raise SystemExit(
                "graph-valid adaptive selection chose an ineligible candidate"
            )


def main() -> int:
    if set(EXPECTED_SCHEMAS) != REQUIRED:
        raise SystemExit("evidence schema map does not cover the frozen artifact set")
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
    required_manifest_keys = {
        "plan",
        "profiles",
        "profile_aliases",
        "actions",
        "scalar_functions",
        "aggregate_functions",
        "operators",
        "types",
        "join_modes",
        "collision_policy",
        "union_modes",
        "semantic_modes",
        "function_arities",
        "defaults",
        "semantic_rules",
        "leaf_fixture_ids",
        "literal_constraints",
        "action_parameters",
        "aggregate_empty_results",
        "numeric_rules",
        "string_unicode_rules",
        "multi_input_identity",
        "output_contract",
    }
    if not required_manifest_keys.issubset(manifest):
        raise SystemExit("baseline manifest is missing normative contract fields")
    aliases = manifest.get("profile_aliases")
    if not isinstance(aliases, dict):
        raise SystemExit("baseline profile aliases must be an object")
    expected_aliases = {
        "dtcs:profile/portable-relational-kernel/2": "dtcs:profile/portable-relational-kernel/1",
        "dtcs:profile/portable-relational/2": "dtcs:profile/portable-relational/1",
    }
    for alias, canonical in expected_aliases.items():
        details = aliases.get(alias)
        if (
            not isinstance(details, dict)
            or details.get("canonical") != canonical
            or details.get("proof") != "exact-vocabulary-equivalence"
            or canonical not in manifest.get("profiles", [])
        ):
            raise SystemExit(
                f"profile alias lacks normative equivalence proof: {alias}"
            )
    from etlantic.transform.portable_baseline import baseline_manifest

    if manifest != baseline_manifest():
        raise SystemExit("baseline evidence manifest differs from runtime manifest")
    index = json.loads((EVIDENCE / "portable_evidence_index_0_50.json").read_text())
    validate_artifact_schema("portable_evidence_index_0_50.json", index.get("schema"))
    repository_commit = str(index.get("repository_commit") or "")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", repository_commit):
        raise SystemExit("evidence index repository_commit is invalid")
    if repository_commit != head:
        # Generated evidence necessarily changes the evidence tree after the
        # source revision is committed.  Accept only that single, immediate
        # evidence commit; accepting an arbitrary ancestor allows stale source
        # claims to pass under a newer implementation.
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", f"{repository_commit}..{head}"],
            cwd=ROOT,
            text=True,
        ).splitlines()
        commits = int(
            subprocess.check_output(
                ["git", "rev-list", "--count", f"{repository_commit}..{head}"],
                cwd=ROOT,
                text=True,
            ).strip()
        )
        if commits != 1 or any(
            not path.startswith("docs/11_DEVELOPMENT/evidence/portable_0_50/")
            for path in changed
        ):
            raise SystemExit(
                "evidence repository_commit must be HEAD or the immediate "
                "source parent of an evidence-only commit"
            )
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    )
    if dirty.strip():
        raise SystemExit("qualification evidence requires a clean worktree")
    source_digest = index.get("source_tree_digest")
    if not isinstance(source_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", source_digest
    ):
        raise SystemExit("evidence index source_tree_digest is missing or invalid")
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    digest = hashlib.sha256()
    evidence_prefix = b"docs/11_DEVELOPMENT/evidence/portable_0_50/"
    for raw in sorted(
        item for item in tracked if item and not item.startswith(evidence_prefix)
    ):
        digest.update(raw)
        digest.update(b"\0")
        digest.update((ROOT / raw.decode("utf-8")).read_bytes())
        digest.update(b"\0")
    if digest.hexdigest() != source_digest:
        raise SystemExit("evidence source tree differs from the recorded qualification")
    if index.get("result") not in {"pass", "blocked"}:
        raise SystemExit(
            "evidence index result must be pass or an explicit blocked no-go"
        )
    if index.get("result") == "pass" and index.get("qualification") != "qualified":
        raise SystemExit("passing evidence requires qualification=qualified")
    if index.get("result") == "blocked" and index.get("qualification") != "no-go":
        raise SystemExit("blocked evidence requires qualification=no-go")
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
    metadata = index.get("artifact_metadata")
    if not isinstance(metadata, dict) or set(metadata) != listed:
        raise SystemExit("evidence index must provide metadata for every artifact")
    for name in listed:
        item = metadata.get(name)
        schema = EXPECTED_SCHEMAS[name]
        artifact_schema = (
            json.loads((EVIDENCE / name).read_text()).get("schema")
            if name.endswith(".json")
            else "markdown/1"
        )
        if (
            not isinstance(item, dict)
            or item.get("path") != name
            or not str(item.get("id") or "").strip()
            or item.get("schema") != schema
            or artifact_schema != schema
            or item.get("sha256") != digests.get(name)
            or not str(item.get("command") or "").strip()
            or not isinstance(item.get("environment"), dict)
            or item.get("result") != "pass"
        ):
            raise SystemExit(f"evidence index metadata is incomplete: {name}")
    for name in REQUIRED - {"portable_evidence_index_0_50.json"}:
        artifact = EVIDENCE / name
        if artifact.suffix == ".json":
            payload = json.loads(artifact.read_text())
            if (
                payload.get("schema") != EXPECTED_SCHEMAS[name]
                or "repository_commit" not in payload
                or "result" not in payload
            ):
                raise SystemExit(f"artifact metadata is incomplete: {name}")
            if payload.get("repository_commit") != repository_commit:
                raise SystemExit(f"artifact commit differs from evidence index: {name}")
            if payload.get("source_tree_digest") != source_digest:
                raise SystemExit(
                    f"artifact source digest differs from evidence index: {name}"
                )
            if (
                not isinstance(payload.get("command"), str)
                or not payload["command"].strip()
            ):
                raise SystemExit(f"artifact command is missing: {name}")
            if not isinstance(payload.get("environment"), dict):
                raise SystemExit(f"artifact environment is missing: {name}")
            result = payload.get("result")
            if result not in {"pass", "blocked"}:
                raise SystemExit(f"artifact has non-final result: {name}")
            if (
                result == "blocked"
                and not str(payload.get("notes") or payload.get("note") or "").strip()
            ):
                raise SystemExit(
                    f"blocked artifact lacks a blocker explanation: {name}"
                )
            if index.get("result") == "pass" and result != "pass":
                raise SystemExit(
                    f"qualified index references non-passing artifact: {name}"
                )
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digests.get(name) != digest:
            raise SystemExit(f"evidence digest mismatch: {name}")
    support = json.loads(
        (EVIDENCE / "portable_requirement_support_0_50.json").read_text()
    )
    from etlantic.transform.compiler import validate_requirement_support_payload

    reports = support.get("reports")
    if not isinstance(reports, dict) or set(reports) != {
        "local",
        "polars",
        "pandas",
        "sql",
        "pyspark",
        "datafusion",
        "duckdb",
    }:
        raise SystemExit("requirement evidence does not cover all seven engines")
    for engine, report in reports.items():
        try:
            validate_requirement_support_payload(report)
        except ValueError as exc:
            raise SystemExit(
                f"invalid requirement evidence for {engine}: {exc}"
            ) from exc
        if not report.get("requirements") or not report.get("findings"):
            raise SystemExit(f"requirement evidence is empty for {engine}")
        requirements = {
            str(item.get("id")): item for item in report.get("requirements") or []
        }
        findings_by_requirement = {
            str(item.get("requirement")): item for item in report.get("findings") or []
        }
        for requirement_id, requirement in requirements.items():
            if requirement.get("applicability") == "not_applicable":
                continue
            if requirement.get("obligation") != "required":
                continue
            finding = findings_by_requirement.get(requirement_id)
            if finding is None or finding.get("support") not in {
                "supported_exact",
                "supported_with_lowering",
            }:
                raise SystemExit(
                    f"required support evidence is not positive for {engine}: {requirement_id}"
                )
    coverage = json.loads((EVIDENCE / "portable_claim_coverage_0_50.json").read_text())
    claims = coverage.get("claims")
    expected_fixtures = sorted(set((manifest.get("leaf_fixture_ids") or {}).values()))
    if not isinstance(claims, list) or {item.get("engine") for item in claims} != set(
        reports
    ):
        raise SystemExit("claim coverage must contain exactly one claim per engine")
    if coverage.get("required_fixture_ids") != expected_fixtures:
        raise SystemExit("claim coverage fixture inventory differs from baseline")
    expected_matrix = {
        ("local", "host", None),
        ("polars", "eager", None),
        ("polars", "lazy", None),
        ("pandas", "eager", None),
        ("sql", "relation", "sqlite"),
        ("sql", "relation", "postgresql"),
        ("pyspark", "native", "jvm"),
        ("datafusion", "lazy", "native"),
        ("duckdb", "lazy", "native"),
    }
    matrix = coverage.get("qualification_matrix")
    campaigns = coverage.get("campaign_results")
    campaign_ids = {
        item.get("id")
        for item in campaigns
        if isinstance(item, dict)
        and item.get("result") == "pass"
        and item.get("exit_code") == 0
    }
    if (
        not isinstance(matrix, list)
        or not isinstance(campaigns, list)
        or len(campaign_ids) != len(campaigns)
        or len(campaign_ids) < 4
        or {
            (item.get("engine"), item.get("mode"), item.get("dialect"))
            for item in matrix
            if isinstance(item, dict)
        }
        != expected_matrix
        or any(
            item.get("result") != "pass"
            or not item.get("campaign_ids")
            or not set(item.get("campaign_ids") or {}).issubset(campaign_ids)
            or set(item.get("campaign_ids") or ())
            != (
                {f"public-{item.get('dialect')}", f"canonical-{item.get('dialect')}"}
                if item.get("engine") == "sql"
                else campaign_ids
            )
            for item in matrix
            if isinstance(item, dict)
        )
    ):
        raise SystemExit("qualification matrix is incomplete or not passing")
    from etlantic.testing.portable_fixtures import FIXTURES

    fixture_names = {case.name for case in FIXTURES}
    bindings = manifest.get("leaf_fixture_ids") or {}
    if set(bindings.values()) - fixture_names:
        raise SystemExit(
            "baseline manifest references fixture IDs absent from the corpus"
        )
    for claim in claims:
        if claim.get("fixture_coverage") != "complete":
            raise SystemExit("claim coverage is not complete")
        if claim.get("required_fixture_ids") != expected_fixtures:
            raise SystemExit("claim is missing a baseline fixture binding")
        if claim.get("fixture_bindings") != bindings:
            raise SystemExit("claim fixture bindings differ from the baseline manifest")
        fixture_ids = claim.get("fixture_ids")
        if not isinstance(fixture_ids, list) or not set(expected_fixtures).issubset(
            fixture_ids
        ):
            raise SystemExit(
                "claim fixture coverage is not backed by selected fixtures"
            )
        fixture_results = claim.get("fixture_results")
        if not isinstance(fixture_results, list) or {
            item.get("fixture_id") for item in fixture_results if isinstance(item, dict)
        } != set(fixture_ids):
            raise SystemExit("claim fixture results do not cover the selected fixtures")
        if any(
            not isinstance(item, dict)
            or item.get("result") != "pass"
            or not isinstance(item.get("command"), str)
            or not item["command"].strip()
            for item in fixture_results
        ):
            raise SystemExit("claim fixture result is missing a passing command link")
        modes = claim.get("execution_modes")
        if not isinstance(modes, dict) or not {"eager", "lazy"}.issubset(modes):
            raise SystemExit("claim is missing eager/lazy execution dimensions")
        if not isinstance(claim.get("semantic_modes"), list):
            raise SystemExit("claim is missing semantic mode dimensions")
        mode_results = claim.get("mode_results")
        if not isinstance(mode_results, list) or any(
            item.get("result") != "pass"
            for item in mode_results
            if isinstance(item, dict)
        ):
            raise SystemExit("claim is missing passing mode results")
    pushdown = json.loads(
        (EVIDENCE / "portable_pushdown_contract_0_50.json").read_text()
    )
    proofs = pushdown.get("proofs")
    findings = pushdown.get("findings")
    if not isinstance(proofs, dict) or not isinstance(findings, list):
        raise SystemExit("pushdown evidence lacks executable proof records")
    for item in findings:
        if item.get("obligation") != "required":
            continue
        proof = str(item.get("proof_reference") or "")
        engine = str(item.get("engine") or "")
        target = str(item.get("target") or "")
        expected = f"native-execution:{engine}:{target}"
        action_proof = ((proofs.get(engine) or {}).get("actions") or {}).get(target)
        if (
            proof != expected
            or not isinstance(action_proof, dict)
            or action_proof.get("proof_id") != expected
            or not action_proof.get("native_explain_digest")
            or not action_proof.get("action_explain_digest")
            or not action_proof.get("action_native_digest")
            or not action_proof.get("result_digest")
            or action_proof.get("host_fallback") is not False
            or action_proof.get("proof_basis") != "native_explain_and_execution_trace"
        ):
            raise SystemExit("required pushdown finding lacks native execution proof")
        if engine in {"sql", "duckdb"} and not {
            "materialization",
            "lost_fusion",
        }.issubset(set(action_proof.get("physical_effects") or ())):
            raise SystemExit(
                "SQL/DuckDB pushdown proof omits temporary materialization effects"
            )
        if engine == "sql":
            sqlite_execution = (proofs.get(engine) or {}).get("sqlite_execution")
            if (
                not isinstance(sqlite_execution, dict)
                or not re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(sqlite_execution.get("result_digest") or ""),
                )
                or not re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(sqlite_execution.get("native_explain_digest") or ""),
                )
                or sqlite_execution.get("host_fallback") is not False
                or not isinstance(sqlite_execution.get("action_native_digests"), dict)
                or not isinstance(sqlite_execution.get("action_explain_digests"), dict)
            ):
                raise SystemExit("SQL pushdown proof lacks SQLite execution evidence")
    adaptive = json.loads(
        (EVIDENCE / "portable_adaptive_handoff_0_50.json").read_text()
    )
    adaptive_fixtures = adaptive.get("fixtures")
    adaptive_command = str(adaptive.get("command") or "")
    if (
        not isinstance(adaptive_fixtures, list)
        or not adaptive_fixtures
        or any(
            not isinstance(fixture, str) or fixture not in adaptive_command
            for fixture in adaptive_fixtures
        )
    ):
        raise SystemExit(
            "adaptive handoff must link each recorded fixture to its executed command"
        )
    scenarios = adaptive.get("scenarios")
    required_scenarios = {
        "partial-required-unknown",
        "preferred-unknown",
        "lowering-effects",
        "graph-valid-alternative",
        "graph-invalid",
        "evidence-drift",
    }
    if (
        not isinstance(scenarios, list)
        or {item.get("id") for item in scenarios if isinstance(item, dict)}
        != required_scenarios
    ):
        raise SystemExit("adaptive handoff scenario coverage is incomplete")
    for scenario in scenarios:
        if (
            not isinstance(scenario, dict)
            or scenario.get("result")
            not in {"pass", "rejected_before_io", "rejected_graph_invalid"}
            or str(scenario.get("fixture") or "") not in adaptive_fixtures
            or str(scenario.get("fixture") or "") not in adaptive_command
        ):
            raise SystemExit(
                "adaptive handoff scenario is not tied to an executed fixture"
            )
        if scenario["id"] != "evidence-drift":
            evaluation = scenario.get("candidate_evaluation")
            if (
                not isinstance(evaluation, dict)
                or not isinstance(evaluation.get("candidates"), list)
                or not evaluation["candidates"]
            ):
                raise SystemExit(
                    "adaptive scenario lacks candidate evaluation evidence"
                )
            seen_targets: set[tuple[str, str]] = set()
            targets_by_node: dict[str, set[str]] = {}
            for candidate in evaluation["candidates"]:
                if (
                    not isinstance(candidate, dict)
                    or not isinstance(candidate.get("id"), str)
                    or not isinstance(candidate.get("node"), str)
                    or not candidate.get("node")
                    or not isinstance(candidate.get("eligible"), bool)
                    or candidate.get("decision")
                    not in {"eligible", "eliminated_before_preference_scoring"}
                    or (
                        candidate["eligible"]
                        and not isinstance(candidate.get("preferred_score"), int)
                    )
                    or (
                        not candidate["eligible"]
                        and candidate.get("preferred_score") is not None
                    )
                ):
                    raise SystemExit("adaptive candidate evaluation is incomplete")
                requirements = candidate.get("requirements")
                if not isinstance(requirements, dict):
                    raise SystemExit("adaptive candidate requirements are missing")
                support_report = candidate.get("support_report")
                if not isinstance(support_report, dict):
                    raise SystemExit("adaptive candidate support evidence is missing")
                target_key = validate_adaptive_target_binding(
                    candidate,
                    node=str(candidate["node"]),
                    seen_targets=seen_targets,
                )
                targets_by_node.setdefault(str(candidate["node"]), set()).add(
                    target_key
                )
                try:
                    validate_requirement_support_payload(support_report)
                except ValueError as exc:
                    raise SystemExit(
                        "adaptive candidate support evidence is invalid"
                    ) from exc
                support_requirements = {
                    str(item["id"]): item for item in support_report["requirements"]
                }
                support_findings = {
                    str(item["requirement"]): item
                    for item in support_report["findings"]
                }
                aliases = {
                    str((item.get("parameters") or {}).get("value")): identifier
                    for identifier, item in support_requirements.items()
                    if (item.get("parameters") or {}).get("value") is not None
                }
                resolved = {
                    requirement: (
                        requirement
                        if requirement in support_findings
                        else aliases.get(requirement)
                    )
                    for requirement in requirements
                }
                if (
                    None in resolved.values()
                    or set(resolved.values())
                    != {
                        identifier
                        for identifier, item in support_requirements.items()
                        if item.get("applicability") == "applicable"
                    }
                    or any(
                        identifier is None
                        or support_findings[identifier].get("support")
                        != requirements[requirement]
                        for requirement, identifier in resolved.items()
                    )
                ):
                    raise SystemExit("adaptive support vector is not evidence-backed")
                validate_adaptive_lowering_binding(
                    candidate,
                    requirements,
                    support_findings,
                    resolved,
                )
            nodes = evaluation.get("nodes")
            if not isinstance(nodes, list) or len(nodes) < 2:
                raise SystemExit(
                    "adaptive evaluation must cover multiple logical nodes"
                )
            validate_adaptive_target_matrix(targets_by_node, nodes)
            if scenario["id"] == "graph-invalid" and (
                evaluation.get("graph_valid") is not False
                or not evaluation.get("graph_failures")
            ):
                raise SystemExit("adaptive graph-invalid fixture is not rejected")
            if scenario["id"] == "graph-valid-alternative" and (
                evaluation.get("graph_valid") is not True
                or evaluation.get("graph_failures")
            ):
                raise SystemExit("adaptive graph-valid alternative is not selected")
            validate_adaptive_selection(evaluation)
    if adaptive.get("execution") != "planning-only; no adaptive execution":
        raise SystemExit("adaptive handoff must declare planning-only execution")
    dependency = json.loads(
        (EVIDENCE / "portable_dependency_security_0_50.json").read_text()
    )
    if "check_portable_0_50_dependencies.py" not in str(
        dependency.get("command") or ""
    ):
        raise SystemExit("dependency evidence must run isolated wheel checks")
    if "isolated_local_conformance" not in set(dependency.get("checks") or ()):
        raise SystemExit("dependency evidence must run isolated Local conformance")
    findings_doc = (EVIDENCE / "FINDINGS_0_50.md").read_text()
    migration_doc = (EVIDENCE / "MIGRATION_0_49_TO_0_50.md").read_text()
    whats_new_doc = (EVIDENCE / "WHATS_NEW_0_50.md").read_text()
    validate_findings_ledger(findings_doc)
    for phrase in ("baseline", "repin", "rollback", "native"):
        if phrase not in migration_doc.lower():
            raise SystemExit("migration guidance is incomplete")
    for phrase in ("Qualified matrix", "Local", "Polars", "SQL", "does not claim"):
        if phrase.lower() not in whats_new_doc.lower():
            raise SystemExit("what's-new qualification matrix is incomplete")
    cross_engine = json.loads(
        (EVIDENCE / "portable_cross_engine_0_50.json").read_text()
    )
    validate_cross_engine_digests(cross_engine)
    print("0.50 evidence artifact set is complete and structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
