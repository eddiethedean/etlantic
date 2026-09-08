"""Security corpus for portable SQL lowering (no value interpolation)."""

from __future__ import annotations

import asyncio

import pytest

from etlantic.transform.compiler import (
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
)

pytestmark = pytest.mark.sql


def _hostile_filter_plan(value: str) -> dict:
    return {
        "planIdentity": "dtcs.transform-plan/2",
        "profile": "dtcs:profile/portable-relational-kernel/1",
        "inputs": {"rows": {}},
        "outputs": {"result": {}},
        "actions": [
            {
                "id": "f1",
                "kind": {
                    "action": "dtcs:filter",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "eq",
                            "left": {
                                "kind": "fieldRef",
                                "scope": "column",
                                "target": "name",
                            },
                            "right": {
                                "kind": "literal",
                                "value": {"type": "string", "value": value},
                            },
                        }
                    },
                },
            }
        ],
    }


def test_portable_sql_binds_injection_payloads() -> None:
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    compiler = create_transform_compiler()
    payload = "x'; DROP TABLE t;--"
    plan = _hostile_filter_plan(payload)
    planning = TransformPlanningContext(
        pipeline_id="sec",
        step_name="step",
        profile_name="sec",
        engine="sql",
    )
    assert compiler.analyze(plan, context=planning).supported
    compiled = compiler.compile(
        plan,
        context=TransformCompileContext(
            pipeline_id="sec",
            plan_id="p",
            step_name="step",
            profile_name="sec",
            engine="sql",
        ),
    )
    assert "DROP" not in str(compiled.explain).upper()
    bundle = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"rows": [{"name": "ok", "id": 1}]},
            parameters={},
            context=TransformExecutionContext(
                run_id="sec",
                pipeline_id="sec",
                plan_id="p",
                step_name="step",
                engine="sql",
            ),
        )
    )
    # Payload must not appear as interpolated SQL text in metrics/explain.
    assert "DROP TABLE" not in str(bundle.metrics).upper()
    assert "DROP TABLE" not in str(compiled.explain).upper()


def test_portable_sql_rejects_trusted_fragments() -> None:
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    compiler = create_transform_compiler()
    plan = {
        "planIdentity": "dtcs.transform-plan/2",
        "profile": "dtcs:profile/portable-relational-kernel/1",
        "inputs": {"rows": {}},
        "outputs": {"result": {}},
        "actions": [],
        "metadata": {"trusted_fragment": "SELECT 1"},
    }
    report = compiler.analyze(
        plan,
        context=TransformPlanningContext(
            pipeline_id="sec",
            step_name="step",
            profile_name="sec",
            engine="sql",
        ),
    )
    assert report.supported is False
    assert any(f.code == "PMXFORM301" for f in report.findings)


def test_hostile_identifier_sanitized_for_temp_tables() -> None:
    pytest.importorskip("sqlalchemy")
    from etlantic.sql.helpers import require_safe_identifier
    from etlantic_sql.transform_compiler import _safe_table

    cleaned = _safe_table('evil"; DROP TABLE t;--')
    assert ";" not in cleaned
    assert '"' not in cleaned
    require_safe_identifier(cleaned)
    with pytest.raises(ValueError):
        require_safe_identifier('evil"; DROP TABLE t;--')


def test_postgresql_portable_literals_preserve_their_declared_type() -> None:
    """Typed portable literals avoid PostgreSQL polymorphic bind ambiguity."""
    from etlantic_sql.compiler import SqlCompiler
    from etlantic_sql.lowering.expr import lower_expr

    expression = lower_expr(
        {"kind": "literal", "value": {"type": "null", "value": None}},
        parameters={},
    )
    params: dict[str, object] = {}
    rendered = SqlCompiler(dialect="postgresql", supports_merge=True).compile_expr(
        expression, params=params, relation_sql='"t"'
    )

    assert rendered == "CAST(:p1 AS TEXT)"
    assert params == {"p1": None}
