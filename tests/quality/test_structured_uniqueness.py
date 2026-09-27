"""Regression coverage for structured portable uniqueness keys."""

from __future__ import annotations

from etlantic.quality.evaluate import split_by_quality
from etlantic.quality.model import QualityRuleset, rule_not_null, rule_uniqueness


def test_uniqueness_handles_list_and_object_values() -> None:
    rules = QualityRuleset(rules=(rule_uniqueness("value"),))

    valid, invalid, diagnostics = split_by_quality(
        [
            {"value": [1, {"nested": ["x", "y"]}]},
            {"value": [1, {"nested": ["x", "y"]}]},
            {"value": {"a": 1, "b": {"c": [2]}}},
            {"value": {"a": 1, "b": {"c": [2]}}},
        ],
        rules,
    )

    assert len(valid) == 2
    assert len(invalid) == 2
    assert [item["row_index"] for item in diagnostics] == [1, 3]
    assert all("duplicate key" in item["message"] for item in diagnostics)


def test_dict_key_order_and_composite_structured_keys_are_canonical() -> None:
    rules = QualityRuleset(
        rules=(rule_uniqueness("ignored", fields=["region", "attributes"]),)
    )
    rows = [
        {"region": ["west", 1], "attributes": {"x": 1, "y": {"z": 2}}},
        {"region": ["west", 1], "attributes": {"y": {"z": 2}, "x": 1}},
        {"region": ["west", 2], "attributes": {"x": 1, "y": {"z": 2}}},
    ]

    valid, invalid, diagnostics = split_by_quality(rows, rules)

    assert valid == [rows[0], rows[2]]
    assert invalid == [rows[1]]
    assert diagnostics[0]["row_index"] == 1


def test_optional_structured_uniqueness_warns_without_rejecting() -> None:
    rules = QualityRuleset(rules=(rule_uniqueness("value", required=False),))
    rows = [{"value": {"items": [1, 2]}}, {"value": {"items": [1, 2]}}]

    valid, invalid, diagnostics = split_by_quality(rows, rules)

    assert valid == rows
    assert invalid == []
    assert diagnostics[0]["severity"] == "warning"
    assert diagnostics[0]["optional"] is True
    assert diagnostics[0]["row_index"] == 1


def test_rejected_row_does_not_consume_structured_uniqueness_key() -> None:
    rules = QualityRuleset(rules=(rule_not_null("name"), rule_uniqueness("value")))
    rows = [
        {"name": None, "value": [1, 2]},
        {"name": "accepted", "value": [1, 2]},
        {"name": "duplicate", "value": [1, 2]},
    ]

    valid, invalid, diagnostics = split_by_quality(rows, rules)

    assert valid == [rows[1]]
    assert invalid == [rows[0], rows[2]]
    assert diagnostics[0]["row_index"] == 0
    assert diagnostics[1]["row_index"] == 2
    assert "duplicate key" in diagnostics[1]["message"]


def test_unsupported_cyclic_uniqueness_value_is_a_row_diagnostic() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)
    rules = QualityRuleset(rules=(rule_uniqueness("value"),))

    valid, invalid, diagnostics = split_by_quality(
        [{"value": cyclic}, {"value": [1]}],
        rules,
    )

    assert valid == [{"value": [1]}]
    assert invalid == [{"value": cyclic}]
    assert diagnostics[0]["row_index"] == 0
    assert "cyclic list" in diagnostics[0]["message"]


def test_uniqueness_key_is_type_aware_for_equal_python_scalars() -> None:
    rules = QualityRuleset(rules=(rule_uniqueness("value"),))

    valid, invalid, diagnostics = split_by_quality(
        [{"value": 1}, {"value": True}],
        rules,
    )

    assert len(valid) == 2
    assert invalid == []
    assert diagnostics == []


def test_signed_zero_is_duplicate_for_scalar_and_nested_float_values() -> None:
    rules = QualityRuleset(rules=(rule_uniqueness("scalar"), rule_uniqueness("nested")))
    rows = [
        {"scalar": 0.0, "nested": [0.0]},
        {"scalar": -0.0, "nested": [-0.0]},
    ]

    valid, invalid, diagnostics = split_by_quality(rows, rules)

    assert valid == [rows[0]]
    assert invalid == [rows[1]]
    assert diagnostics[0]["row_index"] == 1
    assert "duplicate key on scalar" in diagnostics[0]["message"]
    assert "duplicate key on nested" in diagnostics[0]["message"]
