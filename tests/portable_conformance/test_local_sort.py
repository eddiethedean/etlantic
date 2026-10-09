"""Regression coverage for Local's canonical relational sort keys."""

from __future__ import annotations

from etlantic.transform.compiler import TransformPlanningContext
from etlantic.transform.local_compiler import LocalTransformCompiler, _apply


def _sort_then_deduplicate(rows: list[dict[str, int]]) -> list[dict[str, int]]:
    sorted_rows = _apply(
        rows,
        "dtcs:sort",
        {
            "keys": [
                {
                    "expression": {"kind": "fieldRef", "target": "quantity"},
                    "direction": "asc",
                }
            ]
        },
        {},
        {},
    )
    return _apply(sorted_rows, "dtcs:deduplicate", {"keys": ["id"]}, {}, {})


def test_local_canonical_sort_selects_same_deduplicated_record_for_any_input_order() -> (
    None
):
    rows = [{"id": 1, "quantity": 4}, {"id": 1, "quantity": 3}]

    assert _sort_then_deduplicate(rows) == [{"id": 1, "quantity": 3}]
    assert _sort_then_deduplicate(list(reversed(rows))) == [{"id": 1, "quantity": 3}]


def test_local_canonical_sort_honors_direction_and_null_placement() -> None:
    rows = [{"quantity": 3}, {"quantity": None}, {"quantity": 4}]

    assert _apply(
        rows,
        "dtcs:sort",
        {
            "keys": [
                {
                    "expression": {"kind": "fieldRef", "target": "quantity"},
                    "direction": "desc",
                    "nulls": "first",
                }
            ]
        },
        {},
        {},
    ) == [{"quantity": None}, {"quantity": 4}, {"quantity": 3}]


def test_local_analysis_rejects_unsupported_sort_expression_shape() -> None:
    report = LocalTransformCompiler().analyze(
        {
            "actions": [
                {
                    "kind": {
                        "action": "dtcs:sort",
                        "parameters": {
                            "keys": [{"expression": {"kind": "futureExpr"}}]
                        },
                    }
                }
            ]
        },
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )

    assert report.supported is False
    assert any(
        finding.requirement == "sort:key_expression" for finding in report.findings
    )


def test_local_analysis_rejects_sort_field_reference_without_target() -> None:
    report = LocalTransformCompiler().analyze(
        {
            "actions": [
                {
                    "kind": {
                        "action": "dtcs:sort",
                        "parameters": {"keys": [{"expression": {"kind": "fieldRef"}}]},
                    }
                }
            ]
        },
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )

    assert report.supported is False
    assert any(
        finding.requirement == "sort:key_expression:field_target"
        for finding in report.findings
    )


def test_local_analysis_rejects_nested_sort_field_reference_without_target() -> None:
    report = LocalTransformCompiler().analyze(
        {
            "actions": [
                {
                    "kind": {
                        "action": "dtcs:sort",
                        "parameters": {
                            "keys": [
                                {
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:lower",
                                        "args": [{"kind": "fieldRef"}],
                                    }
                                }
                            ]
                        },
                    }
                }
            ]
        },
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )

    assert report.supported is False
    finding = next(
        finding
        for finding in report.findings
        if finding.requirement == "sort:key_expression:field_target"
    )
    assert finding.expression_path.endswith("expression.args[0].target")


def test_local_analysis_rejects_sort_binary_expression_without_right_operand() -> None:
    report = LocalTransformCompiler().analyze(
        {
            "actions": [
                {
                    "kind": {
                        "action": "dtcs:sort",
                        "parameters": {
                            "keys": [
                                {
                                    "expression": {
                                        "kind": "binary",
                                        "op": "eq",
                                        "left": {
                                            "kind": "fieldRef",
                                            "target": "quantity",
                                        },
                                    }
                                }
                            ]
                        },
                    }
                }
            ]
        },
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )

    assert report.supported is False
    assert any(
        finding.requirement == "sort:key_expression:binary_operands"
        for finding in report.findings
    )
