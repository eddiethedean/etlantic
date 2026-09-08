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
