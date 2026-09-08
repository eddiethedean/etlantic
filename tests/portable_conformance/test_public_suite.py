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


def _adaptive_support_report(states: dict[str, str]) -> dict[str, object]:
    from etlantic.transform.compiler import (
        COMPILER_PROTOCOL,
        TransformSupportFinding,
        TransformSupportReport,
        requirement_records_from_mapping,
    )

    evidence = "adaptive-fixture-evidence"
    requirements = requirement_records_from_mapping({"actions": list(states)})
    requirement_ids = {
        str((record.get("parameters") or {}).get("value")): str(record["id"])
        for record in requirements
    }
    findings = tuple(
        TransformSupportFinding(
            code="PMXFORM000",
            requirement=requirement_ids[requirement],
            reason="fixture support result",
            support=state,
            evidence_fingerprint=evidence,
            lowering_id="lowering/fixture-v1"
            if state == "supported_with_lowering"
            else None,
            proof_reference="proof/fixture-v1"
            if state == "supported_with_lowering"
            else None,
            conditions=("preserve-null",) if state == "supported_with_lowering" else (),
            physical_effects=("materialization",)
            if state == "supported_with_lowering"
            else (),
        )
        for requirement, state in states.items()
    )
    return TransformSupportReport(
        supported=all(
            state in {"supported_exact", "supported_with_lowering"}
            for state in states.values()
        ),
        evidence_fingerprint=evidence,
        requirements=requirements,
        requirement_findings=findings,
    ).to_requirement_support(
        target={
            "engine": "local",
            "compiler": "adaptive-fixture",
            "version": "1",
            "protocol": COMPILER_PROTOCOL,
            "package": "etlantic-adaptive-fixture/"
            + ",".join(f"{key}={states[key]}" for key in sorted(states)),
        }
    )


def test_adaptive_partial_engine_required_unknown_eliminates_before_scoring() -> None:
    from etlantic.transform.capabilities import evaluate_adaptive_candidates

    result = evaluate_adaptive_candidates(
        [
            {
                "id": "partial",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "dtcs:join": "unknown",
                },
                "support_report": _adaptive_support_report(
                    {"dtcs:filter": "supported_exact", "dtcs:join": "unknown"}
                ),
            },
            {
                "id": "complete",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "dtcs:join": "supported_exact",
                },
                "support_report": _adaptive_support_report(
                    {"dtcs:filter": "supported_exact", "dtcs:join": "supported_exact"}
                ),
            },
        ],
        required_requirements=("dtcs:join",),
        preferred_requirements=("dtcs:filter",),
    )
    partial = next(item for item in result["candidates"] if item["id"] == "partial")
    assert partial["eligible"] is False
    assert partial["decision"] == "eliminated_before_preference_scoring"
    assert result["selected"] == "complete"


def test_adaptive_preferred_unknown_has_no_positive_preference() -> None:
    from etlantic.transform.capabilities import evaluate_adaptive_candidates

    result = evaluate_adaptive_candidates(
        [
            {
                "id": "unknown-preference",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "dtcs:sort": "unknown",
                },
                "support_report": _adaptive_support_report(
                    {"dtcs:filter": "supported_exact", "dtcs:sort": "unknown"}
                ),
            }
        ],
        required_requirements=("dtcs:filter",),
        preferred_requirements=("dtcs:sort",),
    )
    assert result["candidates"][0]["preferred_score"] == 0


def test_adaptive_lowering_records_effects_and_identity() -> None:
    from etlantic.transform.capabilities import evaluate_adaptive_candidates

    result = evaluate_adaptive_candidates(
        [
            {
                "id": "lowered",
                "requirements": {"dtcs:filter": "supported_with_lowering"},
                "support_report": _adaptive_support_report(
                    {"dtcs:filter": "supported_with_lowering"}
                ),
            }
        ],
        required_requirements=("dtcs:filter",),
    )
    lowering = result["candidates"][0]["lowering"]
    assert lowering == {
        "id": "lowering/fixture-v1",
        "requirements": ["dtcs:filter"],
        "proof": "proof/fixture-v1",
        "conditions": ["preserve-null"],
        "physical_effects": ["materialization"],
    }


