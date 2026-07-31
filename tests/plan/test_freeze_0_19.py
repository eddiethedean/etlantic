"""Plan deep-freeze and fingerprint verification (0.19 WP-I / WP-J)."""

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
    Transformation,
)
from etlantic.plan import (
    deep_freeze,
    plan_from_json,
    plan_pipeline,
    plan_to_json,
    verify_plan_fingerprint,
)
from etlantic.plan.freeze import immutable_mapping


class Row(Data):
    id: int


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("local")
def identity_local(rows: list[Row]) -> list[Row]:
    return list(rows)


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")


def test_deep_freeze_nested_dict_immutable() -> None:
    frozen = deep_freeze({"a": {"b": [1, {"c": 2}]}})
    with pytest.raises(TypeError):
        frozen["a"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        frozen["a"]["b"] = []  # type: ignore[index]
    assert frozen["a"]["b"][1]["c"] == 2
    mapped = immutable_mapping({"x": [1, 2]})
    with pytest.raises(TypeError):
        mapped["x"] = [3]  # type: ignore[index]


def test_verify_plan_fingerprint_rejects_tampered() -> None:
    plan = plan_pipeline(Sample, profile="local")
    data = plan.to_dict()
    data["fingerprint"] = "deadbeef" * 8
    tampered = plan.__class__.from_dict(data, verify=False)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        verify_plan_fingerprint(tampered)


def test_plan_from_json_still_verifies() -> None:
    plan = plan_pipeline(Sample, profile="local")
    data = json.loads(plan_to_json(plan))
    data["fingerprint"] = "deadbeef" * 8
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        plan_from_json(json.dumps(data), verify=True)
    restored = plan_from_json(json.dumps(data), verify=False)
    assert restored.fingerprint == "deadbeef" * 8
