"""Regression tests for fail-closed portable evidence validation."""

from __future__ import annotations

import pytest
from scripts.check_portable_0_50 import (
    validate_adaptive_lowering_binding,
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
