"""Regression tests for fail-closed portable evidence validation."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from scripts.check_portable_0_50 import (
    validate_adaptive_lowering_binding,
    validate_adaptive_selection,
    validate_adaptive_target_binding,
    validate_adaptive_target_matrix,
    validate_artifact_schema,
    validate_cross_engine_digests,
    validate_findings_ledger,
    validate_pushdown_campaign,
    validate_pushdown_findings,
    validate_requirement_campaign,
)


def _requirement_campaign_fixture() -> dict[str, object]:
    from scripts.check_portable_0_50 import (
        EXPECTED_CANONICAL_ACTIONS,
        EXPECTED_ENGINES,
    )

    from etlantic.transform.compiler import (
        TransformSupportFinding,
        TransformSupportReport,
        requirement_records_from_mapping,
    )

    evidence = "qualification-evidence"
    definition = {
        "actions": [
            {"id": f"action-{index}", "kind": {"action": action}}
            for index, action in enumerate(sorted(EXPECTED_CANONICAL_ACTIONS))
        ]
    }
    canonical_requirements = requirement_records_from_mapping(
        {"actions": sorted(EXPECTED_CANONICAL_ACTIONS)}, definition=definition
    )
    canonical_findings = tuple(
        TransformSupportFinding(
            code="PMXFORM000",
            requirement=f"action:{action}",
            reason="qualified",
            support="supported_exact",
            evidence_fingerprint=evidence,
        )
        for action in sorted(EXPECTED_CANONICAL_ACTIONS)
    )
    canonical_report = TransformSupportReport(
        supported=True,
        evidence_fingerprint=evidence,
        requirements=canonical_requirements,
        requirement_findings=canonical_findings,
    )
    baseline_report = TransformSupportReport(
        supported=True,
        evidence_fingerprint=evidence,
        requirements=requirement_records_from_mapping({"actions": ["dtcs:filter"]}),
        requirement_findings=(
            TransformSupportFinding(
                code="PMXFORM000",
                requirement="action:dtcs:filter",
                reason="qualified",
                support="supported_exact",
                evidence_fingerprint=evidence,
            ),
        ),
    )
    unsupported_definition = {
        "actions": [{"id": "negative", "kind": {"action": "dtcs:not-supported"}}]
    }
    unsupported_requirements = requirement_records_from_mapping(
        {"actions": ["dtcs:not-supported"]}, definition=unsupported_definition
    )

    def target(engine: str) -> dict[str, str]:
        return {
            "engine": engine,
            "compiler": "fixture",
            "version": "1",
            "package": "fixture-package",
            "implementation": "fixture/1",
        }

    reports = {
        engine: canonical_report.to_requirement_support(target=target(engine))
        for engine in EXPECTED_ENGINES
    }
    baseline_reports = {
        engine: baseline_report.to_requirement_support(target=target(engine))
        for engine in EXPECTED_ENGINES
    }
    negatives: dict[str, list[dict[str, object]]] = {}
    for engine in EXPECTED_ENGINES:
        entries: list[dict[str, object]] = []
        for fixture_id, state, requirements in (
            ("unsupported-action", "unsupported", unsupported_requirements),
            (
                "unavailable-runtime",
                "unavailable",
                requirement_records_from_mapping(
                    {"environment_requirements": ["unavailable-runtime"]}
                ),
            ),
            (
                "unknown-runtime",
                "unknown",
                requirement_records_from_mapping(
                    {"environment_requirements": ["unknown-runtime"]}
                ),
            ),
        ):
            report = TransformSupportReport(
                supported=False,
                evidence_fingerprint=evidence,
                requirements=requirements,
                requirement_findings=(
                    TransformSupportFinding(
                        code="PMXFORM302",
                        requirement=str(requirements[0]["id"]),
                        reason=f"fixture reports {state}",
                        support=state,
                        evidence_fingerprint=evidence,
                    ),
                ),
            ).to_requirement_support(target=target(engine))
            entries.append(
                {
                    "fixture_id": fixture_id,
                    "expected_state": state,
                    "definition_digest": "a" * 64,
                    "provenance": {
                        "kind": (
                            "target_availability_probe"
                            if state == "unavailable"
                            else "compiler_analyze"
                        ),
                        "compiler": "fixture",
                    },
                    "support_report": report,
                }
            )
        negatives[engine] = entries
    return {
        "canonical_definition_fingerprint": "b" * 64,
        "canonical_action_count": len(EXPECTED_CANONICAL_ACTIONS),
        "reports": reports,
        "baseline_reports": baseline_reports,
        "negative_reports": negatives,
    }


def test_evidence_schema_mutation_is_rejected() -> None:
    with pytest.raises(SystemExit, match="invalid evidence schema"):
        validate_artifact_schema(
            "portable_cross_engine_0_50.json",
            "etlantic.portable-cross-engine/999",
        )


def test_cross_engine_digest_mutation_is_rejected() -> None:
    payload = {
        "normalized_result_digest": "a" * 64,
        "canonical_result_digests": {
            "postgresql": "a" * 64,
            "sqlite": "b" * 64,
        },
    }
    with pytest.raises(SystemExit, match="canonical digests"):
        validate_cross_engine_digests(payload)


def test_requirement_campaign_requires_canonical_plan_reports() -> None:
    payload = _requirement_campaign_fixture()
    validate_requirement_campaign(payload)
    payload["reports"] = payload["baseline_reports"]
    with pytest.raises(SystemExit, match="canonical action-level"):
        validate_requirement_campaign(payload)


def test_requirement_campaign_requires_every_negative_state() -> None:
    payload = _requirement_campaign_fixture()
    negative_reports = payload["negative_reports"]
    assert isinstance(negative_reports, dict)
    negative_reports["local"] = [
        item
        for item in negative_reports["local"]
        if item["expected_state"] != "unknown"
    ]
    with pytest.raises(SystemExit, match="negative support corpus"):
        validate_requirement_campaign(payload)


def test_requirement_campaign_rejects_generic_negative_finding_path() -> None:
    from etlantic.transform.compiler import _support_fingerprint

    payload = _requirement_campaign_fixture()
    negative_reports = payload["negative_reports"]
    assert isinstance(negative_reports, dict)
    unsupported = next(
        item
        for item in negative_reports["local"]
        if item["expected_state"] == "unsupported"
    )
    report = unsupported["support_report"]
    assert isinstance(report, dict)
    finding = next(
        item for item in report["findings"] if item["support"] == "unsupported"
    )
    finding["path"] = "findings"
    report["fingerprint"] = _support_fingerprint(report)
    with pytest.raises(SystemExit, match="not plan-scoped"):
        validate_requirement_campaign(payload)


def test_requirement_campaign_rejects_state_only_negative_evidence() -> None:
    payload = _requirement_campaign_fixture()
    negative = payload["negative_reports"]["local"][1]
    del negative["provenance"]
    with pytest.raises(SystemExit, match="execution provenance"):
        validate_requirement_campaign(payload)


def test_adaptive_lowering_mutation_is_rejected() -> None:
    candidate = {
        "requirements": {"dtcs:filter": "supported_with_lowering"},
        "lowering": {
            "id": "lowering/fixture-v1",
            "requirements": ["dtcs:filter"],
            "proof": "proof/fixture-v1",
            "conditions": ["preserve-null"],
            "physical_effects": ["materialization"],
        },
    }
    support_findings = {
        "dtcs@1/actions/dtcs:filter#actions": {
            "lowering_id": "lowering/fixture-v1",
            "proof_reference": "proof/fixture-v1",
            "conditions": ["preserve-null"],
            "physical_effects": ["materialization"],
        }
    }
    resolved: dict[str, str | None] = {
        "dtcs:filter": "dtcs@1/actions/dtcs:filter#actions"
    }
    candidate["lowering"]["proof"] = "proof/fabricated"
    with pytest.raises(SystemExit, match="not evidence-backed"):
        validate_adaptive_lowering_binding(
            candidate, candidate["requirements"], support_findings, resolved
        )


def test_adaptive_target_binding_mutation_is_rejected() -> None:
    candidate = {
        "node": "orders",
        "target": {"engine": "local", "compiler": "fixture", "version": "1"},
        "support_report": {
            "target": {
                "engine": "local",
                "compiler": "fixture",
                "version": "2",
            }
        },
    }
    with pytest.raises(SystemExit, match="target is not evidence-backed"):
        validate_adaptive_target_binding(candidate, node="orders", seen_targets=set())


def test_adaptive_duplicate_target_is_rejected() -> None:
    target = {"engine": "local", "compiler": "fixture", "version": "1"}
    candidate = {"target": target, "support_report": {"target": target}}
    seen_targets: set[tuple[str, str]] = set()
    validate_adaptive_target_binding(
        candidate, node="orders", seen_targets=seen_targets
    )
    with pytest.raises(SystemExit, match="placement target is ambiguous"):
        validate_adaptive_target_binding(
            candidate, node="orders", seen_targets=seen_targets
        )


def test_adaptive_incomplete_target_matrix_is_rejected() -> None:
    with pytest.raises(SystemExit, match="every node and target"):
        validate_adaptive_target_matrix(
            {"orders": {"target-a", "target-b"}, "customers": {"target-a"}},
            ["orders", "customers"],
        )


def test_adaptive_selection_must_reference_an_evaluated_candidate() -> None:
    evaluation = {
        "nodes": ["orders", "customers"],
        "candidates": [
            {"id": "complete", "node": "orders", "eligible": True},
            {"id": "complete", "node": "customers", "eligible": True},
        ],
        "selected": {"orders": "fabricated", "customers": "complete"},
        "graph_valid": True,
        "graph_failures": [],
    }
    with pytest.raises(SystemExit, match="unknown candidate"):
        validate_adaptive_selection(evaluation)


def test_adaptive_graph_valid_selection_cannot_choose_ineligible_candidate() -> None:
    evaluation = {
        "nodes": ["orders", "customers"],
        "candidates": [
            {"id": "partial", "node": "orders", "eligible": False},
            {"id": "complete", "node": "orders", "eligible": True},
            {"id": "complete", "node": "customers", "eligible": True},
        ],
        "selected": {"orders": "partial", "customers": "complete"},
        "graph_valid": True,
        "graph_failures": [],
    }
    with pytest.raises(SystemExit, match="ineligible"):
        validate_adaptive_selection(evaluation)


@pytest.mark.parametrize(
    "missing",
    [
        "SOL-050-019",
        "SOL-050-020",
        "SOL-050-021",
        "SOL-050-024",
        "FINAL-050-006",
        "FINAL-050-010",
    ],
)
def test_findings_ledger_rejects_missing_historical_finding(missing: str) -> None:
    from scripts.check_portable_0_50 import (
        EXPECTED_FINAL_FINDINGS,
        EXPECTED_SOL_FINDINGS,
    )

    findings = EXPECTED_SOL_FINDINGS | EXPECTED_FINAL_FINDINGS
    document = "\n".join(
        f"| {finding_id} | High | resolved by regression evidence |"
        for finding_id in sorted(findings - {missing})
    )
    document += "\nSol re-review pending\n"
    with pytest.raises(SystemExit, match="ledger is incomplete"):
        validate_findings_ledger(document)


def test_findings_ledger_rejects_unresolved_disposition() -> None:
    from scripts.check_portable_0_50 import (
        EXPECTED_FINAL_FINDINGS,
        EXPECTED_SOL_FINDINGS,
    )

    findings = EXPECTED_SOL_FINDINGS | EXPECTED_FINAL_FINDINGS
    document = "\n".join(
        f"| {finding_id} | High | "
        f"{'pending' if finding_id == 'SOL-050-020' else 'resolved'} |"
        for finding_id in sorted(findings)
    )
    document += "\nSol re-review pending\n"
    with pytest.raises(SystemExit, match="does not resolve SOL-050-020"):
        validate_findings_ledger(document)


def test_pushdown_campaign_covers_every_outcome() -> None:
    from scripts.generate_portable_0_50_evidence import (
        PUSHDOWN_OUTCOME_ORDER,
        _pushdown_outcome_fixtures,
    )

    payload = {
        "outcomes": list(PUSHDOWN_OUTCOME_ORDER),
        "outcome_fixtures": _pushdown_outcome_fixtures(),
    }
    validate_pushdown_campaign(payload)


def test_pushdown_campaign_rejects_missing_outcome_fixture() -> None:
    from scripts.generate_portable_0_50_evidence import (
        PUSHDOWN_OUTCOME_ORDER,
        _pushdown_outcome_fixtures,
    )

    fixtures = _pushdown_outcome_fixtures()
    fixtures.pop()
    with pytest.raises(SystemExit, match="outcome corpus is incomplete"):
        validate_pushdown_campaign(
            {
                "outcomes": list(PUSHDOWN_OUTCOME_ORDER),
                "outcome_fixtures": fixtures,
            }
        )


def test_pushdown_campaign_rejects_mutated_lowering_evidence() -> None:
    from scripts.generate_portable_0_50_evidence import (
        PUSHDOWN_OUTCOME_ORDER,
        _pushdown_outcome_fixtures,
    )

    from etlantic.transform.compiler import _support_fingerprint

    fixtures = _pushdown_outcome_fixtures()
    lowered = next(
        item for item in fixtures if item["outcome"] == "pushed_with_lowering"
    )
    report = lowered["support_report"]
    report["pushdown"][0]["lowering_id"] = "lowering/fabricated-v1"
    report["fingerprint"] = _support_fingerprint(report)
    with pytest.raises(SystemExit, match="lowered pushdown evidence is incomplete"):
        validate_pushdown_campaign(
            {
                "outcomes": list(PUSHDOWN_OUTCOME_ORDER),
                "outcome_fixtures": fixtures,
            }
        )


def _pushdown_evidence_fixture() -> dict[str, object]:
    return json.loads(
        (
            Path(__file__).parents[2] / "docs/11_DEVELOPMENT/evidence/portable_0_50/"
            "portable_pushdown_contract_0_50.json"
        ).read_text()
    )


def _pushdown_expected_evidence(payload: dict[str, object]) -> dict[str, str]:
    findings = payload["findings"]
    assert isinstance(findings, list)
    return {
        engine: next(
            item["evidence_fingerprint"]
            for item in findings
            if item["engine"] == engine
        )
        for engine in {
            "local",
            "polars",
            "pandas",
            "sql",
            "pyspark",
            "datafusion",
            "duckdb",
        }
    }


def _refresh_temp_evidence_metadata(evidence: Path) -> None:
    """Keep copied evidence metadata aligned with the current test checkout."""
    root = Path(__file__).parents[2]
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
    digest = hashlib.sha256()
    evidence_prefix = b"docs/11_DEVELOPMENT/evidence/portable_0_50/"
    for raw in sorted(
        item for item in tracked if item and not item.startswith(evidence_prefix)
    ):
        digest.update(raw)
        digest.update(b"\0")
        digest.update((root / raw.decode("utf-8")).read_bytes())
        digest.update(b"\0")
    source_digest = digest.hexdigest()
    index_path = evidence / "portable_evidence_index_0_50.json"
    index = json.loads(index_path.read_text())
    index["source_tree_digest"] = source_digest
    for name in index["artifacts"]:
        path = evidence / name
        if path.suffix == ".json":
            payload = json.loads(path.read_text())
            payload["source_tree_digest"] = source_digest
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        artifact_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        index["digests"][name] = artifact_digest
        index["artifact_metadata"][name]["sha256"] = artifact_digest
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")


def test_pushdown_findings_reject_missing_matrix_entry() -> None:
    payload = _pushdown_evidence_fixture()
    findings = payload["findings"]
    assert isinstance(findings, list)
    findings.pop()
    with pytest.raises(SystemExit, match="findings matrix is incomplete"):
        validate_pushdown_findings(findings, payload["proofs"], payload)


def test_pushdown_findings_reject_malformed_evidence_inventory() -> None:
    payload = _pushdown_evidence_fixture()
    payload["evidence"] = [{} for _ in range(7)]
    with pytest.raises(
        SystemExit, match="pushdown evidence fingerprint inventory is incomplete"
    ):
        validate_pushdown_findings(payload["findings"], payload["proofs"], payload)


def test_pushdown_findings_reject_cross_engine_evidence_binding_mutation() -> None:
    payload = _pushdown_evidence_fixture()
    findings = payload["findings"]
    assert isinstance(findings, list)
    expected = _pushdown_expected_evidence(payload)
    for item in findings:
        if item["engine"] == "sql":
            item["evidence_fingerprint"] = expected["pandas"]
        elif item["engine"] == "pandas":
            item["evidence_fingerprint"] = expected["sql"]
    with pytest.raises(SystemExit, match="not bound to engine evidence"):
        validate_pushdown_findings(
            findings,
            payload["proofs"],
            payload,
            expected_evidence_fingerprints=expected,
        )


def test_production_checker_rejects_digest_updated_missing_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.check_portable_0_50 as checker

    evidence = tmp_path / "portable_0_50"
    shutil.copytree(checker.EVIDENCE, evidence)
    contract_name = "portable_pushdown_contract_0_50.json"
    contract_path = evidence / contract_name
    payload = json.loads(contract_path.read_text())
    payload["findings"].pop()
    contract_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _refresh_temp_evidence_metadata(evidence)
    monkeypatch.setattr(checker, "EVIDENCE", evidence)
    real_check_output = checker.subprocess.check_output

    def clean_status(command: object, **kwargs: object) -> object:
        if command == ["git", "status", "--porcelain"]:
            return "" if kwargs.get("text") else b""
        return real_check_output(command, **kwargs)

    monkeypatch.setattr(checker.subprocess, "check_output", clean_status)
    with pytest.raises(SystemExit, match="findings matrix is incomplete"):
        checker.main()


def test_production_checker_rejects_digest_updated_missing_pushdown_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.check_portable_0_50 as checker

    evidence = tmp_path / "portable_0_50"
    shutil.copytree(checker.EVIDENCE, evidence)
    contract_name = "portable_pushdown_contract_0_50.json"
    contract_path = evidence / contract_name
    payload = json.loads(contract_path.read_text())
    for finding in payload["findings"]:
        finding.pop("evidence_fingerprint", None)
    payload["evidence"] = []
    contract_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _refresh_temp_evidence_metadata(evidence)
    monkeypatch.setattr(checker, "EVIDENCE", evidence)
    real_check_output = checker.subprocess.check_output

    def clean_status(command: object, **kwargs: object) -> object:
        if command == ["git", "status", "--porcelain"]:
            return "" if kwargs.get("text") else b""
        return real_check_output(command, **kwargs)

    monkeypatch.setattr(checker.subprocess, "check_output", clean_status)
    with pytest.raises(
        SystemExit, match="pushdown evidence fingerprint inventory is incomplete"
    ):
        checker.main()


def test_production_checker_accepts_refreshed_current_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.check_portable_0_50 as checker

    evidence = tmp_path / "portable_0_50"
    shutil.copytree(checker.EVIDENCE, evidence)
    _refresh_temp_evidence_metadata(evidence)
    monkeypatch.setattr(checker, "EVIDENCE", evidence)
    real_check_output = checker.subprocess.check_output

    def clean_status(command: object, **kwargs: object) -> object:
        if command == ["git", "status", "--porcelain"]:
            return "" if kwargs.get("text") else b""
        return real_check_output(command, **kwargs)

    monkeypatch.setattr(checker.subprocess, "check_output", clean_status)
    assert checker.main() == 0


def test_production_checker_rejects_coordinated_fingerprint_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refreshed report/index cannot replace compiler-derived identity."""
    import scripts.check_portable_0_50 as checker

    from etlantic.transform.compiler import _support_fingerprint

    evidence = tmp_path / "portable_0_50"
    shutil.copytree(checker.EVIDENCE, evidence)
    fake = "f" * 64
    support_path = evidence / "portable_requirement_support_0_50.json"
    support = json.loads(support_path.read_text())
    for report in support["reports"].values():
        for record in report["evidence"]:
            record["fingerprint"] = fake
        for finding in report["findings"]:
            finding["evidence_fingerprint"] = fake
        for finding in report.get("pushdown", []):
            finding["evidence_fingerprint"] = fake
        report["fingerprint"] = _support_fingerprint(report)
    support_path.write_text(json.dumps(support, indent=2, sort_keys=True) + "\n")
    _refresh_temp_evidence_metadata(evidence)
    monkeypatch.setattr(checker, "EVIDENCE", evidence)
    real_check_output = checker.subprocess.check_output

    def clean_status(command: object, **kwargs: object) -> object:
        if command == ["git", "status", "--porcelain"]:
            return "" if kwargs.get("text") else b""
        return real_check_output(command, **kwargs)

    monkeypatch.setattr(checker.subprocess, "check_output", clean_status)
    with pytest.raises(SystemExit, match="compiler-derived"):
        checker.main()