def test_adaptive_lowering_preserves_independent_identities() -> None:
    from etlantic.transform.capabilities import evaluate_adaptive_candidates

    support_report = _adaptive_support_report(
        {
            "dtcs:filter": "supported_with_lowering",
            "dtcs:join": "supported_with_lowering",
        }
    )
    support_report["findings"][1]["lowering_id"] = "lowering/other-v1"
    support_report["findings"][1]["proof_reference"] = "proof/other-v1"
    support_report["findings"][1]["conditions"] = ["preserve-order"]
    support_report["findings"][1]["physical_effects"] = ["shuffle"]
    from etlantic.transform.compiler import _support_fingerprint

    support_report["fingerprint"] = _support_fingerprint(support_report)
    result = evaluate_adaptive_candidates(
        [
            {
                "id": "lowered",
                "requirements": {
                    "dtcs:filter": "supported_with_lowering",
                    "dtcs:join": "supported_with_lowering",
                },
                "support_report": support_report,
            }
        ],
        required_requirements=("dtcs:filter", "dtcs:join"),
    )
    candidate = result["candidates"][0]
    assert isinstance(candidate, dict)
    assert candidate["lowerings"] == [
        {
            "id": "lowering/fixture-v1",
            "requirements": ["dtcs:filter"],
            "proof": "proof/fixture-v1",
            "conditions": ["preserve-null"],
            "physical_effects": ["materialization"],
        },
        {
            "id": "lowering/other-v1",
            "requirements": ["dtcs:join"],
            "proof": "proof/other-v1",
            "conditions": ["preserve-order"],
            "physical_effects": ["shuffle"],
        },
    ]
    assert "lowering" not in candidate


def test_adaptive_lowering_is_derived_from_support_evidence() -> None:
    from etlantic.transform.capabilities import evaluate_adaptive_candidates

    with pytest.raises(ValueError, match="derived from support evidence"):
        evaluate_adaptive_candidates(
            [
                {
                    "id": "unproven",
                    "requirements": {"dtcs:filter": "supported_with_lowering"},
                    "support_report": _adaptive_support_report(
                        {"dtcs:filter": "supported_with_lowering"}
                    ),
                    "lowering": {
                        "id": "fabricated",
                        "approved": True,
                        "requirements": ["dtcs:filter"],
                        "proof": "anything",
                        "physical_effects": ["anything"],
                    },
                }
            ],
            required_requirements=("dtcs:filter",),
        )


def test_adaptive_evaluation_retains_per_node_selection() -> None:
    from etlantic.transform.capabilities import evaluate_adaptive_candidates

    result = evaluate_adaptive_candidates(
        [
            {
                "node": "orders",
                "id": "partial",
                "requirements": {"dtcs:join": "unknown"},
                "support_report": _adaptive_support_report({"dtcs:join": "unknown"}),
            },
            {
                "node": "orders",
                "id": "complete",
                "requirements": {"dtcs:join": "supported_exact"},
                "support_report": _adaptive_support_report(
                    {"dtcs:join": "supported_exact"}
                ),
            },
            {
                "node": "customers",
                "id": "complete",
                "requirements": {"dtcs:join": "supported_exact"},
                "support_report": _adaptive_support_report(
                    {"dtcs:join": "supported_exact"}
                ),
            },
        ],
        required_requirements={"orders": ("dtcs:join",), "customers": ("dtcs:join",)},
    )
    assert result["nodes"] == ["customers", "orders"]
    assert result["selected"] == {"customers": "complete", "orders": "complete"}
    partial = next(item for item in result["candidates"] if item["id"] == "partial")
    assert partial["node"] == "orders"
    assert partial["required_failures"] == ["dtcs:join"]


def test_adaptive_graph_edge_requirement_invalidates_assignment() -> None:
    from etlantic.transform.capabilities import evaluate_adaptive_candidates

    result = evaluate_adaptive_candidates(
        [
            {
                "node": "orders",
                "id": "native",
                "requirements": {"dtcs:join": "supported_exact"},
                "support_report": _adaptive_support_report(
                    {"dtcs:join": "supported_exact"}
                ),
            },
            {
                "node": "customers",
                "id": "native",
                "requirements": {"dtcs:join": "supported_exact"},
                "support_report": _adaptive_support_report(
                    {"dtcs:join": "supported_exact"}
                ),
            },
        ],
        required_requirements={
            "orders": ("dtcs:join",),
            "customers": ("dtcs:join",),
        },
        edges=(
            {
                "producer": "orders",
                "consumer": "customers",
                "requirements": ("interchange:arrow",),
            },
        ),
    )
    assert result["graph_valid"] is False
    assert result["graph_failures"] == [
        {
            "producer": "orders",
            "consumer": "customers",
            "requirement": "interchange:arrow",
        }
    ]


