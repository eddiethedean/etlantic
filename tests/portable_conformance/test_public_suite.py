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


def test_conformance_rejects_incomplete_baseline_profile_claim() -> None:
    from etlantic.transform.compiler import (
        COMPILER_PROTOCOL,
        TransformCapabilities,
        TransformCompilerInfo,
    )
    from etlantic.transform.protocol import KERNEL_PROFILE_V1

    class IncompleteCompiler:
        info = TransformCompilerInfo(
            name="incomplete",
            version="0",
            engine="local",
            compiler_protocol=COMPILER_PROTOCOL,
            capabilities=TransformCapabilities(
                profiles=frozenset({KERNEL_PROFILE_V1}),
                actions=frozenset({"dtcs:project"}),
            ),
        )

    with pytest.raises(AssertionError, match="Baseline profile claim is incomplete"):
        run_portable_transform_conformance_suite(IncompleteCompiler())


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
    assert report.pushdown[0].outcome == "not_applicable"
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


@pytest.mark.datafusion
def test_datafusion_union_and_full_join_preserve_schema_and_keys() -> None:
    pytest.importorskip("datafusion")
    import asyncio

    import pyarrow as pa

    from datafusion import SessionContext
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )
    from etlantic_datafusion import create_transform_compiler

    async def execute(action: str, parameters: dict, left: list, right: list) -> list:
        plan = {
            "inputs": {"left": {}, "right": {}},
            "actions": [
                {
                    "id": "a",
                    "kind": {
                        "id": "a",
                        "action": action,
                        "target": "left",
                        "parameters": parameters,
                    },
                }
            ],
            "outputs": {"result": {}},
            "requirements": {"dependencies": [{"from": "a", "to": "result"}]},
        }
        compiler = create_transform_compiler()
        compiled = compiler.compile(
            plan,
            context=TransformCompileContext("p", "pl", "s", "profile", "datafusion"),
        )
        session = SessionContext()
        output = await compiler.execute(
            compiled,
            inputs={
                "left": session.from_arrow(pa.Table.from_pylist(left)),
                "right": session.from_arrow(pa.Table.from_pylist(right)),
            },
            parameters={},
            context=TransformExecutionContext("r", "p", "pl", "s", "datafusion"),
        )
        return [
            row
            for batch in output.valid["result"].collect()
            for row in batch.to_pylist()
        ]

    unioned = asyncio.run(
        execute(
            "dtcs:union",
            {"mode": "byName", "allowMissingColumns": True, "other": "right"},
            [{"a": 1}],
            [{"b": 2}],
        )
    )
    assert {tuple(sorted(row.items())) for row in unioned} == {
        (("a", 1), ("b", None)),
        (("a", None), ("b", 2)),
    }
    joined = asyncio.run(
        execute(
            "dtcs:join",
            {
                "type": "full",
                "right": "right",
                "leftKey": "id",
                "rightKey": "id",
                "collisionPolicy": "fail",
            },
            [{"id": 1, "l": "L"}],
            [{"id": 2, "r": "R"}],
        )
    )
    assert {row["id"] for row in joined} == {1, 2}


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
    assert payload["findings"][0]["support"] == "unknown"


def test_requirement_support_uses_explicit_canonical_positive_evidence() -> None:
    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler

    compiler = LocalTransformCompiler()
    report = compiler.analyze(
        {"actions": [{"kind": {"action": "dtcs:filter"}}]},
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )
    payload = report.to_requirement_support(
        target={
            "engine": "local",
            "compiler": compiler.info.name,
            "version": compiler.info.version,
        }
    )
    assert any(item["support"] == "supported_exact" for item in payload["findings"])


def test_requirement_support_serializes_unknown_requirements_fail_closed() -> None:
    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler

    report = LocalTransformCompiler().analyze(
        {},
        context=TransformPlanningContext("p", "s", "profile", "local"),
        requirements={"future_dimension": ["x"]},
    )
    payload = report.to_requirement_support(target={"engine": "local"})
    assert all(item["id"].startswith("dtcs@1/") for item in payload["requirements"])
    assert {item["requirement"] for item in payload["findings"]} == {
        item["id"] for item in payload["requirements"]
    }
    assert any(item["support"] == "unknown" for item in payload["findings"])


