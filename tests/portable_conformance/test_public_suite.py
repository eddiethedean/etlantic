"""Public portable transform conformance suite smoke tests."""

from __future__ import annotations

import pytest

from etlantic.testing import (
    portable_transform_conformance,
    run_portable_transform_conformance_suite,
)


def test_suite_passes_local() -> None:
    from etlantic.transform.local_compiler import LocalTransformCompiler

    run_portable_transform_conformance_suite(LocalTransformCompiler())


@pytest.mark.datafusion
def test_suite_passes_datafusion() -> None:
    pytest.importorskip("datafusion")
    from etlantic_datafusion import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


@pytest.mark.datafusion
def test_datafusion_analysis_reports_native_pushdown_boundaries() -> None:
    pytest.importorskip("datafusion")
    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic_datafusion import create_transform_compiler

    report = create_transform_compiler().analyze(
        {"actions": [{"kind": {"action": "dtcs:limit", "parameters": {"n": 1}}}]},
        context=TransformPlanningContext("p", "s", "profile", "datafusion"),
    )
    assert report.pushdown
    assert report.pushdown[0].outcome == "unknown"
    assert report.pushdown[0].physical_effects == ()


@pytest.mark.datafusion
def test_datafusion_lazy_validation_enforces_fail_policy() -> None:
    pytest.importorskip("datafusion")
    import pyarrow as pa
    from pydantic import BaseModel

    from datafusion import SessionContext
    from etlantic.dataframe.protocol import (
        DataframeExecutionContext,
        DataframeValidationOutcome,
        DataframeValidationPolicy,
        ValidationDecision,
    )
    from etlantic_datafusion import create_plugin

    class Row(BaseModel):
        id: int

    frame = SessionContext().from_arrow(pa.Table.from_pylist([{"id": "bad"}]))
    context = DataframeExecutionContext(
        run_id="r",
        pipeline_id="p",
        plan_id="plan",
        step_name="s",
        engine="datafusion",
        validation_policy=DataframeValidationPolicy(
            output_outcome=DataframeValidationOutcome.FAIL,
        ),
    )
    _, decision, diagnostics, _ = create_plugin().validate_frame(
        frame,
        contract_type=Row,
        context=context,
        boundary="output_validation",
    )
    assert decision is ValidationDecision.FAILED
    assert diagnostics


@pytest.mark.datafusion
def test_datafusion_keyed_deduplicate_executes_natively() -> None:
    pytest.importorskip("datafusion")
    import asyncio

    import pyarrow as pa

    from datafusion import SessionContext
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )
    from etlantic_datafusion import create_transform_compiler

    plan = {
        "inputs": {"t": {}},
        "actions": [
            {
                "id": "d",
                "kind": {
                    "id": "d",
                    "action": "dtcs:deduplicate",
                    "target": "t",
                    "parameters": {"keys": ["id"]},
                },
            }
        ],
        "outputs": {"result": {}},
        "requirements": {"dependencies": [{"from": "d", "to": "result"}]},
    }
    compiler = create_transform_compiler()
    compiled = compiler.compile(
        plan,
        context=TransformCompileContext("p", "pl", "s", "profile", "datafusion"),
    )
    session = SessionContext()
    frame = session.from_arrow(
        pa.Table.from_pylist([{"id": 1, "value": "a"}, {"id": 1, "value": "b"}])
    )
    result = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"t": frame},
            parameters={},
            context=TransformExecutionContext("r", "p", "pl", "s", "datafusion"),
        )
    ).valid["result"]
    assert len([row for batch in result.collect() for row in batch.to_pylist()]) == 1


@pytest.mark.datafusion
def test_datafusion_null_safe_join_matches_null_keys() -> None:
    pytest.importorskip("datafusion")
    import asyncio

    import pyarrow as pa

    from datafusion import SessionContext
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )
    from etlantic_datafusion import create_transform_compiler

    plan = {
        "inputs": {"left": {}, "right": {}},
        "actions": [
            {
                "id": "j",
                "kind": {
                    "id": "j",
                    "action": "dtcs:join",
                    "target": "left",
                    "parameters": {
                        "right": "right",
                        "type": "inner",
                        "leftKey": "id",
                        "rightKey": "id",
                        "nullSafe": True,
                        "collisionPolicy": "fail",
                    },
                },
            }
        ],
        "outputs": {"result": {}},
        "requirements": {"dependencies": [{"from": "j", "to": "result"}]},
    }
    compiler = create_transform_compiler()
    compiled = compiler.compile(
        plan,
        context=TransformCompileContext("p", "pl", "s", "profile", "datafusion"),
    )
    session = SessionContext()
    inputs = {
        "left": session.from_arrow(pa.Table.from_pylist([{"id": None, "l": "L"}])),
        "right": session.from_arrow(pa.Table.from_pylist([{"id": None, "r": "R"}])),
    }
    result = asyncio.run(
        compiler.execute(
            compiled,
            inputs=inputs,
            parameters={},
            context=TransformExecutionContext("r", "p", "pl", "s", "datafusion"),
        )
    ).valid["result"]
    assert [row for batch in result.collect() for row in batch.to_pylist()] == [
        {"id": None, "l": "L", "r": "R"}
    ]