def test_adaptive_graph_edge_requires_producer_and_consumer_support() -> None:
    from etlantic.transform.capabilities import evaluate_adaptive_candidates

    result = evaluate_adaptive_candidates(
        [
            {
                "id": "producer",
                "node": "source",
                "requirements": {"dtcs:filter": "supported_exact"},
                "support_report": _adaptive_support_report(
                    {"dtcs:filter": "supported_exact"}
                ),
            },
            {
                "id": "consumer",
                "node": "sink",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "interchange:arrow": "supported_exact",
                },
                "support_report": _adaptive_support_report(
                    {
                        "dtcs:filter": "supported_exact",
                        "interchange:arrow": "supported_exact",
                    }
                ),
            },
        ],
        edges=[
            {
                "producer": "source",
                "consumer": "sink",
                "requirements": ["interchange:arrow"],
            }
        ],
    )
    assert result["graph_valid"] is False
    assert result["graph_failures"] == [
        {
            "producer": "source",
            "consumer": "sink",
            "requirement": "interchange:arrow",
        }
    ]


def test_adaptive_graph_selection_prefers_complete_feasible_assignment() -> None:
    from etlantic.transform.capabilities import evaluate_adaptive_candidates

    result = evaluate_adaptive_candidates(
        [
            {
                "node": "source",
                "id": "z-fast",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "interchange:arrow": "unknown",
                },
                "support_report": _adaptive_support_report(
                    {
                        "dtcs:filter": "supported_exact",
                        "interchange:arrow": "unknown",
                    }
                ),
            },
            {
                "node": "source",
                "id": "a-valid",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "interchange:arrow": "supported_exact",
                },
                "support_report": _adaptive_support_report(
                    {
                        "dtcs:filter": "supported_exact",
                        "interchange:arrow": "supported_exact",
                    }
                ),
            },
            {
                "node": "sink",
                "id": "sink",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "interchange:arrow": "supported_exact",
                },
                "support_report": _adaptive_support_report(
                    {
                        "dtcs:filter": "supported_exact",
                        "interchange:arrow": "supported_exact",
                    }
                ),
            },
        ],
        required_requirements={"source": ("dtcs:filter",), "sink": ()},
        preferred_requirements={"source": ("dtcs:filter",)},
        edges=(
            {
                "producer": "source",
                "consumer": "sink",
                "requirements": ("interchange:arrow",),
            },
        ),
    )
    assert result["selected"] == {"sink": "sink", "source": "a-valid"}
    assert result["graph_valid"] is True
    assert result["graph_failures"] == []


def test_adaptive_candidate_target_must_be_unique_per_node() -> None:
    from etlantic.transform.capabilities import evaluate_adaptive_candidates

    report = _adaptive_support_report({"dtcs:filter": "supported_exact"})
    with pytest.raises(ValueError, match="placement target must be unique"):
        evaluate_adaptive_candidates(
            [
                {
                    "node": "source",
                    "id": "one",
                    "requirements": {"dtcs:filter": "supported_exact"},
                    "support_report": report,
                },
                {
                    "node": "source",
                    "id": "two",
                    "requirements": {"dtcs:filter": "supported_exact"},
                    "support_report": report,
                },
            ],
            required_requirements=("dtcs:filter",),
        )


def test_orchestrator_preflights_selected_portable_nodes_as_a_plan() -> None:
    from types import SimpleNamespace
    from typing import Any, cast

    from etlantic.registry import ImplementationDescriptor
    from etlantic.runtime.orchestrator import LocalOrchestrator

    portable = ImplementationDescriptor(
        transformation_id="t",
        engine="local",
        identity="portable",
        kind="portable_compiled",
    )
    native = ImplementationDescriptor(
        transformation_id="t2",
        engine="local",
        identity="native",
        kind="native",
    )
    orchestrator = LocalOrchestrator.__new__(LocalOrchestrator)
    cast(Any, orchestrator).plan = SimpleNamespace(
        implementations={"source": portable, "native": native}
    )
    calls: list[str] = []
    orchestrator._preflight_portable_descriptor = lambda descriptor, *, node_name: (
        calls.append(node_name)
    )
    orchestrator._preflight_portable_plan({"native", "source"})
    assert calls == ["source"]


