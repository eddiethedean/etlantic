"""Closed adaptive /2 wire-model tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import anyio
import pytest

from etlantic import Data, Extract, Load, Pipeline
from etlantic.exceptions import PipelineExecutionError
from etlantic.orchestration import compile_plan
from etlantic.plan import (
    ADAPTIVE_PLAN_SCHEMA,
    AdaptiveDecision,
    AdaptiveInventory,
    AdaptivePipelinePlan,
    AdaptiveRegion,
    CandidateRecord,
    PhysicalDAG,
    PhysicalUnit,
    TargetDescriptor,
    plan_fingerprint,
    plan_from_json,
    plan_pipeline,
    plan_to_json,
)
from etlantic.plan.adaptive_serialize import adaptive_plan_fingerprint
from etlantic.plan.model import _graph_to_dict
from etlantic.plan.slicing import slice_graph
from etlantic.runtime.request import RunRequest
from etlantic.runtime.scheduler import LocalScheduler, SchedulingContext

jsonschema = pytest.importorskip("jsonschema")

ROOT = Path(__file__).resolve().parents[2]


class Row(Data):
    id: int


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    out: Load[Row] = Load(input=raw, asset="out")


def _plan() -> AdaptivePipelinePlan:
    explicit = plan_pipeline(Sample, profile="local")
    nodes = explicit.logical_graph.node_names()
    inventory = AdaptiveInventory(
        targets=(
            TargetDescriptor(target_id="local", identity="target-1", engine="local"),
        ),
        eligible_target_order=("local",),
        fingerprint="inventory-1",
    )
    candidates = tuple(
        CandidateRecord(
            candidate_id=f"{node}-local",
            node_name=node,
            target_id="local",
            kind="source" if node == "raw" else "sink",
            status="eligible",
        )
        for node in nodes
    )
    decisions = tuple(
        AdaptiveDecision(
            node_name=node, candidate_id=f"{node}-local", target_id="local"
        )
        for node in nodes
    )
    unit = PhysicalUnit(
        identity="unit-1",
        kind="compute",
        target_identity="target-1",
        logical_nodes=nodes,
    )
    dag = PhysicalDAG(
        units=(unit,),
        logical_to_physical={node: "unit-1" for node in nodes},
        topological_order=("unit-1",),
    )
    plan = AdaptivePipelinePlan(
        schema=ADAPTIVE_PLAN_SCHEMA,
        plan_id="plan-2",
        pipeline_id=explicit.pipeline_id,
        pipeline_name=explicit.pipeline_name,
        profile_name="adaptive-local",
        fingerprint="",
        logical_graph=explicit.logical_graph,
        selected_nodes=None,
        inventory=inventory,
        candidates=candidates,
        decisions=decisions,
        objective=(0, 0, 0),
        regions=(
            AdaptiveRegion(identity="region-1", target_id="local", logical_nodes=nodes),
        ),
        physical_dag=dag,
        protocol_versions={
            "plan": ADAPTIVE_PLAN_SCHEMA,
            "physical_unit": "etlantic.physical_unit/1",
        },
        profile_snapshot={},
        security_domain="default",
        metadata={},
    )
    return replace(plan, fingerprint=adaptive_plan_fingerprint(plan))


def test_adaptive_wire_round_trip_and_dispatch() -> None:
    plan = _plan()
    assert plan_fingerprint(plan) == plan.fingerprint
    restored = plan_from_json(plan_to_json(plan))
    assert isinstance(restored, AdaptivePipelinePlan)
    assert restored.to_dict() == plan.to_dict()


def test_tampered_adaptive_section_fails_fingerprint() -> None:
    data = json.loads(plan_to_json(_plan()))
    data["objective"][0] = 99
    with pytest.raises(ValueError, match="PMADP401"):
        plan_from_json(json.dumps(data))


def test_unknown_adaptive_section_rejected() -> None:
    data = _plan().to_dict()
    data["unknown"] = True
    with pytest.raises(ValueError, match="PMADP400"):
        AdaptivePipelinePlan.from_dict(data, verify=False)


def test_adaptive_nested_records_are_immutable() -> None:
    plan = _plan()
    with pytest.raises(TypeError):
        plan.metadata["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        plan.physical_dag.logical_to_physical["raw"] = "other"  # type: ignore[index]


def test_adaptive_top_level_sequences_are_deeply_immutable() -> None:
    plan = replace(_plan(), objective=[0, 0, 0])  # type: ignore[arg-type]

    assert isinstance(plan.objective, tuple)


def test_adaptive_metadata_rejects_live_backend_objects() -> None:
    with pytest.raises(ValueError, match="PMADP"):
        replace(_plan(), metadata={"etlantic.backend": object()})


def test_adaptive_plan_binds_regions_to_inventory_and_decisions() -> None:
    plan = _plan()
    region = replace(plan.regions[0], target_id="missing")
    with pytest.raises(ValueError, match="PMADP403"):
        replace(plan, regions=(region,))

    other_target = TargetDescriptor(
        target_id="other", identity="target-2", engine="local"
    )
    inventory = replace(
        plan.inventory,
        targets=(plan.inventory.targets[0], other_target),
        eligible_target_order=("local", "other"),
    )
    candidates = tuple(
        CandidateRecord(
            candidate_id=f"{node}-other",
            node_name=node,
            target_id="other",
            kind="source" if node == "raw" else "sink",
            status="eligible",
        )
        for node in plan.logical_graph.node_names()
    )
    with pytest.raises(ValueError, match="PMADP403"):
        replace(
            plan,
            inventory=inventory,
            candidates=plan.candidates + candidates,
            regions=(replace(plan.regions[0], target_id="other"),),
        )


def test_adaptive_plan_binds_physical_units_to_target_inventory() -> None:
    plan = _plan()
    unit = replace(plan.physical_dag.units[0], target_identity="missing")
    dag = replace(plan.physical_dag, units=(unit,))
    with pytest.raises(ValueError, match="PMADP403"):
        replace(plan, physical_dag=dag)


def test_physical_unit_rejects_secret_like_metadata() -> None:
    with pytest.raises(ValueError, match="PMADP101"):
        PhysicalUnit(
            identity="unit-secret",
            kind="compute",
            target_identity="target-1",
            metadata={"api_token": "resolved-secret"},
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {"client_secret": "resolved-secret"},
        {"clientSecret": "resolved-secret"},
        {"APIKey": "resolved-secret"},
        {"APIKEY": "resolved-secret"},
        {"authorization": "Bearer resolved-secret"},
        {"endpoint": "postgres://user:pass@host/db"},
        {"nested": {"sample_rows": [{"id": 1}]}},
        {"etlantic.preview": [{"id": 1}]},
    ],
)
def test_physical_unit_rejects_nested_sensitive_envelope_values(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="PMADP101"):
        PhysicalUnit(
            identity="unit-sensitive",
            kind="compute",
            target_identity="target-1",
            metadata=metadata,
        )


def test_physical_unit_from_dict_rejects_credential_url() -> None:
    payload = PhysicalUnit(
        identity="unit-safe",
        kind="compute",
        target_identity="target-1",
    ).to_dict()
    payload["metadata"] = {"endpoint": "postgres://user:pass@host/db"}
    with pytest.raises(ValueError, match="PMADP101"):
        PhysicalUnit.from_dict(payload)


def test_physical_unit_allows_scalar_policy_metadata_values() -> None:
    unit = PhysicalUnit(
        identity="unit-scalar",
        kind="compute",
        target_identity="target-1",
        policy={"values": "normalized"},
        metadata={"etlantic.rule": {"payload": "metadata-only"}},
    )
    assert unit.to_dict()["policy"] == {"values": "normalized"}


@pytest.mark.parametrize(
    ("field", "payload"),
    [
        ("metadata", {"sample_rows": [{"customer_id": 7}]}),
        ("profile_snapshot", {"source_rows": [{"customer_id": 7}]}),
        ("metadata", {"evidence": [{"details": {"rows": [[7, "Ada"]]}}]}),
        ("metadata", {"etlantic.preview": [{"customer_id": 7}]}),
        ("metadata", {"etlantic.preview": {"customer_id": 7}}),
        ("metadata", {"etlantic.SOURCEROWS": {"customer_id": 7}}),
        ("profile_snapshot", {"diagnostic": [{"customer_id": 7}]}),
    ],
)
def test_adaptive_plan_rejects_source_rows_in_all_wire_sections(
    field: str, payload: dict[str, object]
) -> None:
    with pytest.raises(ValueError, match="PMADP101"):
        replace(_plan(), **{field: payload})


def test_adaptive_plan_json_rejects_source_rows() -> None:
    payload = json.loads(plan_to_json(_plan()))
    payload["profile_snapshot"] = {"source_rows": [{"customer_id": 7}]}
    with pytest.raises(ValueError, match="PMADP101"):
        plan_from_json(json.dumps(payload))


def test_adaptive_plan_allows_scalar_profile_snapshot_values() -> None:
    plan = replace(_plan(), profile_snapshot={"data": "metadata-only"})
    assert plan.to_dict()["profile_snapshot"] == {"data": "metadata-only"}


def test_adaptive_plan_allows_schema_valid_structured_metadata() -> None:
    schema = json.loads(
        (ROOT / "src/etlantic/schemas/adaptive-pipeline-plan.schema.json").read_text(
            encoding="utf-8"
        )
    )
    document = _plan().to_dict()
    document["metadata"] = {"etlantic.rules": [{"name": "quality", "enabled": True}]}
    jsonschema.Draft202012Validator(schema).validate(document)

    restored = AdaptivePipelinePlan.from_dict(document, verify=False)

    assert restored.to_dict()["metadata"] == document["metadata"]


def test_target_descriptor_rejects_non_string_protocol_versions() -> None:
    with pytest.raises(ValueError, match="PMADP"):
        TargetDescriptor(
            target_id="local",
            identity="target-1",
            engine="local",
            protocol_versions={"compiler": 1},  # type: ignore[dict-item]
        )


def test_target_descriptor_rejects_non_json_capability_fingerprint() -> None:
    with pytest.raises(ValueError, match="PMADP"):
        TargetDescriptor(
            target_id="local",
            identity="target-1",
            engine="local",
            capability_fingerprint=object(),  # type: ignore[arg-type]
        )


def test_adaptive_plan_rejects_non_string_fingerprint_before_verification() -> None:
    document = _plan().to_dict()
    document["fingerprint"] = {"not": "a fingerprint"}

    with pytest.raises(ValueError, match="PMADP400"):
        AdaptivePipelinePlan.from_dict(document, verify=False)


def test_candidate_record_rejects_blank_identity_fields() -> None:
    with pytest.raises(ValueError, match="PMADP"):
        CandidateRecord(
            candidate_id="",
            node_name="raw",
            target_id="local",
            kind="source",
            status="eligible",
        )


def test_adaptive_external_consumer_rejected_before_compilation() -> None:
    with pytest.raises(ValueError, match="PMADP500"):
        _plan().compile(target="airflow")


def test_public_compile_rejects_adaptive_before_plugin_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_discovery(*args: object, **kwargs: object) -> object:
        raise AssertionError("orchestrator discovery must not run for /2")

    monkeypatch.setattr(
        "etlantic.orchestration.compile.discover_orchestrator_plugins",
        unexpected_discovery,
    )

    with pytest.raises(ValueError, match="PMADP500"):
        compile_plan(_plan(), target="airflow")  # type: ignore[arg-type]


def test_partial_adaptive_plan_rejects_unsliced_logical_graph() -> None:
    data = _plan().to_dict()
    data["selected_nodes"] = ["raw"]
    data["candidates"] = [
        candidate for candidate in data["candidates"] if candidate["node_name"] == "raw"
    ]
    data["decisions"] = [
        decision for decision in data["decisions"] if decision["node_name"] == "raw"
    ]
    data["regions"][0]["logical_nodes"] = ["raw"]
    data["physical_dag"]["units"][0]["logical_nodes"] = ["raw"]
    data["physical_dag"]["logical_to_physical"] = {"raw": "unit-1"}

    with pytest.raises(ValueError, match="PMADP403"):
        AdaptivePipelinePlan.from_dict(data, verify=False)


def test_partial_adaptive_plan_accepts_and_round_trips_sliced_logical_graph() -> None:
    data = _plan().to_dict()
    data["selected_nodes"] = ["raw"]
    data["logical_graph"] = _graph_to_dict(slice_graph(_plan().logical_graph, ("raw",)))
    data["candidates"] = [
        candidate for candidate in data["candidates"] if candidate["node_name"] == "raw"
    ]
    data["decisions"] = [
        decision for decision in data["decisions"] if decision["node_name"] == "raw"
    ]
    data["regions"][0]["logical_nodes"] = ["raw"]
    data["physical_dag"]["units"][0]["logical_nodes"] = ["raw"]
    data["physical_dag"]["logical_to_physical"] = {"raw": "unit-1"}

    partial = AdaptivePipelinePlan.from_dict(data, verify=False)
    partial = replace(partial, fingerprint=adaptive_plan_fingerprint(partial))
    restored = plan_from_json(plan_to_json(partial))

    assert restored.selected_nodes == ("raw",)
    assert restored.logical_graph.node_names() == ("raw",)


def test_physical_primary_mapping_must_match_compute_unit_attribution() -> None:
    with pytest.raises(ValueError, match="PMADP403"):
        PhysicalDAG(
            units=(
                PhysicalUnit(
                    identity="unit-raw",
                    kind="compute",
                    target_identity="target-1",
                    logical_nodes=("raw",),
                ),
                PhysicalUnit(
                    identity="unit-out",
                    kind="compute",
                    target_identity="target-1",
                    logical_nodes=("out",),
                ),
            ),
            logical_to_physical={"raw": "unit-out", "out": "unit-raw"},
            topological_order=("unit-raw", "unit-out"),
        )


def test_physical_primary_mapping_must_reference_compute_unit() -> None:
    with pytest.raises(ValueError, match="PMADP403"):
        PhysicalDAG(
            units=(
                PhysicalUnit(
                    identity="compute-raw",
                    kind="compute",
                    target_identity="target-1",
                    logical_nodes=("raw",),
                ),
                PhysicalUnit(
                    identity="publish-raw",
                    kind="publication",
                    target_identity="target-1",
                    logical_nodes=("raw",),
                ),
            ),
            logical_to_physical={"raw": "publish-raw"},
            topological_order=("compute-raw", "publish-raw"),
        )


def test_candidate_matrix_is_canonical_node_then_target_order() -> None:
    data = _plan().to_dict()
    data["candidates"] = list(reversed(data["candidates"]))

    restored = AdaptivePipelinePlan.from_dict(data, verify=False)

    assert [candidate.node_name for candidate in restored.candidates] == ["raw", "out"]


def test_candidate_matrix_rejects_duplicate_node_target_cell() -> None:
    data = _plan().to_dict()
    duplicate = {**data["candidates"][0], "candidate_id": "raw-local-duplicate"}
    data["candidates"].append(duplicate)
    data["decisions"][0]["candidate_id"] = duplicate["candidate_id"]

    with pytest.raises(ValueError, match="PMADP220"):
        AdaptivePipelinePlan.from_dict(data, verify=False)


def test_adaptive_region_rejects_non_boolean_fused_value() -> None:
    document = _plan().to_dict()
    document["regions"][0]["fused"] = "false"

    with pytest.raises(ValueError, match="PMADP400"):
        AdaptivePipelinePlan.from_dict(document, verify=False)


def test_adaptive_plan_rejects_unsupported_physical_protocol_version() -> None:
    document = _plan().to_dict()
    document["protocol_versions"]["physical_unit"] = "etlantic.physical_unit/999"

    with pytest.raises(ValueError, match="PMADP400"):
        AdaptivePipelinePlan.from_dict(document, verify=False)


def test_adaptive_plan_rejects_unknown_top_level_protocol_version() -> None:
    document = _plan().to_dict()
    document["protocol_versions"]["unexpected"] = "example.protocol/1"

    with pytest.raises(ValueError, match="PMADP400"):
        AdaptivePipelinePlan.from_dict(document, verify=False)


def test_adaptive_plan_rejects_non_array_objective() -> None:
    document = _plan().to_dict()
    document["objective"] = "latency"

    with pytest.raises(ValueError, match="PMADP"):
        AdaptivePipelinePlan.from_dict(document, verify=False)


def _set_target_evidence_refs_to_scalar(document: dict[str, Any]) -> None:
    document["inventory"]["targets"][0]["evidence_refs"] = "evidence-1"


def _set_physical_dependencies_to_object(document: dict[str, Any]) -> None:
    document["physical_dag"]["units"][0]["dependencies"] = {}


@pytest.mark.parametrize(
    "mutate",
    [_set_target_evidence_refs_to_scalar, _set_physical_dependencies_to_object],
)
def test_adaptive_plan_rejects_non_array_nested_fields(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    document = _plan().to_dict()
    mutate(document)

    with pytest.raises(ValueError, match="PMADP"):
        AdaptivePipelinePlan.from_dict(document, verify=False)


@pytest.mark.parametrize(
    "field, value",
    [
        ("logical_graph", {}),
        ("selected_nodes", []),
        ("selected_nodes", ["raw", "raw"]),
    ],
)
def test_adaptive_json_schema_rejects_model_invalid_documents(
    field: str, value: object
) -> None:
    schema = json.loads(
        (ROOT / "src/etlantic/schemas/adaptive-pipeline-plan.schema.json").read_text(
            encoding="utf-8"
        )
    )
    document = _plan().to_dict()
    document[field] = value

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(document)


def test_adaptive_json_schema_rejects_rejected_candidate_without_reason() -> None:
    schema = json.loads(
        (ROOT / "src/etlantic/schemas/adaptive-pipeline-plan.schema.json").read_text(
            encoding="utf-8"
        )
    )
    document = _plan().to_dict()
    document["candidates"][0]["status"] = "rejected"
    document["candidates"][0]["reason_codes"] = []

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(document)


def test_local_scheduler_rejects_adaptive_before_runtime_access() -> None:
    class RuntimeMustNotBeTouched:
        def __getattribute__(self, name: str) -> object:
            raise AssertionError(f"runtime access before /2 rejection: {name}")

    async def execute() -> None:
        await LocalScheduler().execute(
            _plan(),  # type: ignore[arg-type]
            request=RunRequest(),
            runtime=RuntimeMustNotBeTouched(),
            context=SchedulingContext(),
        )

    with pytest.raises(PipelineExecutionError, match="PMADP500") as excinfo:
        anyio.run(execute)
    assert excinfo.value.code == "PMADP500"
    assert excinfo.value.stage == "admission"
