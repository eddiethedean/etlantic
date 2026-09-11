"""Adaptive placement planner behavior for 0.52."""

from __future__ import annotations

import hashlib

import anyio
import pytest

from etlantic import Data, Extract, Load, Pipeline
from etlantic.exceptions import PipelineExecutionError, PipelineValidationError
from etlantic.plan import (
    AdaptivePipelinePlan,
    explain_plan,
    plan_from_json,
    plan_pipeline,
    plan_pipeline_with_report,
    plan_to_json,
)
from etlantic.profile import PlacementTarget, Profile
from etlantic.registry import PlanningContext, PluginDescriptor, builtin_stub_registry
from etlantic.runtime.execute import arun_pipeline


class Row(Data):
    id: int


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    out: Load[Row] = Load(input=raw, asset="out")


def adaptive_profile(**kwargs: object) -> Profile:
    values: dict[str, object] = {
        "name": "adaptive-local",
        "execution_strategy": "adaptive",
        "portable_transform_policy": "require",
        "placement_targets": {
            "local": PlacementTarget(engine="local"),
        },
        "eligible_targets": ("local",),
    }
    values.update(kwargs)
    return Profile(**values)  # type: ignore[arg-type]


def test_adaptive_plan_is_verified_and_explainable() -> None:
    plan = plan_pipeline(Sample, profile=adaptive_profile())
    assert isinstance(plan, AdaptivePipelinePlan)
    assert plan.schema == "etlantic.plan/2"
    assert plan.plan_id == f"plan:{plan.fingerprint[:16]}"
    assert plan_from_json(plan_to_json(plan)).to_dict() == plan.to_dict()
    explanation = explain_plan(plan)
    assert explanation["planning_only"] is True
    assert len(explanation["decisions"]) == 2


def test_adaptive_report_path_uses_same_plan_dispatch() -> None:
    plan, report = plan_pipeline_with_report(Sample, profile=adaptive_profile())
    assert report.valid
    assert isinstance(plan, AdaptivePipelinePlan)


def test_adaptive_execution_rejects_before_runtime() -> None:
    async def run() -> None:
        with pytest.raises(PipelineExecutionError, match="PMADP500"):
            await arun_pipeline(Sample, profile=adaptive_profile())

    anyio.run(run)


def test_adaptive_cross_target_requires_directional_handoff_evidence() -> None:
    profile = adaptive_profile(
        placement_targets={
            "producer": PlacementTarget(engine="local"),
            "consumer": PlacementTarget(engine="null"),
        },
        eligible_targets=("producer", "consumer"),
        implementation_overrides={"raw": "producer", "out": "consumer"},
    )
    with pytest.raises(PipelineValidationError, match="PMADP320"):
        plan_pipeline(Sample, profile=profile)


def test_adaptive_cross_target_accepts_fully_bound_content_evidence() -> None:
    from etlantic.planning.adaptive import _handoff_contract

    targets = {
        "producer": PlacementTarget(engine="local"),
        "consumer": PlacementTarget(engine="null"),
    }
    profile = adaptive_profile(
        placement_targets=targets,
        eligible_targets=("producer", "consumer"),
        implementation_overrides={"raw": "producer", "out": "consumer"},
    )
    context = PlanningContext.create(profile, registry=builtin_stub_registry())
    edge = Sample.build_graph().edges[0]
    evidence = _handoff_contract(
        targets["producer"], targets["consumer"], edge, context
    )
    evidence["evidence_ref"] = f"sha256:{hashlib.sha256(b'handoff').hexdigest()}"
    context.registry.register_plugin(
        PluginDescriptor(
            name="verified-handoff",
            kind="handoff",
            version="1",
            metadata={"handoff_evidence": [evidence]},
        )
    )

    plan = plan_pipeline(Sample, context=context)
    transfers = [unit for unit in plan.physical_dag.units if unit.kind == "transfer"]
    assert len(transfers) == 1
    expected_contract = {
        key: value for key, value in evidence.items() if key != "evidence_ref"
    }
    assert dict(transfers[0].metadata["etlantic.handoff_contract"]) == expected_contract


def test_adaptive_artifacts_redact_absolute_target_resources() -> None:
    profile = adaptive_profile(
        placement_targets={
            "local": PlacementTarget(
                engine="local", resource="/private/etlantic/provider"
            )
        }
    )
    plan = plan_pipeline(Sample, profile=profile)
    assert "/private/etlantic/provider" not in plan_to_json(plan)