def test_orchestrator_rejects_before_lifecycle_or_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    from types import SimpleNamespace

    from etlantic.exceptions import NodeExecutionError
    from etlantic.lifecycle.runtime import PipelineRuntime
    from etlantic.model import LogicalGraph, Node, NodeKind
    from etlantic.plan.model import PLAN_SCHEMA
    from etlantic.runtime.orchestrator import LocalOrchestrator
    from etlantic.runtime.request import RunRequest

    graph = LogicalGraph(
        pipeline_id="pipeline:preflight",
        pipeline_name="Preflight",
        nodes=(Node(name="source", kind=NodeKind.SOURCE, identity="source"),),
    )
    plan = SimpleNamespace(
        schema=PLAN_SCHEMA,
        plan_id="plan:preflight",
        pipeline_id=graph.pipeline_id,
        pipeline_name=graph.pipeline_name,
        profile_name="test",
        fingerprint="test",
        logical_graph=graph,
        selected_nodes=None,
        execution_settings={},
        implementations={},
        profile_snapshot={},
        regions=(),
        logical_to_physical={},
        physical_units=(),
        intents={},
        metadata={},
    )
    runtime = PipelineRuntime()
    events: list[object] = []
    runtime.events.subscribe(events.append)
    starts: list[str] = []
    cleanups: list[str] = []

    class Bridge:
        def start_run(self, **kwargs: object) -> None:
            starts.append(str(kwargs["run_id"]))

    class Plugin:
        def cleanup_run(self, **kwargs: object) -> None:
            cleanups.append(str(kwargs["run_id"]))

    runtime._observability_bridge = Bridge()
    runtime.sql_plugins["fake"] = Plugin()
    orchestrator = LocalOrchestrator(runtime, plan, RunRequest())

    monkeypatch.setattr(
        "etlantic.plan.serialize.verify_plan_fingerprint", lambda ignored: None
    )

    def reject(_selected: set[str]) -> None:
        raise NodeExecutionError(
            "portable compiler evidence is stale",
            node_name="source",
            code="PMXFORM306",
        )

    monkeypatch.setattr(orchestrator, "_preflight_portable_plan", reject)
    with pytest.raises(NodeExecutionError, match="stale"):
        asyncio.run(orchestrator.execute())
    assert events == []
    assert starts == []
    assert cleanups == []


def test_adaptive_evidence_drift_rejects_before_io() -> None:
    from etlantic.transform.compiler import preflight_portable_support
    from etlantic.transform.local_compiler import LocalTransformCompiler

    descriptor = type(
        "Descriptor",
        (),
        {"compiler_evidence_fingerprint": "stale", "support_summary": {}},
    )()
    with pytest.raises(ValueError, match="evidence"):
        preflight_portable_support(descriptor, LocalTransformCompiler(), engine="local")


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


