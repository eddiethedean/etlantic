"""Regression coverage for the frozen portable Decimal contract."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from etlantic.testing.portable_fixtures.corpus import FixtureCase
from etlantic.testing.portable_transform_conformance import (
    _run_case,
    default_frame_factory,
)
from etlantic.transform import functions as F
from etlantic.transform.compiler import TransformPlanningContext


def _decimal_case(
    *,
    expression: dict[str, Any],
    rows: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> FixtureCase:
    return FixtureCase(
        name="decimal_contract",
        required_profiles=frozenset(),
        required_actions=frozenset(),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p",
                        "target": "t",
                        "parameters": {
                            "fields": [{"name": "value", "expression": expression}]
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


def _decimal_sum_case(rows: list[dict[str, Any]], expected: Decimal) -> FixtureCase:
    return _aggregate_case(
        callee="dtcs:sum",
        expression=F.col("amount").node,
        rows=rows,
        expected=expected,
    )


def _aggregate_case(
    *,
    callee: str,
    expression: dict[str, Any],
    rows: list[dict[str, Any]],
    expected: Any,
) -> FixtureCase:
    return FixtureCase(
        name="decimal_sum_contract",
        required_profiles=frozenset(),
        required_actions=frozenset(),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "a",
                    "kind": {
                        "action": "dtcs:aggregate",
                        "id": "a",
                        "target": "t",
                        "parameters": {
                            "groupBy": [],
                            "aggregates": [
                                {
                                    "name": "total",
                                    "expression": {
                                        "kind": "call",
                                        "callee": callee,
                                        "args": [expression],
                                    },
                                }
                            ],
                        },
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "a", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": rows},
        expected=[{"total": expected}],
    )


def _run(compiler: Any, case: FixtureCase) -> None:
    _run_case(
        compiler,
        case,
        planning=TransformPlanningContext(
            pipeline_id="decimal",
            step_name="step",
            profile_name="portable",
            engine=compiler.info.engine,
        ),
        to_frame=default_frame_factory(compiler.info.engine),
    )


def test_public_decimal_literal_is_json_safe_and_exact() -> None:
    literal = F.lit(Decimal("1234567890.123456789012345678")).node
    assert literal == {
        "kind": "literal",
        "value": {
            "type": "decimal",
            "value": "1234567890.123456789012345678",
        },
    }


def test_local_decimal_literal_preserves_coefficient_and_scale() -> None:
    from etlantic.transform.local_compiler import LocalTransformCompiler

    value = Decimal("1234567890.123456789012345678")
    case = _decimal_case(
        expression=F.lit(value).node,
        rows=[{"seed": 1}],
        expected=[{"value": value}],
    )
    _run(LocalTransformCompiler(), case)


@pytest.mark.sql
def test_sqlite_decimal_field_round_trip_preserves_precision() -> None:
    from etlantic_sql import create_transform_compiler

    value = Decimal("1234567890.123456789012345678")
    case = _decimal_case(
        expression=F.col("amount").node,
        rows=[{"amount": value}],
        expected=[{"value": value}],
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_postgresql_decimal_field_round_trip_preserves_precision() -> None:
    if (
        not __import__("os")
        .environ.get("ETLANTIC_SQL_URL", "")
        .startswith("postgresql")
    ):
        pytest.skip("PostgreSQL Decimal verification requires ETLANTIC_SQL_URL")
    from etlantic_sql import create_transform_compiler

    value = Decimal("1234567890.123456789012345678")
    case = _decimal_case(
        expression=F.col("amount").node,
        rows=[{"amount": value}],
        expected=[{"value": value}],
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_sqlite_decimal_sum_preserves_precision() -> None:
    from etlantic_sql import create_transform_compiler

    value = Decimal("1234567890.123456789012345678")
    case = _decimal_sum_case(
        rows=[{"amount": value}, {"amount": Decimal("0.000000000000000001")}],
        expected=Decimal("1234567890.123456789012345679"),
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_postgresql_decimal_sum_preserves_precision() -> None:
    if (
        not __import__("os")
        .environ.get("ETLANTIC_SQL_URL", "")
        .startswith("postgresql")
    ):
        pytest.skip("PostgreSQL Decimal verification requires ETLANTIC_SQL_URL")
    from etlantic_sql import create_transform_compiler

    value = Decimal("1234567890.123456789012345678")
    case = _decimal_sum_case(
        rows=[{"amount": value}, {"amount": Decimal("0.000000000000000001")}],
        expected=Decimal("1234567890.123456789012345679"),
    )
    _run(create_transform_compiler(), case)


@pytest.mark.duckdb
def test_duckdb_decimal_field_and_sum_preserve_precision() -> None:
    pytest.importorskip("duckdb")
    from etlantic_duckdb import create_transform_compiler

    value = Decimal("1234567890.123456789012345678")
    case = _decimal_sum_case(
        rows=[{"amount": value}, {"amount": Decimal("0.000000000000000001")}],
        expected=Decimal("1234567890.123456789012345679"),
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_sqlite_decimal_predicate_does_not_change_integer_aggregate_type() -> None:
    from etlantic_sql import create_transform_compiler

    predicate_value = F.when(
        F.col("amount") > F.lit(Decimal("0")),
        1,
    ).otherwise(0)
    case = _aggregate_case(
        callee="dtcs:sum",
        expression=predicate_value.node,
        rows=[{"amount": Decimal("1.5")}, {"amount": Decimal("-1.0")}],
        expected=1,
    )
    _run(create_transform_compiler(), case)


@pytest.mark.sql
def test_sqlite_decimal_predicate_does_not_break_string_min_aggregate() -> None:
    from etlantic_sql import create_transform_compiler

    value = F.when(
        F.col("amount") > F.lit(Decimal("0")),
        "yes",
    ).otherwise("no")
    case = _aggregate_case(
        callee="dtcs:min",
        expression=value.node,
        rows=[{"amount": Decimal("1.5")}, {"amount": Decimal("-1.0")}],
        expected="no",
    )
    _run(create_transform_compiler(), case)
