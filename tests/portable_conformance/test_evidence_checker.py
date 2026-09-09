"""Regression tests for fail-closed portable evidence validation."""

from __future__ import annotations

import json
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


def test_pushdown_findings_reject_missing_matrix_entry() -> None:
    payload = _pushdown_evidence_fixture()
    findings = payload["findings"]
    assert isinstance(findings, list)
    findings.pop()
    with pytest.raises(SystemExit, match="findings matrix is incomplete"):
        validate_pushdown_findings(findings, payload["proofs"], payload)


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