def test_backend_null_propagation_for_variadic_scalars() -> None:
    """Backends must not inherit skip-null semantics from native functions."""
    import asyncio

    from etlantic.testing.portable_transform_conformance import (
        default_frame_factory,
        normalize_rows,
        rows_from_frame,
    )
    from etlantic.transform.compiler import (
        TransformCompileContext,
        TransformExecutionContext,
    )

    def literal(type_: str, value: object) -> dict[str, object]:
        return {"kind": "literal", "value": {"type": type_, "value": value}}

    def call(name: str, *args: dict[str, object]) -> dict[str, object]:
        return {"kind": "call", "callee": name, "args": list(args)}

    fields = [
        {"name": name, "expression": expression}
        for name, expression in (
            (
                "concat",
                call("dtcs:concat", literal("null", None), literal("string", "x")),
            ),
            (
                "concat_ws",
                call(
                    "dtcs:concat_ws",
                    literal("string", "-"),
                    literal("null", None),
                    literal("string", "x"),
                ),
            ),
            ("least", call("dtcs:least", literal("null", None), literal("integer", 1))),
            (
                "greatest",
                call("dtcs:greatest", literal("null", None), literal("integer", 1)),
            ),
        )
    ]
    plan = {
        "planIdentity": "dtcs.transform-plan/2",
        "inputs": {"t": {}},
        "actions": [
            {
                "id": "p",
                "kind": {
                    "id": "p",
                    "action": "dtcs:project",
                    "target": "t",
                    "parameters": {"fields": fields},
                },
            }
        ],
        "outputs": {"result": {}},
        "requirements": {"dependencies": [{"from": "p", "to": "result"}]},
    }
    compilers = []
    from etlantic_duckdb import create_transform_compiler as duckdb

    from etlantic_datafusion import create_transform_compiler as datafusion
    from etlantic_pandas import create_transform_compiler as pandas
    from etlantic_polars import create_transform_compiler as polars
    from etlantic_sql import create_transform_compiler as sql

    compilers.extend((polars(), pandas(), sql(), datafusion(), duckdb()))
    for compiler in compilers:
        factory = default_frame_factory(compiler.info.engine)
        try:
            compiled = compiler.compile(
                plan,
                context=TransformCompileContext(
                    "null-semantics",
                    "null-semantics",
                    "plan",
                    "step",
                    compiler.info.engine,
                ),
            )
            bundle = asyncio.run(
                compiler.execute(
                    compiled,
                    inputs={"t": factory([{"seed": 1}])},
                    parameters={},
                    context=TransformExecutionContext(
                        "null-semantics",
                        "null-semantics",
                        "plan",
                        "step",
                        compiler.info.engine,
                    ),
                )
            )
            assert normalize_rows(rows_from_frame(bundle.valid["result"])) == [
                {"concat": None, "concat_ws": None, "least": None, "greatest": None}
            ]
        finally:
            provider = getattr(factory, "_etlantic_provider", None)
            handle = getattr(factory, "_etlantic_handle", None)
            context = getattr(factory, "_etlantic_ctx", None)
            if provider and handle and context:
                provider.release(handle, context)


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


def test_all_compilers_reject_literal_zero_arithmetic() -> None:
    """Portable arithmetic must not inherit backend-specific zero behavior."""
    from etlantic_duckdb import create_transform_compiler as duckdb

    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler
    from etlantic_datafusion import create_transform_compiler as datafusion
    from etlantic_pandas import create_transform_compiler as pandas
    from etlantic_polars import create_transform_compiler as polars
    from etlantic_pyspark import create_transform_compiler as pyspark
    from etlantic_sql import create_transform_compiler as sql

    expression = {
        "kind": "binary",
        "op": "divide",
        "left": {"kind": "literal", "value": {"type": "integer", "value": 1}},
        "right": {"kind": "literal", "value": {"type": "integer", "value": 0}},
    }
    plan = {
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
                        "fields": [{"name": "value", "expression": expression}]
                    },
                },
            }
        ],
        "outputs": {"result": {}},
        "requirements": {"dependencies": [{"from": "p", "to": "result"}]},
    }
    compilers = [
        LocalTransformCompiler(),
        polars(),
        pandas(),
        sql(),
        pyspark(),
        datafusion(),
        duckdb(),
    ]
    for compiler in compilers:
        report = compiler.analyze(
            plan,
            context=TransformPlanningContext("p", "s", "profile", compiler.info.engine),
        )
        assert not report.supported
        assert any(f.code == "PMXFORM302" for f in report.findings)


@pytest.mark.parametrize("operator", ["divide", "modulo"])
def test_all_compilers_reject_dynamic_denominators(operator: str) -> None:
    """A field/parameter divisor cannot be qualified without source I/O."""
    from etlantic_duckdb import create_transform_compiler as duckdb

    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler
    from etlantic_datafusion import create_transform_compiler as datafusion
    from etlantic_pandas import create_transform_compiler as pandas
    from etlantic_polars import create_transform_compiler as polars
    from etlantic_pyspark import create_transform_compiler as pyspark
    from etlantic_sql import create_transform_compiler as sql

    plan = {
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
                            {
                                "name": "value",
                                "expression": {
                                    "kind": "binary",
                                    "op": operator,
                                    "left": {"kind": "fieldRef", "target": "n"},
                                    "right": {"kind": "fieldRef", "target": "d"},
                                },
                            }
                        ]
                    },
                },
            }
        ],
    }
    for compiler in [
        LocalTransformCompiler(),
        polars(),
        pandas(),
        sql(),
        pyspark(),
        datafusion(),
        duckdb(),
    ]:
        report = compiler.analyze(
            plan,
            context=TransformPlanningContext("p", "s", "profile", compiler.info.engine),
        )
        assert not report.supported
        assert any(
            finding.requirement
            == f"arithmetic:{operator}:statically-nonzero-denominator"
            for finding in report.findings
        )


