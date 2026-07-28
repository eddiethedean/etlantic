"""Unit tests for provisional etlantic.quality/1."""

from __future__ import annotations

import pytest

from etlantic.quality import (
    QUALITY_SCHEMA,
    QualityExpression,
    QualityRule,
    QualityRuleset,
    UnmappedQualityRuleError,
    UnsupportedQualitySchemaError,
    analyze_quality,
    map_rule_to_contract,
    quality_fingerprint,
    quality_from_dict,
    quality_to_dict,
    upgrade_quality_dict,
    verify_quality_fingerprint,
)
from etlantic.quality.model import (
    rule_compare,
    rule_custom_contract,
    rule_length,
    rule_membership,
    rule_not_null,
    rule_range,
    rule_regex,
    rule_uniqueness,
)


def test_round_trip_and_fingerprint() -> None:
    expr = QualityExpression(
        expression_id="orders-gate",
        ruleset=QualityRuleset(
            name="bronze",
            rules=(
                rule_not_null("order_id"),
                rule_regex("email", r"^[^@]+@[^@]+$"),
            ),
        ),
    )
    fp = quality_fingerprint(expr)
    data = quality_to_dict(expr)
    data["fingerprint"] = fp
    loaded = quality_from_dict(data)
    assert loaded.schema == QUALITY_SCHEMA
    assert loaded.expression_id == "orders-gate"
    assert len(loaded.ruleset.rules) == 2
    verify_quality_fingerprint(loaded)
    assert quality_fingerprint(loaded) == fp


def test_fingerprint_stable_under_key_order() -> None:
    a = QualityExpression(
        ruleset=QualityRuleset(rules=(rule_not_null("a"), rule_range("b", min_value=1)))
    )
    b = QualityExpression(
        ruleset=QualityRuleset(rules=(rule_not_null("a"), rule_range("b", min_value=1)))
    )
    assert quality_fingerprint(a) == quality_fingerprint(b)


def test_unknown_schema_fails_closed() -> None:
    with pytest.raises(UnsupportedQualitySchemaError):
        upgrade_quality_dict(
            {
                "schema": "etlantic.quality/0",
                "expression_id": "x",
                "ruleset": {"rules": []},
            }
        )
    with pytest.raises(UnsupportedQualitySchemaError):
        upgrade_quality_dict({"expression_id": "x", "ruleset": {"rules": []}})


def test_unknown_kind_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown quality rule kind"):
        QualityRule(kind="spark_column", field="x")


def test_contract_map_table() -> None:
    assert map_rule_to_contract(rule_not_null("id")).nullable is False
    assert (
        map_rule_to_contract(rule_range("n", min_value=0, max_value=10)).min_value == 0
    )
    assert map_rule_to_contract(rule_length("s", max_length=8)).max_length == 8
    assert map_rule_to_contract(rule_regex("s", r"\d+")).pattern == r"\d+"
    assert map_rule_to_contract(rule_membership("s", ["a", "b"])).allowed_values == [
        "a",
        "b",
    ]
    assert map_rule_to_contract(rule_compare("n", "ge", 3)).min_value == 3
    assert map_rule_to_contract(rule_uniqueness("id")).unique is True
    custom = map_rule_to_contract(rule_custom_contract("ck_positive", field="n"))
    assert custom.custom[0]["name"] == "ck_positive"


def test_unmapped_regex_without_pattern() -> None:
    with pytest.raises(UnmappedQualityRuleError):
        map_rule_to_contract(QualityRule(kind="regex", field="x", node={}))


def test_analyze_requires_capabilities() -> None:
    expr = QualityExpression(
        ruleset=QualityRuleset(
            rules=(rule_not_null("id"), rule_regex("email", r".+@.+", required=False))
        )
    )
    analysis = analyze_quality(expr)
    assert "quality.not_null" in analysis.required_capabilities
    assert "invalid_row_separation" in analysis.required_capabilities
    assert "quality.regex" in analysis.optional_capabilities
    assert analysis.validation_cost >= 1
    assert analysis.required_rule_count == 1


def test_custom_contract_fails_closed_without_expression() -> None:
    from etlantic.quality import evaluate_rule, split_by_quality

    rule = rule_custom_contract("ck")
    assert evaluate_rule(rule, {"n": 1}) is not None
    valid, invalid, diags = split_by_quality([{"n": 1}], QualityRuleset(rules=(rule,)))
    assert valid == []
    assert len(invalid) == 1
    assert diags[0]["code"] == "PMQTY410"


def test_optional_rule_does_not_reject() -> None:
    from etlantic.quality import split_by_quality

    ruleset = QualityRuleset(
        rules=(rule_regex("email", r"^a@", required=False), rule_not_null("id"))
    )
    valid, invalid, diags = split_by_quality(
        [{"id": 1, "email": "z@x.com"}],
        ruleset,
    )
    assert len(valid) == 1
    assert invalid == []
    soft = [d for d in diags if d.get("optional")]
    assert soft and soft[0]["severity"] == "warning"


def test_invalid_regex_and_range_type_errors_are_reasons() -> None:
    from etlantic.quality import evaluate_rule

    assert "invalid regex" in (evaluate_rule(rule_regex("s", "("), {"s": "x"}) or "")
    assert "type error" in (
        evaluate_rule(rule_range("n", min_value=1), {"n": "x"}) or ""
    )


def test_field_constraints_dict_projects_nullable_and_compare_ops() -> None:
    mapped = map_rule_to_contract(rule_not_null("id"))
    assert mapped.field_constraints_dict()["nullable"] is False
    gt = map_rule_to_contract(rule_compare("n", "gt", 3))
    data = gt.field_constraints_dict()
    assert any(item.get("type") == "compare" for item in data["custom"])
    uniq = map_rule_to_contract(rule_uniqueness("a", fields=("a", "b")))
    assert uniq.field_constraints_dict()["unique_fields"] == ["a", "b"]


def test_recompute_fingerprint_ignores_stale_embedded() -> None:
    expr = QualityExpression(
        ruleset=QualityRuleset(rules=(rule_not_null("id"),)),
        fingerprint="deadbeef",
    )
    data = quality_to_dict(expr)
    loaded = quality_from_dict(data, verify=False, recompute_fingerprint=True)
    assert loaded.fingerprint == quality_fingerprint(
        QualityExpression(ruleset=QualityRuleset(rules=(rule_not_null("id"),)))
    )


def test_public_exports_include_rule_builders() -> None:
    from etlantic import quality as q

    assert hasattr(q, "rule_not_null")
    assert hasattr(q, "PORTABLE_QUALITY_CAPABILITIES")
