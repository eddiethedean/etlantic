"""Regression tests for the frozen phase-0.50 baseline manifest."""

from __future__ import annotations


def test_baseline_manifest_is_normative_and_fixture_complete() -> None:
    from etlantic.testing.portable_fixtures import FIXTURES
    from etlantic.transform.portable_baseline import baseline_manifest

    manifest = baseline_manifest()
    assert {
        "literal_constraints",
        "action_parameters",
        "aggregate_empty_results",
        "numeric_rules",
        "string_unicode_rules",
        "multi_input_identity",
        "output_contract",
    }.issubset(manifest)
    assert manifest["numeric_rules"]["promotion"]["integer:decimal"] == "decimal"
    assert (
        manifest["output_contract"]["validation"]
        == "runtime_contract_validation_required"
    )
    fixture_names = {fixture.name for fixture in FIXTURES}
    assert set(manifest["leaf_fixture_ids"].values()).issubset(fixture_names)


def test_negative_three_state_fixture_is_selected_without_three_state_claim() -> None:
    """A baseline rejection must run when the feature is intentionally absent."""
    from etlantic.testing.portable_fixtures import fixtures_for_capabilities
    from etlantic.transform.local_compiler import LocalTransformCompiler

    capabilities = LocalTransformCompiler().info.capabilities
    selected = fixtures_for_capabilities(
        profiles=capabilities.profiles,
        actions=capabilities.actions,
        functions=capabilities.functions,
        operators=capabilities.operators,
        types=capabilities.types,
        semantic_modes=capabilities.semantic_modes,
        join_modes=capabilities.join_modes,
        union_modes=capabilities.union_modes,
        collision_policies=capabilities.collision_policies,
    )

    assert "three_state_distinct" not in capabilities.semantic_modes
    assert "reject_missing_literal_without_three_state" in {
        case.name for case in selected
    }


def test_profile_aliases_are_normative_and_proven() -> None:
    from etlantic.transform.portable_baseline import baseline_manifest

    aliases = baseline_manifest()["profile_aliases"]
    assert aliases["dtcs:profile/portable-relational-kernel/2"] == {
        "canonical": "dtcs:profile/portable-relational-kernel/1",
        "proof": "exact-vocabulary-equivalence",
    }
    assert aliases["dtcs:profile/portable-relational/2"] == {
        "canonical": "dtcs:profile/portable-relational/1",
        "proof": "exact-vocabulary-equivalence",
    }


def test_relational_pushdown_records_declared_physical_effects() -> None:
    from etlantic.transform.compiler import relational_pushdown_findings

    findings = relational_pushdown_findings(
        {
            "actions": [
                {
                    "id": "filter-1",
                    "kind": {"action": "dtcs:filter"},
                }
            ]
        },
        evidence_fingerprint="evidence",
        physical_effects=("materialization", "lost_fusion"),
    )
    relational = next(item for item in findings if item.boundary == "relational:0")
    assert relational.physical_effects == ("materialization", "lost_fusion")
