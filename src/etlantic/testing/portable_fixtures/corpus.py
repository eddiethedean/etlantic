"""Mandatory portable transform fixtures keyed by capability claims."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from etlantic.transform.protocol import KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1


@dataclass(frozen=True)
class FixtureCase:
    """One executable conformance case for claimed capabilities."""

    name: str
    required_profiles: frozenset[str]
    required_actions: frozenset[str]
    required_functions: frozenset[str]
    plan: dict[str, Any]
    inputs: dict[str, list[dict[str, Any]]]
    expected: list[dict[str, Any]] | None = None
    expect_unsupported: bool = False
    unsupported_requirement_substr: str | None = None
    parameters: dict[str, Any] | None = None
    required_operators: frozenset[str] = frozenset()
    required_types: frozenset[str] = frozenset()
    required_semantic_modes: frozenset[str] = frozenset()
    required_join_modes: frozenset[str] = frozenset()
    required_union_modes: frozenset[str] = frozenset()
    required_collision_policies: frozenset[str] = frozenset()


def _kernel_filter_project() -> FixtureCase:
    return FixtureCase(
        name="kernel_filter_project_lower",
        required_profiles=frozenset({KERNEL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:filter", "dtcs:project", "dtcs:with_fields"}),
        required_functions=frozenset({"dtcs:lower"}),
        required_operators=frozenset({"gte"}),
        required_types=frozenset({"integer", "string"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"customers": {"id": "customers"}},
            "actions": [
                {
                    "id": "f1",
                    "kind": {
                        "action": "dtcs:filter",
                        "id": "f1",
                        "parameters": {
                            "predicate": {
                                "kind": "binary",
                                "op": "gte",
                                "left": {
                                    "kind": "fieldRef",
                                    "scope": "field",
                                    "target": "age",
                                },
                                "right": {
                                    "kind": "literal",
                                    "value": {"type": "integer", "value": 18},
                                },
                            }
                        },
                        "target": "customers",
                    },
                },
                {
                    "id": "w1",
                    "kind": {
                        "action": "dtcs:with_fields",
                        "id": "w1",
                        "parameters": {
                            "assignments": [
                                {
                                    "name": "email",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:lower",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "email",
                                            }
                                        ],
                                    },
                                }
                            ]
                        },
                        "target": "f1",
                    },
                },
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": ["customer_id", "email", "age"],
                        },
                        "target": "w1",
                    },
                },
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={
            "customers": [
                {"customer_id": 1, "email": "A@X.COM", "age": 30},
                {"customer_id": 2, "email": "b@y.com", "age": 10},
            ]
        },
        expected=[{"customer_id": 1, "email": "a@x.com", "age": 30}],
    )


def _kernel_project_identity() -> FixtureCase:
    return FixtureCase(
        name="kernel_project_identity",
        required_profiles=frozenset({KERNEL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {"fields": ["id"]},
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
        },
        inputs={"t": [{"id": 1}]},
        expected=[{"id": 1}],
    )


def _substr_literal_replace() -> FixtureCase:
    return FixtureCase(
        name="kernel_substr_replace_unicode",
        required_profiles=frozenset({KERNEL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset({"dtcs:substr", "dtcs:replace"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {
                                    "name": "sub",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:substr",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "s",
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "integer",
                                                    "value": 0,
                                                },
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "integer",
                                                    "value": 3,
                                                },
                                            },
                                        ],
                                    },
                                },
                                {
                                    "name": "rep",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:replace",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "s",
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "string",
                                                    "value": "a.b",
                                                },
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "string",
                                                    "value": "X",
                                                },
                                            },
                                        ],
                                    },
                                },
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"s": "abcdef"}, {"s": "a.b"}]},
        expected=[{"rep": "abcdef", "sub": "abc"}, {"rep": "X", "sub": "a.b"}],
    )


def _relational_aggregate() -> FixtureCase:
    return FixtureCase(
        name="relational_join_aggregate",
        required_profiles=frozenset({RELATIONAL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:join", "dtcs:aggregate"}),
        required_functions=frozenset({"dtcs:sum"}),
        required_collision_policies=frozenset({"fail"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {
                "orders": {"id": "orders"},
                "customers": {"id": "customers"},
            },
            "actions": [
                {
                    "id": "j1",
                    "kind": {
                        "action": "dtcs:join",
                        "id": "j1",
                        "parameters": {
                            "type": "left",
                            "right": "customers",
                            "leftKey": "customer_id",
                            "rightKey": "customer_id",
                            "collisionPolicy": "fail",
                        },
                        "target": "orders",
                    },
                },
                {
                    "id": "a1",
                    "kind": {
                        "action": "dtcs:aggregate",
                        "id": "a1",
                        "parameters": {
                            "groupBy": ["region"],
                            "aggregates": [
                                {
                                    "name": "total",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:sum",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "amount",
                                            }
                                        ],
                                    },
                                }
                            ],
                        },
                        "target": "j1",
                    },
                },
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "a1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={
            "orders": [
                {"order_id": 1, "customer_id": 1, "amount": 10.0},
                {"order_id": 2, "customer_id": 1, "amount": 5.0},
                {"order_id": 3, "customer_id": 2, "amount": 7.0},
            ],
            "customers": [
                {"customer_id": 1, "region": "east"},
                {"customer_id": 2, "region": "west"},
            ],
        },
        expected=[
            {"region": "east", "total": 15.0},
            {"region": "west", "total": 7.0},
        ],
    )


def _sort_nulls_limit() -> FixtureCase:
    return FixtureCase(
        name="relational_sort_nulls_limit",
        required_profiles=frozenset({RELATIONAL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:sort", "dtcs:limit"}),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "s1",
                    "kind": {
                        "action": "dtcs:sort",
                        "id": "s1",
                        "parameters": {
                            "keys": [
                                {
                                    "column": "k",
                                    "direction": "asc",
                                    "nulls": "last",
                                }
                            ]
                        },
                        "target": "t",
                    },
                },
                {
                    "id": "l1",
                    "kind": {
                        "action": "dtcs:limit",
                        "id": "l1",
                        "parameters": {"n": 2},
                        "target": "s1",
                    },
                },
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "l1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"k": "b", "v": 2}, {"k": None, "v": 1}, {"k": "a", "v": 3}]},
        expected=[{"k": "a", "v": 3}, {"k": "b", "v": 2}],
    )


def _empty_ungrouped_count() -> FixtureCase:
    # Filter-all then count_all so engines receive a typed non-empty schema first.
    return FixtureCase(
        name="relational_empty_count_all",
        required_profiles=frozenset({RELATIONAL_PROFILE_V1, KERNEL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:filter", "dtcs:aggregate"}),
        required_functions=frozenset({"dtcs:count_all"}),
        required_operators=frozenset({"eq"}),
        required_types=frozenset({"integer"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "f1",
                    "kind": {
                        "action": "dtcs:filter",
                        "id": "f1",
                        "parameters": {
                            "predicate": {
                                "kind": "binary",
                                "op": "eq",
                                "left": {
                                    "kind": "fieldRef",
                                    "scope": "field",
                                    "target": "x",
                                },
                                "right": {
                                    "kind": "literal",
                                    "value": {"type": "integer", "value": -1},
                                },
                            }
                        },
                        "target": "t",
                    },
                },
                {
                    "id": "a1",
                    "kind": {
                        "action": "dtcs:aggregate",
                        "id": "a1",
                        "parameters": {
                            "groupBy": [],
                            "aggregates": [
                                {
                                    "name": "n",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:count_all",
                                        "args": [],
                                    },
                                }
                            ],
                        },
                        "target": "f1",
                    },
                },
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "a1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"x": 1}]},
        expected=[{"n": 0}],
    )


def _decimal_extremes() -> FixtureCase:
    return FixtureCase(
        name="kernel_decimal_coalesce",
        required_profiles=frozenset({KERNEL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset({"dtcs:coalesce"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {
                                    "name": "v",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:coalesce",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "a",
                                            },
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "b",
                                            },
                                        ],
                                    },
                                }
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"a": None, "b": 1.5}, {"a": -1e9, "b": 2.0}]},
        expected=[{"v": 1.5}, {"v": -1000000000.0}],
    )


def _reject_suffix_collision() -> FixtureCase:
    return FixtureCase(
        name="reject_join_collision_suffix",
        required_profiles=frozenset({RELATIONAL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:join"}),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "actions": [
                {
                    "id": "j1",
                    "kind": {
                        "action": "dtcs:join",
                        "id": "j1",
                        "parameters": {
                            "type": "inner",
                            "right": "r",
                            "leftKey": "id",
                            "rightKey": "id",
                            "collisionPolicy": "suffix",
                        },
                        "target": "l",
                    },
                }
            ],
        },
        inputs={},
        expected=None,
        expect_unsupported=True,
        unsupported_requirement_substr="collisionPolicy",
    )


def _string_advanced_trim_regex() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_STRING_ADVANCED

    return FixtureCase(
        name="string_advanced_trim_regex_replace",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_STRING_ADVANCED}),
        required_actions=frozenset({"dtcs:with_fields", "dtcs:project"}),
        required_functions=frozenset({"dtcs:trim", "dtcs:regex_replace"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "w1",
                    "kind": {
                        "action": "dtcs:with_fields",
                        "id": "w1",
                        "parameters": {
                            "assignments": [
                                {
                                    "name": "name",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:trim",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "name",
                                            }
                                        ],
                                    },
                                },
                                {
                                    "name": "code",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:regex_replace",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "code",
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "string",
                                                    "value": r"\d+",
                                                },
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "string",
                                                    "value": "N",
                                                },
                                            },
                                        ],
                                    },
                                },
                            ]
                        },
                        "target": "t",
                    },
                },
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {"fields": ["name", "code"]},
                        "target": "w1",
                    },
                },
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"name": "  Alice  ", "code": "A12B"}]},
        expected=[{"name": "Alice", "code": "ANB"}],
    )


def _conversion_to_string() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_CONVERSION

    return FixtureCase(
        name="conversion_to_string",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_CONVERSION}),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset({"dtcs:to_string"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {
                                    "name": "label",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:to_string",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "n",
                                            }
                                        ],
                                    },
                                }
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"n": 42}]},
        expected=[{"label": "42"}],
    )


def _statistics_variance() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_STATISTICS

    return FixtureCase(
        name="statistics_variance",
        required_profiles=frozenset(
            {KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1, PROFILE_STATISTICS}
        ),
        required_actions=frozenset({"dtcs:aggregate"}),
        required_functions=frozenset({"dtcs:variance"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "a1",
                    "kind": {
                        "action": "dtcs:aggregate",
                        "id": "a1",
                        "parameters": {
                            "groupBy": [],
                            "aggregations": [
                                {
                                    "name": "v",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:variance",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "x",
                                            }
                                        ],
                                    },
                                }
                            ],
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "a1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"x": 1.0}, {"x": 3.0}]},
        expected=[{"v": 2.0}],
    )


def _window_v1_row_number() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_WINDOW_V1

    return FixtureCase(
        name="window_v1_row_number",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_WINDOW_V1}),
        required_actions=frozenset({"dtcs:with_fields", "dtcs:project"}),
        required_functions=frozenset({"dtcs:row_number"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "w1",
                    "kind": {
                        "action": "dtcs:with_fields",
                        "id": "w1",
                        "parameters": {
                            "assignments": [
                                {
                                    "name": "rn",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:row_number",
                                        "args": [],
                                    },
                                    "window": {
                                        "partitionBy": ["g"],
                                        "orderBy": [
                                            {
                                                "expression": {
                                                    "kind": "fieldRef",
                                                    "scope": "field",
                                                    "target": "x",
                                                },
                                                "direction": "asc",
                                            }
                                        ],
                                    },
                                }
                            ]
                        },
                        "target": "t",
                    },
                },
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {"fields": ["g", "x", "rn"]},
                        "target": "w1",
                    },
                },
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"g": "a", "x": 2}, {"g": "a", "x": 1}, {"g": "b", "x": 9}]},
        expected=[
            {"g": "a", "x": 1, "rn": 1},
            {"g": "a", "x": 2, "rn": 2},
            {"g": "b", "x": 9, "rn": 1},
        ],
    )


def _complex_values_array_size() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_COMPLEX_VALUES

    return FixtureCase(
        name="complex_values_array_size",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_COMPLEX_VALUES}),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset({"dtcs:array", "dtcs:size"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {
                                    "name": "n",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:size",
                                        "args": [
                                            {
                                                "kind": "call",
                                                "callee": "dtcs:array",
                                                "args": [
                                                    {
                                                        "kind": "fieldRef",
                                                        "scope": "field",
                                                        "target": "a",
                                                    },
                                                    {
                                                        "kind": "fieldRef",
                                                        "scope": "field",
                                                        "target": "b",
                                                    },
                                                ],
                                            }
                                        ],
                                    },
                                }
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"a": 1, "b": 2}]},
        expected=[{"n": 2}],
    )


def _complex_types_field_access() -> FixtureCase:
    from etlantic.transform.protocol import (
        PROFILE_COMPLEX_TYPES,
        PROFILE_COMPLEX_VALUES,
    )

    return FixtureCase(
        name="complex_types_field_access",
        required_profiles=frozenset(
            {KERNEL_PROFILE_V1, PROFILE_COMPLEX_TYPES, PROFILE_COMPLEX_VALUES}
        ),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset({"dtcs:object", "dtcs:field"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {
                                    "name": "city",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:field",
                                        "args": [
                                            {
                                                "kind": "call",
                                                "callee": "dtcs:object",
                                                "args": [
                                                    {
                                                        "kind": "literal",
                                                        "value": {
                                                            "type": "string",
                                                            "value": "city",
                                                        },
                                                    },
                                                    {
                                                        "kind": "fieldRef",
                                                        "scope": "field",
                                                        "target": "city",
                                                    },
                                                ],
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "string",
                                                    "value": "city",
                                                },
                                            },
                                        ],
                                    },
                                }
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"city": "NYC"}]},
        expected=[{"city": "NYC"}],
    )


def _reshape_explode() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_RESHAPE

    return FixtureCase(
        name="reshape_explode",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_RESHAPE}),
        required_actions=frozenset({"dtcs:explode", "dtcs:project"}),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "e1",
                    "kind": {
                        "action": "dtcs:explode",
                        "id": "e1",
                        "parameters": {"field": "tags"},
                        "target": "t",
                    },
                },
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {"fields": ["id", "tags"]},
                        "target": "e1",
                    },
                },
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"id": 1, "tags": ["a", "b"]}]},
        expected=[{"id": 1, "tags": "a"}, {"id": 1, "tags": "b"}],
    )


def _reshape_explode_empty() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_RESHAPE

    return FixtureCase(
        name="reshape_explode_empty",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_RESHAPE}),
        required_actions=frozenset({"dtcs:explode", "dtcs:project"}),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "e1",
                    "kind": {
                        "action": "dtcs:explode",
                        "id": "e1",
                        "parameters": {"field": "tags"},
                        "target": "t",
                    },
                },
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {"fields": ["id", "tags"]},
                        "target": "e1",
                    },
                },
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"id": 1, "tags": ["a"]}, {"id": 2, "tags": []}]},
        expected=[{"id": 1, "tags": "a"}, {"id": 2, "tags": None}],
    )


def _conversion_cast_integer() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_CONVERSION

    return FixtureCase(
        name="conversion_cast_integer",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_CONVERSION}),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset({"dtcs:to_integer"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {
                                    "name": "n",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:to_integer",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "s",
                                            }
                                        ],
                                    },
                                }
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"s": "7"}]},
        expected=[{"n": 7}],
    )


def _conversion_try_cast() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_CONVERSION

    return FixtureCase(
        name="conversion_try_cast",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_CONVERSION}),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset({"dtcs:try_cast", "dtcs:cast"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {
                                    "name": "ok",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:cast",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "s",
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "string",
                                                    "value": "integer",
                                                },
                                            },
                                        ],
                                    },
                                },
                                {
                                    "name": "soft",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:try_cast",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "bad",
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "string",
                                                    "value": "integer",
                                                },
                                            },
                                        ],
                                    },
                                },
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"s": "7", "bad": "nope"}]},
        expected=[{"ok": 7, "soft": None}],
    )


def _string_advanced_ltrim_split() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_STRING_ADVANCED

    return FixtureCase(
        name="string_advanced_ltrim_split",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_STRING_ADVANCED}),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset(
            {"dtcs:ltrim", "dtcs:rtrim", "dtcs:split", "dtcs:regex_extract"}
        ),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {
                                    "name": "trimmed",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:ltrim",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "s",
                                            }
                                        ],
                                    },
                                },
                                {
                                    "name": "right",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:rtrim",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "t",
                                            }
                                        ],
                                    },
                                },
                                {
                                    "name": "parts",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:split",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "csv",
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "string",
                                                    "value": ",",
                                                },
                                            },
                                        ],
                                    },
                                },
                                {
                                    "name": "digit",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:regex_extract",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "code",
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "string",
                                                    "value": r"(\d+)",
                                                },
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "integer",
                                                    "value": 1,
                                                },
                                            },
                                        ],
                                    },
                                },
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"s": "  hi", "t": "hi  ", "csv": "a,b", "code": "x12y"}]},
        expected=[{"trimmed": "hi", "right": "hi", "parts": ["a", "b"], "digit": "12"}],
    )


def _statistics_stddev() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_STATISTICS

    return FixtureCase(
        name="statistics_stddev",
        required_profiles=frozenset(
            {KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1, PROFILE_STATISTICS}
        ),
        required_actions=frozenset({"dtcs:aggregate"}),
        required_functions=frozenset({"dtcs:stddev"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "a1",
                    "kind": {
                        "action": "dtcs:aggregate",
                        "id": "a1",
                        "parameters": {
                            "groupBy": [],
                            "aggregations": [
                                {
                                    "name": "s",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:stddev",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "x",
                                            }
                                        ],
                                    },
                                }
                            ],
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "a1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"x": 1.0}, {"x": 3.0}]},
        expected=[{"s": 1.4142135623730951}],
    )


def _window_v1_lag() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_WINDOW_V1

    return FixtureCase(
        name="window_v1_lag",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_WINDOW_V1}),
        required_actions=frozenset({"dtcs:with_fields", "dtcs:project"}),
        required_functions=frozenset({"dtcs:lag"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "w1",
                    "kind": {
                        "action": "dtcs:with_fields",
                        "id": "w1",
                        "parameters": {
                            "assignments": [
                                {
                                    "name": "prev",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:lag",
                                        "args": [
                                            {
                                                "kind": "fieldRef",
                                                "scope": "field",
                                                "target": "v",
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "integer",
                                                    "value": 1,
                                                },
                                            },
                                        ],
                                    },
                                    "window": {
                                        "partitionBy": ["g"],
                                        "orderBy": [
                                            {
                                                "expression": {
                                                    "kind": "fieldRef",
                                                    "scope": "field",
                                                    "target": "v",
                                                },
                                                "direction": "asc",
                                            }
                                        ],
                                    },
                                }
                            ]
                        },
                        "target": "t",
                    },
                },
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {"fields": ["g", "v", "prev"]},
                        "target": "w1",
                    },
                },
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"g": "a", "v": 1}, {"g": "a", "v": 2}]},
        expected=[{"g": "a", "v": 1, "prev": None}, {"g": "a", "v": 2, "prev": 1}],
    )


def _reject_window_frame() -> FixtureCase:
    from etlantic.transform.protocol import PROFILE_WINDOW_V1

    return FixtureCase(
        name="reject_window_frame",
        required_profiles=frozenset({KERNEL_PROFILE_V1, PROFILE_WINDOW_V1}),
        required_actions=frozenset({"dtcs:with_fields"}),
        required_functions=frozenset({"dtcs:row_number"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "w1",
                    "kind": {
                        "action": "dtcs:with_fields",
                        "id": "w1",
                        "parameters": {
                            "assignments": [
                                {
                                    "name": "rn",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:row_number",
                                        "args": [],
                                    },
                                    "window": {
                                        "partitionBy": ["g"],
                                        "orderBy": [
                                            {
                                                "expression": {
                                                    "kind": "fieldRef",
                                                    "scope": "field",
                                                    "target": "v",
                                                },
                                                "direction": "asc",
                                            }
                                        ],
                                        "frame": {
                                            "type": "rows",
                                            "start": "unboundedPreceding",
                                            "end": "currentRow",
                                        },
                                    },
                                }
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
        },
        inputs={"t": [{"g": "a", "v": 1}]},
        expected=None,
        expect_unsupported=True,
        unsupported_requirement_substr="window_frame",
    )


def _complex_types_index() -> FixtureCase:
    from etlantic.transform.protocol import (
        PROFILE_COMPLEX_TYPES,
        PROFILE_COMPLEX_VALUES,
    )

    return FixtureCase(
        name="complex_types_index",
        required_profiles=frozenset(
            {KERNEL_PROFILE_V1, PROFILE_COMPLEX_VALUES, PROFILE_COMPLEX_TYPES}
        ),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset({"dtcs:array", "dtcs:index", "dtcs:element_at"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {
                                    "name": "first",
                                    "expression": {
                                        "kind": "call",
                                        "callee": "dtcs:index",
                                        "args": [
                                            {
                                                "kind": "call",
                                                "callee": "dtcs:array",
                                                "args": [
                                                    {
                                                        "kind": "literal",
                                                        "value": {
                                                            "type": "string",
                                                            "value": "x",
                                                        },
                                                    },
                                                    {
                                                        "kind": "literal",
                                                        "value": {
                                                            "type": "string",
                                                            "value": "y",
                                                        },
                                                    },
                                                ],
                                            },
                                            {
                                                "kind": "literal",
                                                "value": {
                                                    "type": "integer",
                                                    "value": 0,
                                                },
                                            },
                                        ],
                                    },
                                }
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"id": 1}]},
        expected=[{"first": "x"}],
    )


def _reject_missing_literal_without_three_state() -> FixtureCase:
    return FixtureCase(
        name="reject_missing_literal_without_three_state",
        required_profiles=frozenset({KERNEL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset(),
        required_types=frozenset({"missing", "invalid"}),
        required_semantic_modes=frozenset({"three_state_distinct"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {
                                    "name": "x",
                                    "expression": {
                                        "kind": "literal",
                                        "value": {"type": "missing", "value": None},
                                    },
                                }
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
        },
        inputs={"t": [{"id": 1}]},
        expected=None,
        expect_unsupported=True,
        unsupported_requirement_substr="three_state_distinct",
    )


def _baseline_scalar_functions() -> FixtureCase:
    """Exercise every scalar function in the portable 0.50 baseline."""

    def lit(type_: str, value: Any) -> dict[str, Any]:
        return {"kind": "literal", "value": {"type": type_, "value": value}}

    def field(name: str) -> dict[str, Any]:
        return {"kind": "fieldRef", "scope": "field", "target": name}

    def call(name: str, *args: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "call", "callee": name, "args": list(args)}

    def binary(op: str, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "binary", "op": op, "left": left, "right": right}

    def unary(op: str, operand: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "unary", "op": op, "operand": operand}

    neg = {"kind": "unary", "op": "negate", "operand": lit("integer", 4)}
    predicate = {
        "kind": "binary",
        "op": "eq",
        "left": field("n"),
        "right": lit("integer", 4),
    }
    fields = [
        ("lower", call("dtcs:lower", field("s"))),
        ("upper", call("dtcs:upper", field("s"))),
        ("concat", call("dtcs:concat", field("s"), lit("string", "!"))),
        (
            "concat_ws",
            call("dtcs:concat_ws", lit("string", "-"), field("s"), lit("string", "x")),
        ),
        (
            "substr",
            call("dtcs:substr", field("s"), lit("integer", 0), lit("integer", 2)),
        ),
        (
            "replace",
            call("dtcs:replace", field("s"), lit("string", "b"), lit("string", "B")),
        ),
        ("length", call("dtcs:length", field("s"))),
        ("contains", call("dtcs:contains", field("s"), lit("string", "A"))),
        ("starts_with", call("dtcs:starts_with", field("s"), lit("string", "A"))),
        ("ends_with", call("dtcs:ends_with", field("s"), lit("string", "C"))),
        (
            "case_when",
            call(
                "dtcs:case_when", predicate, lit("string", "yes"), lit("string", "no")
            ),
        ),
        ("coalesce", call("dtcs:coalesce", lit("null", None), field("s"))),
        ("if_null", call("dtcs:if_null", lit("null", None), field("s"))),
        ("null_if", call("dtcs:null_if", field("s"), field("s"))),
        ("is_null", call("dtcs:is_null", lit("null", None))),
        ("abs", call("dtcs:abs", neg)),
        ("round", call("dtcs:round", lit("decimal", 3.6), lit("integer", 0))),
        ("round_default", call("dtcs:round", lit("decimal", 3.6))),
        ("floor", call("dtcs:floor", lit("decimal", 3.6))),
        ("ceil", call("dtcs:ceil", lit("decimal", 3.2))),
        ("power", call("dtcs:power", lit("integer", 2), lit("integer", 3))),
        ("sqrt", call("dtcs:sqrt", lit("decimal", 9.0))),
        ("least", call("dtcs:least", field("n"), lit("integer", 2))),
        ("greatest", call("dtcs:greatest", field("n"), lit("integer", 2))),
        ("op_eq", binary("eq", field("n"), lit("integer", 4))),
        ("op_not_eq", binary("not_eq", field("n"), lit("integer", 3))),
        ("op_lt", binary("lt", field("n"), lit("integer", 5))),
        ("op_lte", binary("lte", field("n"), lit("integer", 4))),
        ("op_gt", binary("gt", field("n"), lit("integer", 3))),
        ("op_gte", binary("gte", field("n"), lit("integer", 4))),
        ("op_null_safe_eq", binary("null_safe_eq", field("n"), lit("integer", 4))),
        ("op_and", binary("and", lit("boolean", True), lit("boolean", True))),
        ("op_or", binary("or", lit("boolean", False), lit("boolean", True))),
        ("op_not", unary("not", lit("boolean", False))),
        ("op_add", binary("add", lit("integer", 4), lit("integer", 2))),
        ("op_subtract", binary("subtract", lit("integer", 4), lit("integer", 2))),
        ("op_multiply", binary("multiply", lit("integer", 4), lit("integer", 2))),
        ("op_divide", binary("divide", field("n"), lit("integer", 2))),
        ("op_modulo", binary("modulo", field("n"), lit("integer", 3))),
        ("op_negate", unary("negate", lit("integer", 4))),
        (
            "op_in",
            call("dtcs:in", field("n"), lit("integer", 3), lit("integer", 4)),
        ),
        ("boolean_literal", lit("boolean", True)),
    ]
    return FixtureCase(
        name="baseline_scalar_functions",
        required_profiles=frozenset({KERNEL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:project"}),
        required_functions=frozenset(
            {
                f"dtcs:{name}"
                for name, _ in fields
                if not name.startswith("op_")
                and name not in {"boolean_literal", "round_default"}
            }
        ),
        required_operators=frozenset(
            {
                "eq",
                "not_eq",
                "lt",
                "lte",
                "gt",
                "gte",
                "null_safe_eq",
                "and",
                "or",
                "not",
                "add",
                "subtract",
                "multiply",
                "divide",
                "modulo",
                "negate",
                "in",
            }
        ),
        required_types=frozenset({"null", "boolean", "integer", "decimal", "string"}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "p1",
                    "kind": {
                        "action": "dtcs:project",
                        "id": "p1",
                        "parameters": {
                            "fields": [
                                {"name": name, "expression": expr}
                                for name, expr in fields
                            ]
                        },
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "p1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"s": "AbC", "n": 4}]},
        expected=[
            {
                "lower": "abc",
                "upper": "ABC",
                "concat": "AbC!",
                "concat_ws": "AbC-x",
                "substr": "Ab",
                "replace": "ABC",
                "length": 3,
                "contains": True,
                "starts_with": True,
                "ends_with": True,
                "case_when": "yes",
                "coalesce": "AbC",
                "if_null": "AbC",
                "null_if": None,
                "is_null": True,
                "abs": 4,
                "round": 4.0,
                "round_default": 4.0,
                "floor": 3.0,
                "ceil": 4.0,
                "power": 8.0,
                "sqrt": 3.0,
                "least": 2,
                "greatest": 4,
                "op_eq": True,
                "op_not_eq": True,
                "op_lt": True,
                "op_lte": True,
                "op_gt": True,
                "op_gte": True,
                "op_null_safe_eq": True,
                "op_and": True,
                "op_or": True,
                "op_not": True,
                "op_add": 6,
                "op_subtract": 2,
                "op_multiply": 8,
                "op_divide": 2.0,
                "op_modulo": 1,
                "op_negate": -4,
                "op_in": True,
                "boolean_literal": True,
            }
        ],
    )


def _baseline_aggregate_functions() -> FixtureCase:
    """Exercise every aggregate function in the portable 0.50 baseline."""
    names = ("sum", "average", "min", "max", "count", "count_all", "count_distinct")
    aggregates = [
        {
            "name": name,
            "expression": {
                "kind": "call",
                "callee": f"dtcs:{name}",
                "args": []
                if name == "count_all"
                else [{"kind": "fieldRef", "scope": "field", "target": "v"}],
            },
        }
        for name in names
    ]
    return FixtureCase(
        name="baseline_aggregate_functions",
        required_profiles=frozenset({RELATIONAL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:aggregate"}),
        required_functions=frozenset({f"dtcs:{name}" for name in names}),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "a1",
                    "kind": {
                        "action": "dtcs:aggregate",
                        "id": "a1",
                        "parameters": {"aggregates": aggregates},
                        "target": "t",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "a1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"v": 1}, {"v": 1}, {"v": 2}]},
        expected=[
            {
                "sum": 4,
                "average": 4 / 3,
                "min": 1,
                "max": 2,
                "count": 3,
                "count_all": 3,
                "count_distinct": 2,
            }
        ],
    )


def _qualified_action_smokes() -> tuple[FixtureCase, ...]:
    """Small action-only fixtures keep qualified subsets honest."""
    base = {
        "planIdentity": "dtcs.transform-plan/2",
        "inputs": {"t": {"id": "t"}},
        "outputs": {"result": {"id": "result"}},
    }
    filter_plan = {
        **base,
        "actions": [
            {
                "id": "f1",
                "kind": {
                    "action": "dtcs:filter",
                    "id": "f1",
                    "parameters": {
                        "predicate": {
                            "kind": "literal",
                            "value": {"type": "boolean", "value": True},
                        }
                    },
                    "target": "t",
                },
            }
        ],
    }
    with_fields_plan = {
        **base,
        "actions": [
            {
                "id": "w1",
                "kind": {
                    "action": "dtcs:with_fields",
                    "id": "w1",
                    "parameters": {
                        "assignments": [
                            {
                                "name": "value",
                                "expression": {
                                    "kind": "literal",
                                    "value": {"type": "integer", "value": 1},
                                },
                            },
                            {
                                "name": "eq",
                                "expression": {
                                    "kind": "binary",
                                    "op": "eq",
                                    "left": {"kind": "fieldRef", "target": "id"},
                                    "right": {
                                        "kind": "literal",
                                        "value": {"type": "integer", "value": 1},
                                    },
                                },
                            },
                            {
                                "name": "lt",
                                "expression": {
                                    "kind": "binary",
                                    "op": "lt",
                                    "left": {"kind": "fieldRef", "target": "id"},
                                    "right": {
                                        "kind": "literal",
                                        "value": {"type": "integer", "value": 2},
                                    },
                                },
                            },
                            {
                                "name": "gt",
                                "expression": {
                                    "kind": "binary",
                                    "op": "gt",
                                    "left": {"kind": "fieldRef", "target": "id"},
                                    "right": {
                                        "kind": "literal",
                                        "value": {"type": "integer", "value": 0},
                                    },
                                },
                            },
                        ]
                    },
                    "target": "t",
                },
            }
        ],
    }
    aggregate_plan = {
        **base,
        "actions": [
            {
                "id": "a1",
                "kind": {
                    "action": "dtcs:aggregate",
                    "id": "a1",
                    "parameters": {
                        "aggregates": [
                            {
                                "name": "count",
                                "expression": {
                                    "kind": "call",
                                    "callee": "dtcs:count_all",
                                    "args": [],
                                },
                            }
                        ]
                    },
                    "target": "t",
                },
            }
        ],
    }
    return (
        FixtureCase(
            name="qualified_filter_action",
            required_profiles=frozenset({KERNEL_PROFILE_V1}),
            required_actions=frozenset({"dtcs:filter"}),
            required_functions=frozenset(),
            required_types=frozenset({"boolean"}),
            plan=filter_plan,
            inputs={"t": [{"id": 1}]},
            expected=[{"id": 1}],
        ),
        FixtureCase(
            name="qualified_with_fields_action",
            required_profiles=frozenset({KERNEL_PROFILE_V1}),
            required_actions=frozenset({"dtcs:with_fields"}),
            required_functions=frozenset(),
            required_types=frozenset({"integer"}),
            required_operators=frozenset({"eq", "lt", "gt"}),
            plan=with_fields_plan,
            inputs={"t": [{"id": 1}]},
            expected=[{"eq": True, "gt": True, "id": 1, "lt": True, "value": 1}],
        ),
        FixtureCase(
            name="qualified_count_all_aggregate",
            required_profiles=frozenset({RELATIONAL_PROFILE_V1}),
            required_actions=frozenset({"dtcs:aggregate"}),
            required_functions=frozenset({"dtcs:count_all"}),
            plan=aggregate_plan,
            inputs={"t": [{"id": 1}, {"id": 2}]},
            expected=[{"count": 2}],
        ),
    )


def _qualified_function_smokes() -> tuple[FixtureCase, ...]:
    def literal(type_: str, value: Any) -> dict[str, Any]:
        return {"kind": "literal", "value": {"type": type_, "value": value}}

    field = {"kind": "fieldRef", "scope": "field", "target": "s"}
    return (
        FixtureCase(
            name="qualified_string_functions",
            required_profiles=frozenset({KERNEL_PROFILE_V1}),
            required_actions=frozenset({"dtcs:project"}),
            required_functions=frozenset({"dtcs:lower", "dtcs:coalesce"}),
            required_types=frozenset({"null", "string"}),
            plan={
                "planIdentity": "dtcs.transform-plan/2",
                "inputs": {"t": {"id": "t"}},
                "actions": [
                    {
                        "id": "p1",
                        "kind": {
                            "action": "dtcs:project",
                            "id": "p1",
                            "parameters": {
                                "fields": [
                                    {
                                        "name": "lower",
                                        "expression": {
                                            "kind": "call",
                                            "callee": "dtcs:lower",
                                            "args": [field],
                                        },
                                    },
                                    {
                                        "name": "coalesced",
                                        "expression": {
                                            "kind": "call",
                                            "callee": "dtcs:coalesce",
                                            "args": [literal("null", None), field],
                                        },
                                    },
                                ]
                            },
                            "target": "t",
                        },
                    }
                ],
                "outputs": {"result": {"id": "result"}},
            },
            inputs={"t": [{"s": "AbC"}]},
            expected=[{"coalesced": "AbC", "lower": "abc"}],
        ),
        FixtureCase(
            name="qualified_aggregate_functions",
            required_profiles=frozenset({RELATIONAL_PROFILE_V1}),
            required_actions=frozenset({"dtcs:aggregate"}),
            required_functions=frozenset({"dtcs:sum", "dtcs:count_all"}),
            plan={
                "planIdentity": "dtcs.transform-plan/2",
                "inputs": {"t": {"id": "t"}},
                "actions": [
                    {
                        "id": "a1",
                        "kind": {
                            "action": "dtcs:aggregate",
                            "id": "a1",
                            "parameters": {
                                "aggregates": [
                                    {
                                        "name": "total",
                                        "expression": {
                                            "kind": "call",
                                            "callee": "dtcs:sum",
                                            "args": [
                                                {
                                                    "kind": "fieldRef",
                                                    "scope": "field",
                                                    "target": "n",
                                                }
                                            ],
                                        },
                                    },
                                    {
                                        "name": "count",
                                        "expression": {
                                            "kind": "call",
                                            "callee": "dtcs:count_all",
                                            "args": [],
                                        },
                                    },
                                ]
                            },
                            "target": "t",
                        },
                    }
                ],
                "outputs": {"result": {"id": "result"}},
            },
            inputs={"t": [{"n": 1}, {"n": 3}]},
            expected=[{"count": 2, "total": 4}],
        ),
    )


def _baseline_field_actions() -> FixtureCase:
    return FixtureCase(
        name="baseline_field_actions",
        required_profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
        required_actions=frozenset(
            {
                "dtcs:distinct",
                "dtcs:deduplicate",
                "dtcs:drop_fields",
                "dtcs:rename_fields",
            }
        ),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"t": {"id": "t"}},
            "actions": [
                {
                    "id": "d1",
                    "kind": {
                        "action": "dtcs:distinct",
                        "id": "d1",
                        "parameters": {},
                        "target": "t",
                    },
                },
                {
                    "id": "d2",
                    "kind": {
                        "action": "dtcs:deduplicate",
                        "id": "d2",
                        "parameters": {},
                        "target": "d1",
                    },
                },
                {
                    "id": "d3",
                    "kind": {
                        "action": "dtcs:drop_fields",
                        "id": "d3",
                        "parameters": {"fields": ["b"]},
                        "target": "d2",
                    },
                },
                {
                    "id": "d4",
                    "kind": {
                        "action": "dtcs:rename_fields",
                        "id": "d4",
                        "parameters": {"mapping": {"a": "id"}},
                        "target": "d3",
                    },
                },
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "d4", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"t": [{"a": 1, "b": "x"}, {"a": 1, "b": "x"}, {"a": 2, "b": "y"}]},
        expected=[{"id": 1}, {"id": 2}],
    )


def _baseline_union() -> FixtureCase:
    return FixtureCase(
        name="baseline_union",
        required_profiles=frozenset({RELATIONAL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:union"}),
        required_functions=frozenset(),
        plan={
            "planIdentity": "dtcs.transform-plan/2",
            "inputs": {"left": {"id": "left"}, "right": {"id": "right"}},
            "actions": [
                {
                    "id": "u1",
                    "kind": {
                        "action": "dtcs:union",
                        "id": "u1",
                        "parameters": {"other": "right", "mode": "byName"},
                        "target": "left",
                    },
                }
            ],
            "outputs": {"result": {"id": "result"}},
            "requirements": {
                "dependencies": [{"from": "u1", "to": "result", "reason": "lineage"}]
            },
        },
        inputs={"left": [{"a": 1}], "right": [{"a": 2}]},
        expected=[{"a": 1}, {"a": 2}],
    )


def _baseline_join_modes() -> tuple[FixtureCase, ...]:
    """Exercise every declared relational join mode with a small corpus."""
    inputs = {
        "left": [{"id": 1, "left": "a"}, {"id": 2, "left": "b"}],
        "right": [{"id": 2, "right": "x"}, {"id": 3, "right": "y"}],
    }
    expected_by_mode = {
        "inner": [{"id": 2, "left": "b", "right": "x"}],
        "left": [
            {"id": 1, "left": "a", "right": None},
            {"id": 2, "left": "b", "right": "x"},
        ],
        "right": [
            {"id": 2, "left": "b", "right": "x"},
            {"id": 3, "left": None, "right": "y"},
        ],
        "full": [
            {"id": 1, "left": "a", "right": None},
            {"id": 2, "left": "b", "right": "x"},
            {"id": 3, "left": None, "right": "y"},
        ],
        "semi": [{"id": 2, "left": "b"}],
        "anti": [{"id": 1, "left": "a"}],
    }
    cases: list[FixtureCase] = []
    for mode, expected in expected_by_mode.items():
        cases.append(
            FixtureCase(
                name=f"baseline_join_{mode}",
                required_profiles=frozenset({RELATIONAL_PROFILE_V1}),
                required_actions=frozenset({"dtcs:join"}),
                required_functions=frozenset(),
                required_join_modes=frozenset({mode}),
                required_collision_policies=frozenset({"fail"}),
                plan={
                    "planIdentity": "dtcs.transform-plan/2",
                    "inputs": {"left": {"id": "left"}, "right": {"id": "right"}},
                    "actions": [
                        {
                            "id": "j1",
                            "kind": {
                                "action": "dtcs:join",
                                "id": "j1",
                                "parameters": {
                                    "type": mode,
                                    "right": "right",
                                    "leftKey": "id",
                                    "rightKey": "id",
                                    "collisionPolicy": "fail",
                                },
                                "target": "left",
                            },
                        }
                    ],
                    "outputs": {"result": {"id": "result"}},
                },
                inputs=inputs,
                expected=expected,
            )
        )
    # A cross join has no key predicate and therefore uses a two-row corpus.
    cases.append(
        FixtureCase(
            name="baseline_join_cross",
            required_profiles=frozenset({RELATIONAL_PROFILE_V1}),
            required_actions=frozenset({"dtcs:join"}),
            required_functions=frozenset(),
            required_join_modes=frozenset({"cross"}),
            required_collision_policies=frozenset({"fail"}),
            plan={
                "planIdentity": "dtcs.transform-plan/2",
                "inputs": {"left": {"id": "left"}, "right": {"id": "right"}},
                "actions": [
                    {
                        "id": "j1",
                        "kind": {
                            "action": "dtcs:join",
                            "id": "j1",
                            "parameters": {
                                "type": "cross",
                                "right": "right",
                                "collisionPolicy": "fail",
                            },
                            "target": "left",
                        },
                    }
                ],
                "outputs": {"result": {"id": "result"}},
            },
            inputs={
                "left": inputs["left"],
                "right": [{"rid": 2, "right": "x"}, {"rid": 3, "right": "y"}],
            },
            expected=[
                {"id": 1, "left": "a", "rid": 2, "right": "x"},
                {"id": 1, "left": "a", "rid": 3, "right": "y"},
                {"id": 2, "left": "b", "rid": 2, "right": "x"},
                {"id": 2, "left": "b", "rid": 3, "right": "y"},
            ],
        )
    )
    return tuple(cases)


def _baseline_union_modes() -> tuple[FixtureCase, ...]:
    """Exercise both declared relational union modes."""
    case = _baseline_union()
    by_name = FixtureCase(
        name="baseline_union_by_name",
        required_profiles=case.required_profiles,
        required_actions=case.required_actions,
        required_functions=case.required_functions,
        plan=case.plan,
        inputs=case.inputs,
        expected=case.expected,
        required_union_modes=frozenset({"byName"}),
    )
    by_position_plan = {
        **case.plan,
        "actions": [
            {
                **case.plan["actions"][0],
                "kind": {
                    **case.plan["actions"][0]["kind"],
                    "parameters": {"other": "right", "mode": "byPosition"},
                },
            }
        ],
    }
    by_position = FixtureCase(
        name="baseline_union_by_position",
        required_profiles=case.required_profiles,
        required_actions=case.required_actions,
        required_functions=case.required_functions,
        plan=by_position_plan,
        inputs={"left": [{"a": 1}], "right": [{"b": 2}]},
        expected=[{"a": 1}, {"a": 2}],
        required_union_modes=frozenset({"byPosition"}),
    )
    return by_name, by_position


FIXTURES: tuple[FixtureCase, ...] = (
    _kernel_filter_project(),
    _kernel_project_identity(),
    _substr_literal_replace(),
    _decimal_extremes(),
    _relational_aggregate(),
    _sort_nulls_limit(),
    _empty_ungrouped_count(),
    _reject_suffix_collision(),
    _string_advanced_trim_regex(),
    _string_advanced_ltrim_split(),
    _conversion_to_string(),
    _conversion_cast_integer(),
    _conversion_try_cast(),
    _statistics_variance(),
    _statistics_stddev(),
    _window_v1_row_number(),
    _window_v1_lag(),
    _reject_window_frame(),
    _complex_values_array_size(),
    _complex_types_field_access(),
    _complex_types_index(),
    _reshape_explode(),
    _reshape_explode_empty(),
    _reject_missing_literal_without_three_state(),
    _baseline_scalar_functions(),
    _baseline_aggregate_functions(),
    _baseline_field_actions(),
    _baseline_union(),
    *_baseline_join_modes(),
    *_baseline_union_modes(),
    *_qualified_action_smokes(),
    *_qualified_function_smokes(),
)


def fixtures_for_capabilities(
    *,
    profiles: frozenset[str],
    actions: frozenset[str],
    functions: frozenset[str],
    operators: frozenset[str] = frozenset(),
    types: frozenset[str] = frozenset(),
    semantic_modes: frozenset[str] = frozenset(),
    join_modes: frozenset[str] = frozenset(),
    union_modes: frozenset[str] = frozenset(),
    collision_policies: frozenset[str] = frozenset(),
) -> list[FixtureCase]:
    """Return fixtures whose required claims are covered by the compiler."""
    selected: list[FixtureCase] = []
    for case in FIXTURES:
        if profiles and not case.required_profiles.issubset(profiles):
            continue
        if not case.required_actions.issubset(actions):
            continue
        if not case.required_functions.issubset(functions):
            continue
        if not case.expect_unsupported:
            if not case.required_operators.issubset(operators):
                continue
            if not case.required_types.issubset(types):
                continue
            if not case.required_semantic_modes.issubset(semantic_modes):
                continue
        if not case.required_join_modes.issubset(join_modes):
            continue
        if not case.required_union_modes.issubset(union_modes):
            continue
        if not case.required_collision_policies.issubset(collision_policies):
            continue
        selected.append(case)
    return selected


def mandatory_capability_keys(
    *,
    profiles: frozenset[str],
    actions: frozenset[str],
    functions: frozenset[str],
    operators: frozenset[str] = frozenset(),
    types: frozenset[str] = frozenset(),
    semantic_modes: frozenset[str] = frozenset(),
    join_modes: frozenset[str] = frozenset(),
    union_modes: frozenset[str] = frozenset(),
    collision_policies: frozenset[str] = frozenset(),
) -> set[str]:
    """Capability keys that must have at least one selected fixture."""
    keys: set[str] = set()
    for profile in profiles:
        keys.add(f"profile:{profile}")
    for action in actions:
        keys.add(f"action:{action}")
    for function in functions:
        keys.add(f"function:{function}")
    for operator in operators:
        keys.add(f"operator:{operator}")
    for type_name in types:
        keys.add(f"type:{type_name}")
    for mode in semantic_modes:
        keys.add(f"semantic_mode:{mode}")
    for mode in join_modes:
        keys.add(f"join_mode:{mode}")
    for mode in union_modes:
        keys.add(f"union_mode:{mode}")
    for policy in collision_policies:
        keys.add(f"collision_policy:{policy}")
    return keys


def covered_capability_keys(cases: list[FixtureCase]) -> set[str]:
    keys: set[str] = set()
    for case in cases:
        for profile in case.required_profiles:
            keys.add(f"profile:{profile}")
        for action in case.required_actions:
            keys.add(f"action:{action}")
        for function in case.required_functions:
            keys.add(f"function:{function}")
        for operator in case.required_operators:
            keys.add(f"operator:{operator}")
        for type_name in case.required_types:
            keys.add(f"type:{type_name}")
        for mode in case.required_semantic_modes:
            keys.add(f"semantic_mode:{mode}")
        for mode in case.required_join_modes:
            keys.add(f"join_mode:{mode}")
        for mode in case.required_union_modes:
            keys.add(f"union_mode:{mode}")
        for policy in case.required_collision_policies:
            keys.add(f"collision_policy:{policy}")
    return keys