def test_all_compilers_reject_literal_integer_overflow() -> None:
    from etlantic_duckdb import create_transform_compiler as duckdb

    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler
    from etlantic_datafusion import create_transform_compiler as datafusion
    from etlantic_pandas import create_transform_compiler as pandas
    from etlantic_polars import create_transform_compiler as polars
    from etlantic_pyspark import create_transform_compiler as pyspark
    from etlantic_sql import create_transform_compiler as sql

    plan = {
        "actions": [
            {
                "kind": {
                    "action": "dtcs:project",
                    "parameters": {
                        "fields": [
                            {
                                "name": "overflow",
                                "expression": {
                                    "kind": "binary",
                                    "op": "add",
                                    "left": {
                                        "kind": "literal",
                                        "value": {
                                            "type": "integer",
                                            "value": 2**63 - 1,
                                        },
                                    },
                                    "right": {
                                        "kind": "literal",
                                        "value": {"type": "integer", "value": 1},
                                    },
                                },
                            }
                        ]
                    },
                }
            }
        ]
    }
    for compiler in [
        LocalTransformCompiler(),
        polars(),
        pandas(),
        sql(),
        pyspark(),
        datafusion(),
        duckdb(),
    ]:
        report = compiler.analyze(
            plan,
            context=TransformPlanningContext("p", "s", "profile", compiler.info.engine),
        )
        assert not report.supported
        assert any(
            finding.requirement == "arithmetic:integer-overflow"
            for finding in report.findings
        )


@pytest.mark.parametrize("operator", ["add", "subtract", "multiply"])
def test_all_compilers_reject_dynamic_integer_arithmetic(operator: str) -> None:
    from etlantic_duckdb import create_transform_compiler as duckdb

    from etlantic.transform.compiler import TransformPlanningContext
    from etlantic.transform.local_compiler import LocalTransformCompiler
    from etlantic_datafusion import create_transform_compiler as datafusion
    from etlantic_pandas import create_transform_compiler as pandas
    from etlantic_polars import create_transform_compiler as polars
    from etlantic_pyspark import create_transform_compiler as pyspark
    from etlantic_sql import create_transform_compiler as sql

    plan = {
        "actions": [
            {
                "kind": {
                    "action": "dtcs:project",
                    "parameters": {
                        "fields": [
                            {
                                "name": "value",
                                "expression": {
                                    "kind": "binary",
                                    "op": operator,
                                    "left": {"kind": "fieldRef", "target": "n"},
                                    "right": {
                                        "kind": "literal",
                                        "value": {"type": "integer", "value": 1},
                                    },
                                },
                            }
                        ]
                    },
                }
            }
        ]
    }
    for compiler in [
        LocalTransformCompiler(),
        polars(),
        pandas(),
        sql(),
        pyspark(),
        datafusion(),
        duckdb(),
    ]:
        report = compiler.analyze(
            plan,
            context=TransformPlanningContext("p", "s", "profile", compiler.info.engine),
        )
        assert not report.supported
        assert any(
            finding.requirement == f"arithmetic:{operator}:statically-bounded-operands"
            for finding in report.findings
        )


@pytest.mark.polars
def test_suite_passes_polars() -> None:
    pytest.importorskip("polars")
    from etlantic_polars import create_transform_compiler

    run_portable_transform_conformance_suite(create_transform_compiler())


@pytest.mark.polars
def test_suite_passes_polars_lazy() -> None:
    pytest.importorskip("polars")
    import polars as pl

    from etlantic_polars import create_transform_compiler

    run_portable_transform_conformance_suite(
        create_transform_compiler(),
        to_frame=lambda rows: pl.DataFrame(rows).lazy(),
    )


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
