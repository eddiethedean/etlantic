"""Regression coverage for shared preview and portable scalar semantics."""

from __future__ import annotations

import json
from decimal import Decimal

import etlantic as etl
from etlantic.inference.facade import _eval
from etlantic.transform.functions import col, to_integer


def _literal(value: object) -> dict[str, object]:
    return {"kind": "literal", "value": value}


def _call(callee: str, *args: object) -> dict[str, object]:
    return {"kind": "call", "callee": callee, "args": list(args)}


def test_strict_conversion_helpers_share_conversion_diagnostics() -> None:
    cases = (
        (_call("dtcs:cast", _literal("not-an-int"), _literal("integer")), "integer"),
        (_call("dtcs:to_integer", _literal("not-an-int")), "integer"),
        (_call("dtcs:to_decimal", _literal("not-a-decimal")), "decimal"),
        (_call("dtcs:cast", _literal("1e10000"), _literal("number")), "number"),
        (_call("dtcs:to_integer", _literal(Decimal("1.5"))), "integer"),
    )

    for expression, target in cases:
        diagnostics = []
        assert _eval(expression, {}, diagnostics) is None
        assert [item.code for item in diagnostics] == ["INFER_RUNTIME_CONVERSION"]
        assert target in diagnostics[0].message


def test_try_cast_is_the_explicit_null_producing_conversion() -> None:
    diagnostics = []
    assert (
        _eval(
            _call("dtcs:try_cast", _literal("not-an-int"), _literal("integer")),
            {},
            diagnostics,
        )
        is None
    )
    assert diagnostics == []


def test_null_conversion_stays_null_without_a_failure_diagnostic() -> None:
    expressions = (
        _call("dtcs:cast", _literal(None), _literal("integer")),
        _call("dtcs:try_cast", _literal(None), _literal("integer")),
        _call("dtcs:to_integer", _literal(None)),
        _call("dtcs:to_decimal", _literal(None)),
    )
    for expression in expressions:
        diagnostics = []
        assert _eval(expression, {}, diagnostics) is None
        assert diagnostics == []


def test_decimal_conversion_preserves_decimal_values() -> None:
    result = _eval(_call("dtcs:to_decimal", _literal(Decimal("1.20"))), {})
    assert result == Decimal("1.20")
    assert isinstance(result, Decimal)


def test_preview_boolean_operators_follow_three_valued_truth_tables() -> None:
    truth_values = (True, False, None)
    and_expected = (
        (True, False, None),
        (False, False, False),
        (None, False, None),
    )
    or_expected = (
        (True, True, True),
        (True, False, None),
        (True, None, None),
    )

    for left_index, left in enumerate(truth_values):
        for right_index, right in enumerate(truth_values):
            assert (
                _eval({"kind": "binary", "op": "and", "left": left, "right": right}, {})
                is and_expected[left_index][right_index]
            )
            assert (
                _eval({"kind": "binary", "op": "or", "left": left, "right": right}, {})
                is or_expected[left_index][right_index]
            )

    for value, expected in ((True, False), (False, True), (None, None)):
        assert _eval({"kind": "unary", "op": "not", "expr": value}, {}) is expected


def test_null_safe_equality_remains_distinct_from_equality() -> None:
    assert (
        _eval({"kind": "binary", "op": "eq", "left": None, "right": None}, {}) is None
    )
    assert (
        _eval(
            {"kind": "binary", "op": "null_safe_eq", "left": None, "right": None},
            {},
        )
        is True
    )


def test_filter_uses_true_only_and_reports_invalid_conversion() -> None:
    dataset = etl.from_records(
        [
            {"raw": "10"},
            {"raw": "not-an-int"},
            {"raw": None},
            {"raw": "2"},
        ]
    )

    filtered = dataset.filter(to_integer(col("raw")) > 5)

    assert filtered.preview() == [{"raw": "10"}]
    assert "INFER_RUNTIME_CONVERSION" in {
        diagnostic.code for diagnostic in filtered.diagnostics
    }


def test_unsupported_calls_are_stable_and_diagnostic_budget_is_applied_early() -> None:
    diagnostics = []
    for index in range(10):
        assert (
            _eval(
                _call(
                    f"unsupported_{index}",
                ),
                {},
                diagnostics,
                max_diagnostics=2,
            )
            is None
        )

    assert len(diagnostics) == 2
    assert {item.code for item in diagnostics} == {"INFER_EVALUATION_UNSUPPORTED"}
    assert all(item.severity.value == "error" for item in diagnostics)


def test_runtime_expression_errors_do_not_disappear() -> None:
    diagnostics = []
    assert (
        _eval(
            {"kind": "binary", "op": "divide", "left": 1, "right": 0}, {}, diagnostics
        )
        is None
    )
    assert [item.code for item in diagnostics] == ["INFER_RUNTIME_EVALUATION"]


def test_conversion_diagnostics_round_trip_without_preview_rows() -> None:
    private_value = "sensitive-invalid-conversion-value"
    dataset = etl.from_records([{"raw": private_value}]).withColumn(
        "parsed", to_integer(col("raw"))
    )

    payload = json.dumps(dataset.observation.to_dict(), sort_keys=True)

    assert "INFER_RUNTIME_CONVERSION" in payload
    assert private_value not in payload
