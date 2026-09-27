"""Regression coverage for shared preview and portable scalar semantics."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

import etlantic as etl
from etlantic.transform.column import ColumnExpr
from etlantic.transform.evaluation import (
    ExpressionEvaluationError,
    evaluate_expression,
)
from etlantic.transform.functions import col, concat_ws, to_integer


def _literal(value: object) -> dict[str, object]:
    return {"kind": "literal", "value": value}


def _call(callee: str, *args: object) -> dict[str, object]:
    return {"kind": "call", "callee": callee, "args": list(args)}


def _evaluate(node: Any) -> tuple[Any, list[ExpressionEvaluationError]]:
    errors: list[ExpressionEvaluationError] = []
    result = evaluate_expression(node, {}, on_error=errors.append)
    return result, errors


def _column_call(callee: str, *args: object) -> ColumnExpr:
    return ColumnExpr(
        {"kind": "call", "callee": callee, "args": list(args)},
        functions=frozenset({callee}),
    )


def test_strict_conversion_helpers_share_conversion_diagnostics() -> None:
    cases = (
        (_call("dtcs:cast", _literal("not-an-int"), _literal("integer")), "integer"),
        (_call("dtcs:to_integer", _literal("not-an-int")), "integer"),
        (_call("dtcs:to_decimal", _literal("not-a-decimal")), "decimal"),
        (_call("dtcs:cast", _literal("1e10000"), _literal("number")), "number"),
        (_call("dtcs:to_integer", _literal(Decimal("1.5"))), "integer"),
    )

    for expression, target in cases:
        value, errors = _evaluate(expression)
        assert value is None
        assert [item.code for item in errors] == ["conversion"]
        assert target in str(errors[0])


def test_integer_conversion_rejects_values_outside_signed_int64() -> None:
    for value in (str(2**63), str(-(2**63) - 1)):
        result, errors = _evaluate(_call("dtcs:to_integer", _literal(value)))
        assert result is None
        assert [item.code for item in errors] == ["conversion"]

    for value in (str(-(2**63)), str(2**63 - 1)):
        result, errors = _evaluate(_call("dtcs:to_integer", _literal(value)))
        assert result == int(value)
        assert errors == []


def test_try_cast_is_the_explicit_null_producing_conversion() -> None:
    value, errors = _evaluate(
        _call("dtcs:try_cast", _literal("not-an-int"), _literal("integer"))
    )
    assert value is None
    assert errors == []


def test_try_cast_rejects_an_unsupported_target_type() -> None:
    value, errors = _evaluate(
        _call("dtcs:try_cast", _literal("123"), _literal("not_a_type"))
    )
    assert value is None
    assert [item.code for item in errors] == ["unsupported"]


def test_null_conversion_stays_null_without_a_failure_diagnostic() -> None:
    expressions = (
        _call("dtcs:cast", _literal(None), _literal("integer")),
        _call("dtcs:try_cast", _literal(None), _literal("integer")),
        _call("dtcs:to_integer", _literal(None)),
        _call("dtcs:to_decimal", _literal(None)),
    )
    for expression in expressions:
        value, errors = _evaluate(expression)
        assert value is None
        assert errors == []


def test_decimal_conversion_preserves_decimal_values() -> None:
    result, errors = _evaluate(_call("dtcs:to_decimal", _literal(Decimal("1.20"))))
    assert result == Decimal("1.20")
    assert isinstance(result, Decimal)
    assert errors == []


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
            and_value, and_errors = _evaluate(
                {"kind": "binary", "op": "and", "left": left, "right": right}
            )
            or_value, or_errors = _evaluate(
                {"kind": "binary", "op": "or", "left": left, "right": right}
            )
            assert and_value is and_expected[left_index][right_index]
            assert or_value is or_expected[left_index][right_index]
            assert and_errors == []
            assert or_errors == []

    for value, expected in ((True, False), (False, True), (None, None)):
        result, errors = _evaluate({"kind": "unary", "op": "not", "expr": value})
        assert result is expected
        assert errors == []


def test_null_safe_equality_remains_distinct_from_equality() -> None:
    equal, errors = _evaluate(
        {"kind": "binary", "op": "eq", "left": None, "right": None}
    )
    null_safe_equal, null_safe_errors = _evaluate(
        {"kind": "binary", "op": "null_safe_eq", "left": None, "right": None}
    )
    assert equal is None
    assert null_safe_equal is True
    assert errors == []
    assert null_safe_errors == []


def test_in_uses_sql_null_semantics_for_nullable_candidates() -> None:
    matched, matched_errors = _evaluate(
        _call("dtcs:in", _literal("a"), _literal("a"), _literal(None))
    )
    unmatched, unmatched_errors = _evaluate(
        _call("dtcs:in", _literal("b"), _literal("a"), _literal(None))
    )
    no_null_match, no_null_errors = _evaluate(
        _call("dtcs:in", _literal("b"), _literal("a"))
    )

    assert matched is True
    assert unmatched is None
    assert no_null_match is False
    assert matched_errors == unmatched_errors == no_null_errors == []

    dataset = etl.from_records([{"value": "a"}, {"value": "b"}, {"value": None}])
    assert dataset.filter(col("value").isin("a", None)).preview() == [{"value": "a"}]


def test_concat_ws_skips_null_values_but_propagates_null_separator() -> None:
    joined, errors = _evaluate(
        _call(
            "dtcs:concat_ws",
            _literal("-"),
            _literal("a"),
            _literal(None),
            _literal("b"),
        )
    )
    null_separator, null_separator_errors = _evaluate(
        _call("dtcs:concat_ws", _literal(None), _literal("a"), _literal("b"))
    )

    assert joined == "a-b"
    assert errors == []
    assert null_separator is None
    assert null_separator_errors == []

    dataset = etl.from_records([{"first": "a", "middle": None, "last": "b"}])
    assert dataset.withColumn(
        "joined", concat_ws("-", col("first"), col("middle"), col("last"))
    ).preview() == [{"first": "a", "middle": None, "last": "b", "joined": "a-b"}]


def test_unsupported_expressions_are_diagnosed_even_with_null_arguments() -> None:
    value, call_errors = _evaluate(_call("unknown_function", _literal(None)))
    binary_value, binary_errors = _evaluate(
        {"kind": "binary", "op": "unknown_operator", "left": None, "right": 1}
    )
    assert value is None
    assert [item.code for item in call_errors] == ["unsupported"]
    assert binary_value is None
    assert [item.code for item in binary_errors] == ["unsupported"]


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


def test_preview_filter_preserves_numpy_boolean_scalars() -> None:
    np = pytest.importorskip("numpy")
    dataset = etl.from_records(
        [
            {"flag": np.bool_(True), "value": np.int64(1)},
            {"flag": np.bool_(False), "value": np.int64(0)},
        ]
    )

    direct = dataset.filter(col("flag"))
    compound = dataset.filter(col("flag") & (col("value") > 0))

    assert [bool(row["flag"]) for row in direct.preview()] == [True]
    assert [bool(row["flag"]) for row in compound.preview()] == [True]


def test_runtime_errors_survive_a_full_diagnostic_budget_and_block_export() -> None:
    source = etl.from_records(
        [{"raw": "not-an-int", "unknown": None}],
        limits=etl.InferenceLimits(max_diagnostics=1),
    )
    assert source.diagnostics

    result = source.withColumn("parsed", to_integer(col("raw")))

    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].severity.value == "error"
    assert result.diagnostics[0].code == "INFER_RUNTIME_CONVERSION"
    with pytest.raises(ValueError, match="diagnostics contain errors"):
        result.definition()


def test_unsupported_null_call_is_diagnostic_in_preview_and_blocks_export() -> None:
    source = etl.from_records([{"raw": None}])
    result = source.withColumn(
        "out",
        _column_call("unknown_function", {"kind": "fieldRef", "target": "raw"}),
    )

    assert "INFER_EVALUATION_UNSUPPORTED" in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    with pytest.raises(ValueError, match="diagnostics contain errors"):
        result.definition()


def test_diagnostic_budget_is_applied_to_public_preview_diagnostics() -> None:
    source = etl.from_records([{}], limits=etl.InferenceLimits(max_diagnostics=2))
    result = source.select(
        _column_call("unsupported_0"),
        _column_call("unsupported_1"),
        _column_call("unsupported_2"),
    )

    assert len(result.diagnostics) == 2
    assert {item.code for item in result.diagnostics} == {
        "INFER_EVALUATION_UNSUPPORTED"
    }
    assert all(item.severity.value == "error" for item in result.diagnostics)


def test_runtime_expression_errors_do_not_disappear() -> None:
    result, errors = _evaluate(
        {"kind": "binary", "op": "divide", "left": 1, "right": 0}
    )
    assert result is None
    assert [item.code for item in errors] == ["runtime"]


def test_conversion_diagnostics_round_trip_without_preview_rows() -> None:
    private_value = "sensitive-invalid-conversion-value"
    dataset = etl.from_records([{"raw": private_value}]).withColumn(
        "parsed", to_integer(col("raw"))
    )

    payload = json.dumps(dataset.observation.to_dict(), sort_keys=True)

    assert "INFER_RUNTIME_CONVERSION" in payload
    assert private_value not in payload


def test_preview_integer_overflow_from_numpy_scalar_is_diagnosed() -> None:
    np = pytest.importorskip("numpy")
    dataset = etl.from_records([{"value": np.int64(2**63 - 1)}]).withColumn(
        "overflow", col("value") + 1
    )

    assert dataset.preview() == [{"value": np.int64(2**63 - 1), "overflow": None}]
    assert "INFER_RUNTIME_EVALUATION" in {item.code for item in dataset.diagnostics}
