"""PipelinePlan serialization round-trip tests."""

from __future__ import annotations

import json

import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PlanningContext,
    Transformation,
)
from etlantic.plan import plan_from_json, plan_pipeline, plan_to_json
from etlantic.profile import Profile
from etlantic.registry import BindingDescriptor, builtin_stub_registry
from etlantic.secrets import SecretRef


class Row(Data):
    id: int


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")


def test_secret_ref_round_trip_on_binding() -> None:
    registry = builtin_stub_registry()
    registry.register_binding(
        BindingDescriptor(
            binding="rows",
            provider="memory",
            kind="source",
            secret_ref=SecretRef(provider="env-secrets", name="rows", key="token"),
        )
    )
    profile = Profile(name="sec", assets={"out": "memory"})
    plan = plan_pipeline(
        Sample,
        context=PlanningContext.create(profile=profile, registry=registry),
    )
    assert plan.bindings["raw"].secret_ref is not None
    restored = plan_from_json(plan_to_json(plan))
    assert restored.bindings["raw"].secret_ref is not None
    assert restored.bindings["raw"].secret_ref.key == "token"


def test_plan_from_json_verify_optional() -> None:
    plan = plan_pipeline(Sample, profile="local")
    data = json.loads(plan_to_json(plan))
    data["fingerprint"] = "deadbeef" * 8
    # verify=False accepts tampered fingerprint
    restored = plan_from_json(json.dumps(data), verify=False)
    assert restored.fingerprint == "deadbeef" * 8
    with pytest.raises(ValueError):
        plan_from_json(json.dumps(data), verify=True)
