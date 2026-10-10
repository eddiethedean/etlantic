"""Regression coverage for Local's canonical relational sort keys."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from etlantic.transform.compiler import (
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
)
from etlantic.transform.local_compiler import LocalTransformCompiler


def _execute_local_actions(
    rows: list[dict[str, Any]], actions: list[tuple[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    plan: dict[str, Any] = {
        "inputs": {"source": {}},
        "actions": [
            {
                "id": f"action_{index}",
                "kind": {
                    "id": f"action_{index}",
                    "action": action,
                    "target": "source" if index == 0 else f"action_{index - 1}",
                    "parameters": parameters,
                },
            }
            for index, (action, parameters) in enumerate(actions)
        ],
        "outputs": {"result": {}},
        "requirements": {
            "dependencies": [
                {
                    "from": f"action_{len(actions) - 1}",
                    "to": "result",
                }
            ]
        },
    }
    compiler = LocalTransformCompiler()
    compiled = compiler.compile(
        plan,
        context=TransformCompileContext("p", "pl", "s", "profile", "local"),
    )
    result = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"source": rows},
            parameters={},
            context=TransformExecutionContext("r", "p", "pl", "s", "local"),
        )
    )
    return result.valid["result"]


def _sort_then_deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _execute_local_actions(
        rows,
        [
            (
                "dtcs:sort",
                {
                    "keys": [
                        {
                            "expression": {
                                "kind": "fieldRef",
                                "target": "quantity",
                            },
                            "direction": "asc",
                        }
                    ]
                },
            ),
            ("dtcs:deduplicate", {"keys": ["id"]}),
        ],
    )


def test_local_canonical_sort_selects_same_deduplicated_record_for_any_input_order() -> (
    None
):
    rows = [{"id": 1, "quantity": 4}, {"id": 1, "quantity": 3}]

    assert _sort_then_deduplicate(rows) == [{"id": 1, "quantity": 3}]
    assert _sort_then_deduplicate(list(reversed(rows))) == [{"id": 1, "quantity": 3}]


def test_local_canonical_sort_honors_direction_and_null_placement() -> None:
    rows = [{"quantity": 3}, {"quantity": None}, {"quantity": 4}]

    assert _execute_local_actions(
        rows,
        [
            (
                "dtcs:sort",
                {
                    "keys": [
                        {
                            "expression": {
                                "kind": "fieldRef",
                                "target": "quantity",
                            },
                            "direction": "desc",
                            "nulls": "first",
                        }
                    ]
                },
            )
        ],
    ) == [{"quantity": None}, {"quantity": 4}, {"quantity": 3}]


@pytest.mark.parametrize(
    "rows",
    [
        [{"id": 1, "quantity": float("nan")}, {"id": 1, "quantity": 1.0}],
        [{"id": 1, "quantity": 1.0}, {"id": 1, "quantity": float("nan")}],
    ],
)
def test_local_sort_rejects_nan_values_before_deduplication(
    rows: list[dict[str, float]],
) -> None:
    with pytest.raises(ValueError, match="sort key values cannot contain NaN"):
        _sort_then_deduplicate(rows)


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
    assert finding.expression_path is not None
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


def test_local_analysis_rejects_sort_call_without_callee() -> None:
    report = LocalTransformCompiler().analyze(
        {
            "actions": [
                {
                    "kind": {
                        "action": "dtcs:sort",
                        "parameters": {
                            "keys": [{"expression": {"kind": "call", "args": []}}]
                        },
                    }
                }
            ]
        },
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )

    assert report.supported is False
    assert any(
        finding.requirement == "sort:key_expression:call_callee"
        for finding in report.findings
    )


def test_local_analysis_rejects_sort_call_with_non_list_args() -> None:
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
                                        "callee": "dtcs:current_date",
                                        "args": None,
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
        finding.requirement == "sort:key_expression:call_args"
        for finding in report.findings
    )


@pytest.mark.parametrize(
    ("expression", "requirement"),
    [
        ({"kind": "literal"}, "sort:key_expression:literal_value"),
        (
            {"kind": "unary", "expr": {"kind": "fieldRef", "target": "x"}},
            "sort:key_expression:unary_operator",
        ),
        (
            {
                "kind": "binary",
                "left": {"kind": "fieldRef", "target": "x"},
                "right": {"kind": "literal", "value": 1},
            },
            "sort:key_expression:binary_operator",
        ),
    ],
)
def test_local_analysis_rejects_sort_expression_missing_required_fields(
    expression: dict[str, object], requirement: str
) -> None:
    report = LocalTransformCompiler().analyze(
        {
            "actions": [
                {
                    "kind": {
                        "action": "dtcs:sort",
                        "parameters": {"keys": [{"expression": expression}]},
                    }
                }
            ]
        },
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )

    assert report.supported is False
    assert any(finding.requirement == requirement for finding in report.findings)
