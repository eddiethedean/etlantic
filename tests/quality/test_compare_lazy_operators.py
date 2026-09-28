"""Regression tests for lazy quality comparison dispatch."""

from __future__ import annotations

from etlantic.quality import (
    QualityRuleset,
    evaluate_rule,
    rule_compare,
    split_by_quality,
)


class EqualityOnly:
    """An object that supports equality and rejects unrelated operators."""

    def __eq__(self, other: object, /) -> bool:
        return other == "expected"

    def __ne__(self, other: object, /) -> bool:
        raise AssertionError("ne should not run for an eq comparison")

    def __lt__(self, other: object, /) -> bool:
        raise AssertionError("lt should not run for an eq comparison")

    def __le__(self, other: object, /) -> bool:
        raise AssertionError("le should not run for an eq comparison")

    def __gt__(self, other: object, /) -> bool:
        raise AssertionError("gt should not run for an eq comparison")

    def __ge__(self, other: object, /) -> bool:
        raise AssertionError("ge should not run for an eq comparison")


def test_dictionary_equality_passes_quality_gate() -> None:
    rows = [{"x": {"a": 1}}]
    rules = QualityRuleset(rules=(rule_compare("x", "eq", {"a": 1}),))

    accepted, rejected, diagnostics = split_by_quality(rows, rules)

    assert accepted == rows
    assert rejected == []
    assert diagnostics == []


def test_inequality_accepts_values_with_unrelated_ordering_types() -> None:
    rule = rule_compare("x", "ne", 1)

    assert evaluate_rule(rule, {"x": "1"}) is None


def test_requested_incompatible_ordering_reports_type_error() -> None:
    rule = rule_compare("x", "lt", 1)

    assert evaluate_rule(rule, {"x": {"a": 1}}) == "x compare 'lt' type error"


def test_only_requested_comparison_operator_is_called() -> None:
    rule = rule_compare("x", "eq", "expected")

    assert evaluate_rule(rule, {"x": EqualityOnly()}) is None
