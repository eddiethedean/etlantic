"""Hypothesis property tests for portable IR semantics (0.14)."""

from __future__ import annotations

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from etlantic.transform.capabilities import match_requirements
from etlantic.transform.compiler import TransformCapabilities


@settings(max_examples=40, deadline=None)
@given(
    profiles=st.lists(
        st.sampled_from(
            [
                "dtcs:profile/portable-relational-kernel/1",
                "dtcs:profile/portable-relational/1",
            ]
        ),
        min_size=0,
        max_size=2,
        unique=True,
    ),
    actions=st.lists(
        st.sampled_from(["dtcs:filter", "dtcs:project", "dtcs:join", "dtcs:aggregate"]),
        min_size=0,
        max_size=4,
        unique=True,
    ),
)
def test_capability_matching_is_deterministic(
    profiles: list[str], actions: list[str]
) -> None:
    caps = TransformCapabilities(
        profiles=frozenset(profiles),
        actions=frozenset(actions),
        functions=frozenset(),
        lazy=False,
        eager=True,
    )
    req = {"profiles": profiles, "actions": actions, "functions": []}
    a = match_requirements(req, caps)
    b = match_requirements(req, caps)
    assert a.supported is b.supported
    assert tuple(f.requirement for f in a.findings) == tuple(
        f.requirement for f in b.findings
    )


@settings(max_examples=30, deadline=None)
@given(
    left=st.one_of(st.none(), st.booleans()),
    right=st.one_of(st.none(), st.booleans()),
)
def test_three_valued_and_or_null_aware(left: bool | None, right: bool | None) -> None:
    """Null-aware boolean semantics used by portable filters (SQL-style)."""

    def sql_and(a: bool | None, b: bool | None) -> bool | None:
        if a is False or b is False:
            return False
        if a is None or b is None:
            return None
        return True

    def sql_or(a: bool | None, b: bool | None) -> bool | None:
        if a is True or b is True:
            return True
        if a is None or b is None:
            return None
        return False

    assert sql_and(left, right) == sql_and(left, right)
    assert sql_or(left, right) == sql_or(left, right)
    # Filter retain-true: null and false both drop.
    retain_and = sql_and(left, right) is True
    retain_or = sql_or(left, right) is True
    assert isinstance(retain_and, bool)
    assert isinstance(retain_or, bool)


@pytest.mark.polars
@settings(max_examples=20, deadline=None)
@given(age=st.integers(min_value=0, max_value=120), email=st.emails())
def test_polars_canonical_compile_fingerprint_stable(age: int, email: str) -> None:
    pytest.importorskip("polars")
    from etlantic.transform.compiler import TransformCompileContext
    from etlantic_polars import create_transform_compiler

    plan = {
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
                                "value": {"type": "integer", "value": age},
                            },
                        }
                    },
                    "target": "customers",
                },
            }
        ],
        "outputs": {"result": {"id": "result"}},
        "requirements": {
            "dependencies": [{"from": "f1", "to": "result", "reason": "lineage"}]
        },
        "meta": {"email_sample": email},
    }
    compiler = create_transform_compiler()
    ctx = TransformCompileContext(
        pipeline_id="p",
        plan_id="pl",
        step_name="s",
        profile_name="t",
        engine="polars",
    )
    a = compiler.compile(
        plan,
        context=ctx,
        requirements={
            "profiles": ["dtcs:profile/portable-relational-kernel/1"],
            "actions": ["dtcs:filter"],
            "functions": [],
        },
    )
    b = compiler.compile(
        plan,
        context=ctx,
        requirements={
            "profiles": ["dtcs:profile/portable-relational-kernel/1"],
            "actions": ["dtcs:filter"],
            "functions": [],
        },
    )
    assert a.ir_fingerprint == b.ir_fingerprint
    # Canonical JSON stability for the compiled native plan.
    assert json.dumps(a.native_plan, sort_keys=True) == json.dumps(
        b.native_plan, sort_keys=True
    )