def test_requirement_support_maps_legacy_findings_and_rejects_unknown_target_fields() -> (
    None
):
    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler

    report = LocalTransformCompiler().analyze(
        {},
        context=TransformPlanningContext("p", "s", "profile", "local"),
        requirements={"actions": ["dtcs:filter"], "functions": ["dtcs:not_real"]},
    )
    payload = report.to_requirement_support(target={"engine": "local"})
    function_id = next(
        item["id"] for item in payload["requirements"] if "/functions/" in item["id"]
    )
    assert function_id == "dtcs@1/functions/dtcs:not_real#functions"
    function_finding = next(
        item for item in payload["findings"] if item["requirement"] == function_id
    )
    assert function_finding["reason_code"] == "PMXFORM301"
    assert function_finding["reason"] == "function is not implemented"
    with pytest.raises(ValueError, match="unsupported fields"):
        report.to_requirement_support(target={"engine": "local", "secret": "value"})


def test_requirement_support_rejects_evidence_free_positive_reports() -> None:
    from etlantic.transform.compiler import (
        TransformSupportReport,
        requirement_records_from_mapping,
    )

    report = TransformSupportReport(
        supported=True,
        requirements=requirement_records_from_mapping({"actions": ["dtcs:filter"]}),
    )
    payload = report.to_requirement_support(target={"engine": "local"})
    assert all(item["support"] == "unknown" for item in payload["findings"])


def test_runtime_preflight_rejects_evidence_free_descriptor() -> None:
    from types import SimpleNamespace

    from etlantic.transform.compiler import preflight_portable_support
    from etlantic.transform.local_compiler import LocalTransformCompiler

    compiler = LocalTransformCompiler()
    descriptor = SimpleNamespace(
        compiler_evidence_fingerprint=None,
        support_summary={},
    )
    with pytest.raises(ValueError, match="evidence"):
        preflight_portable_support(descriptor, compiler, engine="local")


def test_host_compiler_reports_explicit_non_pushdown_boundaries() -> None:
    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler

    report = LocalTransformCompiler().analyze(
        {"actions": [{"kind": {"action": "dtcs:project"}}]},
        context=TransformPlanningContext("p", "s", "profile", "local"),
    )
    assert report.pushdown
    assert {item.outcome for item in report.pushdown} == {"not_applicable"}
    assert all(item.obligation == "informational" for item in report.pushdown)


def test_requirement_support_rejects_nested_provenance_and_source_rows() -> None:
    from etlantic.transform.compiler import (
        TransformSupportReport,
        _support_fingerprint,
        requirement_records_from_mapping,
        validate_requirement_support_payload,
    )

    payload = TransformSupportReport(
        supported=True,
        evidence_fingerprint="evidence",
        requirements=requirement_records_from_mapping({"actions": ["dtcs:filter"]}),
    ).to_requirement_support(target={"engine": "local"})
    payload["evidence"][0]["timestamp"] = "volatile"
    payload["evidence"][0]["source_rows"] = [{"secret": "redacted"}]
    payload["fingerprint"] = _support_fingerprint(payload)
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_requirement_support_payload(payload)


def test_requirement_support_rejects_mismatched_evidence_fingerprint() -> None:
    from etlantic.transform.compiler import (
        TransformSupportReport,
        _support_fingerprint,
        requirement_records_from_mapping,
        validate_requirement_support_payload,
    )

    payload = TransformSupportReport(
        supported=True,
        evidence_fingerprint="evidence-a",
        requirements=requirement_records_from_mapping({"actions": ["dtcs:filter"]}),
    ).to_requirement_support(target={"engine": "local"})
    payload["findings"][0]["evidence_fingerprint"] = "evidence-b"
    payload["fingerprint"] = _support_fingerprint(payload)
    with pytest.raises(ValueError, match="does not match evidence"):
        validate_requirement_support_payload(payload)


