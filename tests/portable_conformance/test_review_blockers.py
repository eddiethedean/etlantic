"""Executable verification for open FINAL-REL release blockers.

These tests intentionally fail until the corresponding production behavior is
fixed.  They exercise public compiler analysis/execution paths and encode only
the portable semantic invariant, not a preferred implementation strategy.
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
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


@pytest.mark.sql
def test_final_rel_003_postgresql_uses_complete_case_ignorable_context() -> None:
    """Final-sigma context skips every required case-ignorable separator."""
    _require_postgresql()
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    case = _project_case(
        "final_rel_003_postgresql_complete_sigma_context",
        [("value", _call("dtcs:lower", _field("text")))],
        rows=[
            {"text": "A:\u03a3"},
            {"text": "A\u03a3:B"},
            {"text": "A'\u03a3"},
            {"text": "A\u03a3'B"},
        ],
        expected=[
            {"value": "a:\u03c2"},
            {"value": "a\u03c3:b"},
            {"value": "a'\u03c2"},
            {"value": "a\u03c3'b"},
        ],
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


def test_final_rel_004_composed_row_dependent_substring_offsets_fail_analysis() -> None:
    """Composing a field expression cannot bypass the static-bound requirement."""
    start = _call("dtcs:floor", _field("start"))
    plan = _project_case(
        "final_rel_004_composed_substring_bound",
        [("value", _call("dtcs:substr", _field("text"), start))],
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


def test_final_rel_005_composed_row_dependent_replace_search_fails_analysis() -> None:
    """Composing a field expression cannot bypass the non-empty-search proof."""
    plan = _project_case(
        "final_rel_005_composed_replace_search",
        [
            (
                "value",
                _call(
                    "dtcs:replace",
                    _field("text"),
                    _call("dtcs:lower", _field("search")),
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


def test_final_rel_008_findings_ledger_records_latest_review_round() -> None:
    """The immutable release ledger includes every stable release finding."""
    from scripts.check_portable_0_50 import validate_findings_ledger

    root = Path(__file__).resolve().parents[2]
    ledger = (
        root / "docs/11_DEVELOPMENT/evidence/portable_0_50/FINDINGS_0_50.md"
    ).read_text(encoding="utf-8")
    expected = {f"FINAL-REL-{index:03d}" for index in range(1, 9)} | {"SOL-REL-009"}
    missing = sorted(
        finding_id for finding_id in expected if f"| {finding_id} |" not in ledger
    )
    assert not missing, f"release findings ledger omits {missing!r}"
    for finding_id in sorted(expected):
        row = next(line for line in ledger.splitlines() if f"| {finding_id} |" in line)
        assert "resolved" in row.lower(), f"{finding_id} is not resolved in the ledger"
        with pytest.raises(SystemExit, match="ledger is incomplete"):
            validate_findings_ledger(ledger.replace(row, "", 1))


@pytest.mark.sql
def test_sol_rel_009_sqlite_preserves_boolean_type_through_union(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A boolean contributed by either union input remains a boolean."""
    monkeypatch.setenv("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    case = FixtureCase(
        name="sol_rel_009_sqlite_boolean_union",
        required_profiles=frozenset(),
        required_actions=frozenset(),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"left": {}, "right": {}},
            "actions": [
                {
                    "id": "u",
                    "kind": {
                        "id": "u",
                        "action": "dtcs:union",
                        "target": "left",
                        "parameters": {"other": "right", "mode": "byName"},
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "u", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"left": [{"flag": None}], "right": [{"flag": True}]},
        expected=[{"flag": None}, {"flag": True}],
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_sol_rel_009_sqlite_preserves_boolean_type_for_null_aware_expression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typed-null branches do not erase a scalar expression's boolean result type."""
    monkeypatch.setenv("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    case = _project_case(
        "sol_rel_009_sqlite_boolean_coalesce",
        [
            (
                "value",
                _call(
                    "dtcs:coalesce",
                    _literal("null", None),
                    _literal("boolean", True),
                ),
            )
        ],
        rows=[{"seed": 1}],
        expected=[{"value": True}],
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_sol_rel_009_sqlite_maps_union_boolean_types_by_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A by-position union maps right-side type metadata onto left-side names."""
    monkeypatch.setenv("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    case = FixtureCase(
        name="sol_rel_009_sqlite_boolean_union_by_position",
        required_profiles=frozenset(),
        required_actions=frozenset(),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"left": {}, "right": {}},
            "actions": [
                {
                    "id": "u",
                    "kind": {
                        "id": "u",
                        "action": "dtcs:union",
                        "target": "left",
                        "parameters": {"other": "right", "mode": "byPosition"},
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "u", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"left": [{"value": None}], "right": [{"flag": True}]},
        expected=[{"value": None}, {"value": True}],
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_sol_rel_009_sqlite_parameter_scope_does_not_inherit_field_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parameter sharing a field name retains its own runtime value type."""
    monkeypatch.setenv("ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:")
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    case = _project_case(
        "sol_rel_009_sqlite_parameter_field_name_collision",
        [
            (
                "value",
                {"kind": "fieldRef", "scope": "parameter", "target": "flag"},
            )
        ],
        rows=[{"flag": True}],
        expected=[{"value": 2}],
    )
    case = replace(case, parameters={"flag": 2})
    _run(create_transform_compiler(), case)