def test_production_checker_rejects_sql_dialect_controlled_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Evidence cannot select the SQL compiler identity used to verify itself."""
    import scripts.check_portable_0_50 as checker

    from etlantic.transform.compiler import _support_fingerprint
    from etlantic_sql import SqlTransformCompiler

    evidence = tmp_path / "portable_0_50"
    shutil.copytree(checker.EVIDENCE, evidence)
    sqlite_compiler = SqlTransformCompiler(dialect="sqlite")
    sqlite_fingerprint = sqlite_compiler.info.evidence_fingerprint
    support_path = evidence / "portable_requirement_support_0_50.json"
    support = json.loads(support_path.read_text())
    report = support["reports"]["sql"]
    report["target"]["environment"] = dict(sqlite_compiler.info.environment or {})
    for record in report["evidence"]:
        record["fingerprint"] = sqlite_fingerprint
    for finding in report["findings"]:
        finding["evidence_fingerprint"] = sqlite_fingerprint
    for finding in report["pushdown"]:
        finding["evidence_fingerprint"] = sqlite_fingerprint
    report["fingerprint"] = _support_fingerprint(report)
    support_path.write_text(json.dumps(support, indent=2, sort_keys=True) + "\n")

    contract_path = evidence / "portable_pushdown_contract_0_50.json"
    contract = json.loads(contract_path.read_text())
    old_fingerprint = next(
        item["evidence_fingerprint"]
        for item in contract["findings"]
        if item["engine"] == "sql"
    )
    contract["evidence"] = [
        sqlite_fingerprint if value == old_fingerprint else value
        for value in contract["evidence"]
    ]
    for finding in contract["findings"]:
        if finding["engine"] == "sql":
            finding["evidence_fingerprint"] = sqlite_fingerprint
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")

    _refresh_temp_evidence_metadata(evidence)
    monkeypatch.setattr(checker, "EVIDENCE", evidence)
    real_check_output = checker.subprocess.check_output

    def clean_status(command: object, **kwargs: object) -> object:
        if command == ["git", "status", "--porcelain"]:
            return "" if kwargs.get("text") else b""
        return real_check_output(command, **kwargs)

    monkeypatch.setattr(checker.subprocess, "check_output", clean_status)
    with pytest.raises(SystemExit, match="source-controlled authority"):
        checker.main()


def test_production_checker_rejects_coordinated_native_digest_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Native proof digests must match the independent engine attestation."""
    import scripts.check_portable_0_50 as checker

    evidence = tmp_path / "portable_0_50"
    shutil.copytree(checker.EVIDENCE, evidence)
    contract_path = evidence / "portable_pushdown_contract_0_50.json"
    payload = json.loads(contract_path.read_text())
    sql_proof = payload["proofs"]["sql"]
    sql_proof["result_digest"] = "e" * 64
    sql_proof["native_explain_digest"] = "d" * 64
    for action in sql_proof["actions"].values():
        action["result_digest"] = sql_proof["result_digest"]
        action["native_explain_digest"] = sql_proof["native_explain_digest"]
    contract_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    conformance_path = evidence / "portable_sql_conformance_0_50.json"
    conformance = json.loads(conformance_path.read_text())
    conformance["pushdown_proof_attestation"] = sql_proof
    conformance_path.write_text(
        json.dumps(conformance, indent=2, sort_keys=True) + "\n"
    )
    _refresh_temp_evidence_metadata(evidence)
    monkeypatch.setattr(checker, "EVIDENCE", evidence)
    real_check_output = checker.subprocess.check_output

    def clean_status(command: object, **kwargs: object) -> object:
        if command == ["git", "status", "--porcelain"]:
            return "" if kwargs.get("text") else b""
        return real_check_output(command, **kwargs)

    monkeypatch.setattr(checker.subprocess, "check_output", clean_status)
    with pytest.raises(SystemExit, match="source-controlled authority"):
        checker.main()


