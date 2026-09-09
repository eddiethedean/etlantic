"""Executable verification for open FINAL-REL release blockers.

These tests intentionally fail until the corresponding production behavior is
fixed.  They exercise public compiler analysis/execution paths and encode only
the portable semantic invariant, not a preferred implementation strategy.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from etlantic.testing.portable_fixtures.corpus import FixtureCase
from etlantic.testing.portable_transform_conformance import (
    _run_case,
    default_frame_factory,
)
from etlantic.transform.capabilities import portable_shape_findings
from etlantic.transform.compiler import TransformPlanningContext


def _literal(type_: str, value: Any) -> dict[str, Any]:
    return {"kind": "literal", "value": {"type": type_, "value": value}}


def _field(name: str) -> dict[str, Any]:
    return {"kind": "fieldRef", "scope": "field", "target": name}


def _call(name: str, *args: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "call", "callee": name, "args": list(args)}


def _project_case(
    name: str,
    expressions: list[tuple[str, dict[str, Any]]],
    *,
    rows: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> FixtureCase:
    return FixtureCase(
        name=name,
        required_profiles=frozenset(),
        required_actions=frozenset(),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {}},
            "actions": [
                {
                    "id": "p",
                    "kind": {
                        "id": "p",
                        "action": "dtcs:project",
                        "target": "t",
                        "parameters": {
                            "fields": [
                                {"name": field_name, "expression": expression}
                                for field_name, expression in expressions
                            ]
                        },
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": rows},
        expected=expected,
    )


def _run(compiler: Any, case: FixtureCase) -> None:
    _run_case(
        compiler,
        case,
        planning=TransformPlanningContext(
            pipeline_id="review",
            step_name="step",
            profile_name="portable",
            engine=compiler.info.engine,
        ),
        to_frame=default_frame_factory(compiler.info.engine),
    )


def _require_postgresql() -> None:
    if not os.environ.get("ETLANTIC_SQL_URL", "").startswith("postgresql"):
        pytest.skip("FINAL-REL PostgreSQL verification requires ETLANTIC_SQL_URL")


@pytest.mark.polars
def test_final_rel_001_typed_null_not_propagates() -> None:
    """A typed null operand remains null under portable boolean NOT."""
    pytest.importorskip("polars")
    from etlantic_polars import create_transform_compiler

    case = _project_case(
        "final_rel_001_typed_null_not",
        [
            (
                "value",
                {"kind": "unary", "op": "not", "operand": _literal("null", None)},
            )
        ],
        rows=[{"seed": 1}],
        expected=[{"value": None}],
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_final_rel_001_postgresql_null_substring_bound_propagates() -> None:
    """A null substring bound must not become an ill-typed SQL expression."""
    _require_postgresql()
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    case = _project_case(
        "final_rel_001_postgresql_null_substring_bound",
        [
            (
                "value",
                _call(
                    "dtcs:substr",
                    _literal("string", "abc"),
                    _literal("null", None),
                ),
            )
        ],
        rows=[{"seed": 1}],
        expected=[{"value": None}],
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_final_rel_002_postgresql_rounds_float_column_half_even() -> None:
    """PostgreSQL executes half-even rounding for a floating input column."""
    _require_postgresql()
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    case = _project_case(
        "final_rel_002_postgresql_float_round",
        [
            (
                "value",
                _call(
                    "dtcs:round",
                    _field("number"),
                    _literal("integer", 1),
                ),
            )
        ],
        rows=[{"number": 2.25}],
        expected=[{"value": 2.2}],
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_final_rel_003_postgresql_uses_default_sigma_context() -> None:
    """PostgreSQL lower follows Unicode Default_Case_Conversion context."""
    _require_postgresql()
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    case = _project_case(
        "final_rel_003_postgresql_sigma_context",
        [("value", _call("dtcs:lower", _field("text")))],
        rows=[{"text": "A-\u03a3"}, {"text": "A\u03a3-B"}],
        expected=[{"value": "a-\u03c3"}, {"value": "a\u03c2-b"}],
    )
    _run(create_transform_compiler(), case)


def test_final_rel_004_unbounded_substring_offsets_fail_analysis() -> None:
    """A field-derived bound cannot establish the non-negative invariant."""
    plan = _project_case(
        "final_rel_004_dynamic_substring_bound",
        [("value", _call("dtcs:substr", _field("text"), _field("start")))],
        rows=[{"text": "abc", "start": -1}],
        expected=[],
    ).plan

    findings = portable_shape_findings(plan)
    assert any(
        finding.requirement == "function:dtcs:substr:argument:1" for finding in findings
    )


def test_final_rel_005_dynamic_replace_search_fails_analysis() -> None:
    """A field-derived search cannot prove the empty-search exclusion."""
    plan = _project_case(
        "final_rel_005_dynamic_replace_search",
        [
            (
                "value",
                _call(
                    "dtcs:replace",
                    _field("text"),
                    _field("search"),
                    _literal("string", "x"),
                ),
            )
        ],
        rows=[{"text": "abc", "search": ""}],
        expected=[],
    ).plan

    findings = portable_shape_findings(plan)
    assert any(
        finding.requirement == "function:dtcs:replace:empty_search"
        for finding in findings
    )
