"""Closed adaptive /2 wire-model tests."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from etlantic import Data, Extract, Load, Pipeline
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
    with pytest.raises(ValueError, match="fingerprint mismatch"):
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


def test_adaptive_external_consumer_rejected_before_compilation() -> None:
    with pytest.raises(ValueError, match="PMADP500"):
        _plan().compile(target="airflow")