def test_local_unknown_operator_fails_closed() -> None:
    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler

    plan = {
        "actions": [
            {
                "kind": {
                    "action": "dtcs:filter",
                    "target": "t",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "not-a-real-operator",
                            "left": {"kind": "fieldRef", "target": "x"},
                            "right": {
                                "kind": "literal",
                                "value": {"type": "integer", "value": 1},
                            },
                        }
                    },
                }
            }
        ]
    }
    report = LocalTransformCompiler().analyze(
        plan,
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )
    assert report.supported is False
    assert any(f.requirement == "operator:not-a-real-operator" for f in report.findings)


def test_local_unknown_expression_kind_fails_closed() -> None:
    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler

    plan = {
        "actions": [
            {
                "kind": {
                    "action": "dtcs:project",
                    "target": "t",
                    "parameters": {
                        "fields": [
                            {
                                "name": "x",
                                "expression": {"kind": "not-a-real-expression"},
                            }
                        ]
                    },
                }
            }
        ]
    }
    report = LocalTransformCompiler().analyze(
        plan,
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )
    assert report.supported is False
    assert any(
        f.requirement == "expression_kind:not-a-real-expression"
        for f in report.findings
    )


def test_requirement_matching_rejects_unknown_categories() -> None:
    from etlantic.transform.capabilities import match_requirements
    from etlantic.transform.compiler import TransformCapabilities

    report = match_requirements(
        {"future_dimension": ["required"]}, TransformCapabilities()
    )
    assert report.supported is False
    assert report.findings[0].support == "unknown"


def test_requirement_support_serializes_positive_records() -> None:
    from etlantic.transform.compiler import (
        TransformSupportReport,
        requirement_records_from_mapping,
    )

    report = TransformSupportReport(
        supported=True,
        evidence_fingerprint="evidence",
        requirements=requirement_records_from_mapping({"actions": ["dtcs:filter"]}),
    )
    payload = report.to_requirement_support(target={"engine": "local"})
    assert payload["requirements"]
    assert payload["findings"][0]["support"] == "supported_exact"


@pytest.mark.polars
def test_suite_passes_polars() -> None:
    pytest.importorskip("polars")
    from etlantic_polars import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


@pytest.mark.pandas
def test_suite_passes_pandas() -> None:
    pytest.importorskip("pandas")
    from etlantic_pandas import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


@pytest.mark.spark
def test_suite_passes_pyspark() -> None:
    pytest.importorskip("sparkless")
    from etlantic_pyspark import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


@pytest.mark.sql
def test_suite_passes_sql() -> None:
    pytest.importorskip("sqlalchemy")
    from etlantic_sql import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


@pytest.mark.duckdb
def test_suite_passes_duckdb() -> None:
    pytest.importorskip("duckdb")
    from etlantic_duckdb import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


def test_module_export_surface() -> None:
    assert hasattr(
        portable_transform_conformance, "run_portable_transform_conformance_suite"
    )


def test_local_join_preserves_unmatched_left_key() -> None:
    import asyncio

    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )
    from etlantic.transform.local_compiler import LocalTransformCompiler

    plan = {
        "inputs": {"left": {}, "right": {}},
        "actions": [
            {
                "id": "join",
                "kind": {
                    "id": "join",
                    "action": "dtcs:join",
                    "target": "left",
                    "parameters": {
                        "right": "right",
                        "type": "left",
                        "leftKey": "id",
                        "rightKey": "id",
                        "collisionPolicy": "fail",
                    },
                },
            }
        ],
        "outputs": {"result": {}},
        "requirements": {"dependencies": [{"from": "join", "to": "result"}]},
    }
    compiler = LocalTransformCompiler()
    compiled = compiler.compile(
        plan,
        context=TransformCompileContext("p", "pl", "s", "profile", "local"),
    )
    result = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"left": [{"id": 1}], "right": [{"id": 2, "value": "r"}]},
            parameters={},
            context=TransformExecutionContext("r", "p", "pl", "s", "local"),
        )
    ).valid["result"]
    assert result == [{"id": 1, "value": None}]


def test_local_distinct_ignores_mapping_insertion_order() -> None:
    import asyncio

    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )
    from etlantic.transform.local_compiler import LocalTransformCompiler

    plan = {
        "inputs": {"t": {}},
        "actions": [
            {
                "id": "d",
                "kind": {
                    "id": "d",
                    "action": "dtcs:distinct",
                    "target": "t",
                    "parameters": {},
                },
            }
        ],
        "outputs": {"result": {}},
        "requirements": {"dependencies": [{"from": "d", "to": "result"}]},
    }
    compiler = LocalTransformCompiler()
    compiled = compiler.compile(
        plan,
        context=TransformCompileContext("p", "pl", "s", "profile", "local"),
    )
    result = asyncio.run(
        compiler.execute(
            compiled,
            inputs={"t": [{"a": 1, "b": 2}, {"b": 2, "a": 1}]},
            parameters={},
            context=TransformExecutionContext("r", "p", "pl", "s", "local"),
        )
    ).valid["result"]
    assert len(result) == 1