@pytest.mark.duckdb
def test_duckdb_satisfies_explicit_relational_profile_requirement() -> None:
    pytest.importorskip("duckdb")
    from etlantic_duckdb import create_transform_compiler

    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.protocol import RELATIONAL_PROFILE_V1

    report = create_transform_compiler().analyze(
        {"actions": []},
        context=TransformPlanningContext("p", "s", "profile", "duckdb"),
        requirements={"profiles": [RELATIONAL_PROFILE_V1]},
    )
    assert report.supported is True
    assert any(
        finding.requirement == f"profile:{RELATIONAL_PROFILE_V1}"
        and finding.support == "supported_exact"
        for finding in report.requirement_findings
    )


def test_requirement_support_does_not_reassign_unmatched_legacy_findings() -> None:
    from etlantic.transform.compiler import (
        TransformSupportFinding,
        TransformSupportReport,
        requirement_records_from_mapping,
    )

    report = TransformSupportReport(
        supported=False,
        findings=(
            TransformSupportFinding(
                code="PMXFORM301",
                requirement="capability:lazy",
                reason="lazy execution is not claimed by the compiler",
            ),
        ),
        requirements=requirement_records_from_mapping({"actions": ["dtcs:filter"]}),
    )
    payload = report.to_requirement_support(target={"engine": "local"})
    legacy = next(item for item in payload["requirements"] if item["scope"] == "legacy")
    assert legacy["parameters"]["legacy_requirement"] == "capability:lazy"
    assert payload["findings"][0]["requirement"] == legacy["id"]


def test_local_round_default_and_null_scalar_semantics() -> None:
    from etlantic.transform.local_compiler import _eval

    def literal(type_: str, value: object) -> dict[str, object]:
        return {"kind": "literal", "value": {"type": type_, "value": value}}

    assert (
        _eval(
            {"kind": "call", "callee": "dtcs:round", "args": [literal("decimal", 3.6)]},
            {},
            {},
        )
        == 4
    )
    for callee, args in (
        ("dtcs:contains", [None, "x"]),
        ("dtcs:concat", [None, "x"]),
        ("dtcs:least", [None, 1]),
    ):
        node = {
            "kind": "call",
            "callee": callee,
            "args": [
                literal("null" if value is None else "string", value) for value in args
            ],
        }
        assert _eval(node, {}, {}) is None


def test_local_by_position_union_rejects_heterogeneous_rows() -> None:
    from etlantic.transform.local_compiler import _apply

    with pytest.raises(ValueError, match="incompatible field counts"):
        _apply(
            [{"a": 1, "b": 2}],
            "dtcs:union",
            {"mode": "byPosition", "other": "right"},
            {"right": [{"x": 3}, {"x": 4, "y": 5}]},
            {},
        )


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


@pytest.mark.datafusion
def test_datafusion_semi_and_anti_join_ignore_right_only_columns() -> None:
    pytest.importorskip("datafusion")
    import asyncio

    import pyarrow as pa

    from datafusion import SessionContext
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )
    from etlantic_datafusion import create_transform_compiler

    compiler = create_transform_compiler()
    for join_type, expected in (
        ("semi", [{"id": 1, "left": "a"}]),
        ("anti", [{"id": 2, "left": "b"}]),
    ):
        plan = {
            "inputs": {"left": {}, "right": {}},
            "actions": [
                {
                    "id": "j",
                    "kind": {
                        "action": "dtcs:join",
                        "target": "left",
                        "parameters": {
                            "right": "right",
                            "type": join_type,
                            "leftKey": "id",
                            "rightKey": "id",
                            "collisionPolicy": "fail",
                        },
                    },
                }
            ],
            "outputs": {"result": {}},
            "requirements": {"dependencies": [{"from": "j", "to": "result"}]},
        }
        compiled = compiler.compile(
            plan,
            context=TransformCompileContext("p", "pl", "s", "profile", "datafusion"),
        )
        session = SessionContext()
        bundle = asyncio.run(
            compiler.execute(
                compiled,
                inputs={
                    "left": session.from_arrow(
                        pa.Table.from_pylist(
                            [{"id": 1, "left": "a"}, {"id": 2, "left": "b"}]
                        )
                    ),
                    "right": session.from_arrow(
                        pa.Table.from_pylist([{"id": 1, "right": "x"}])
                    ),
                },
                parameters={},
                context=TransformExecutionContext("r", "p", "pl", "s", "datafusion"),
            )
        )
        assert bundle.valid["result"].collect()[0].to_pylist() == expected
