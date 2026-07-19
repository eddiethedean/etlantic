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


def _kernel_filter_project() -> FixtureCase:
    return FixtureCase(
        name="kernel_filter_project_lower",
        required_profiles=frozenset({KERNEL_PROFILE_V1}),
        required_actions=frozenset({"dtcs:filter", "dtcs:project", "dtcs:with_fields"}),
        required_functions=frozenset({"dtcs:lower"}),
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


FIXTURES: tuple[FixtureCase, ...] = (
    _kernel_filter_project(),
    _substr_literal_replace(),
    _decimal_extremes(),
    _relational_aggregate(),
    _sort_nulls_limit(),
    _empty_ungrouped_count(),
    _reject_suffix_collision(),
)


def fixtures_for_capabilities(
    *,
    profiles: frozenset[str],
    actions: frozenset[str],
    functions: frozenset[str],
) -> list[FixtureCase]:
    """Return fixtures whose required claims are covered by the compiler."""
    selected: list[FixtureCase] = []
    for case in FIXTURES:
        if not case.required_profiles.issubset(profiles):
            continue
        if not case.required_actions.issubset(actions):
            continue
        if not case.required_functions.issubset(functions):
            continue
        selected.append(case)
    return selected


def mandatory_capability_keys(
    *,
    profiles: frozenset[str],
    actions: frozenset[str],
    functions: frozenset[str],
) -> set[str]:
    """Capability keys that must have at least one selected fixture."""
    keys: set[str] = set()
    for profile in profiles:
        if profile in {KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}:
            keys.add(f"profile:{profile}")
    for action in actions:
        keys.add(f"action:{action}")
    for function in functions:
        keys.add(f"function:{function}")
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
    return keys