@pytest.mark.datafusion
def test_datafusion_pushdown_evidence_is_reproducible() -> None:
    """Session-local DataFusion relation names cannot perturb proof digests."""
    pytest.importorskip("datafusion")
    from scripts.generate_portable_0_50_evidence import (
        _compiler_factories,
        _execute_pushdown_fixture,
    )

    compiler = _compiler_factories()["datafusion"]()
    assert _execute_pushdown_fixture(compiler) == _execute_pushdown_fixture(compiler)


def test_pushdown_findings_reject_orphan_native_proof() -> None:
    payload = _pushdown_evidence_fixture()
    proofs = payload["proofs"]
    assert isinstance(proofs, dict)
    actions = proofs["sql"]["actions"]
    assert isinstance(actions, dict)
    del actions["f"]
    with pytest.raises(SystemExit, match="proof action inventory is incomplete"):
        validate_pushdown_findings(payload["findings"], proofs, payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("boundary", "relational:1"),
        ("action", "dtcs:project"),
        ("target", "p"),
        ("outcome", "not_pushed"),
        ("obligation", "preferred"),
    ],
)
def test_pushdown_findings_reject_identity_or_contract_mutation(
    field: str, value: str
) -> None:
    payload = _pushdown_evidence_fixture()
    findings = payload["findings"]
    assert isinstance(findings, list)
    finding = next(
        item for item in findings if item["engine"] == "sql" and item["target"] == "f"
    )
    finding[field] = value
    with pytest.raises(SystemExit):
        validate_pushdown_findings(findings, payload["proofs"], payload)


def test_pushdown_findings_reject_disconnected_action_proof_digest() -> None:
    payload = _pushdown_evidence_fixture()
    proofs = payload["proofs"]
    assert isinstance(proofs, dict)
    action_proof = proofs["sql"]["actions"]["f"]
    assert isinstance(action_proof, dict)
    action_proof["result_digest"] = "0" * 64
    with pytest.raises(SystemExit, match="native pushdown proof is incomplete"):
        validate_pushdown_findings(payload["findings"], proofs, payload)
