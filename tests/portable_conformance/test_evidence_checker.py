"""Regression tests for fail-closed portable evidence validation."""

from __future__ import annotations

import pytest
from scripts.check_portable_0_50 import (
    validate_adaptive_lowering_binding,
    validate_adaptive_selection,
    validate_adaptive_target_binding,
    validate_adaptive_target_matrix,
    validate_artifact_schema,
    validate_cross_engine_digests,
)


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
