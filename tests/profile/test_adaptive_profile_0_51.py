"""0.51 adaptive profile contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etlantic import Data, Extract, Load, Pipeline
from etlantic.exceptions import PipelineValidationError
from etlantic.profile import PlacementTarget, Profile

jsonschema = pytest.importorskip("jsonschema")

ROOT = Path(__file__).resolve().parents[2]


class Row(Data):
    id: int


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    out: Load[Row] = Load(input=raw, asset="out")


def _adaptive() -> Profile:
    return Profile(
        name="adaptive-local",
        execution_strategy="adaptive",
        portable_transform_policy="require",
        placement_targets={
            "local": PlacementTarget(
                engine="local",
                compiler="local-portable",
                required_capabilities=("batch",),
            )
        },
        eligible_targets=("local",),
    )


def test_adaptive_profile_round_trip_and_target_identity() -> None:
    profile = _adaptive()
    restored = Profile.from_dict(json.loads(json.dumps(profile.to_dict())))
    assert restored == profile
    assert (
        restored.placement_targets["local"].identity()
        == profile.placement_targets["local"].identity()
    )


def test_explicit_plan_snapshot_omits_dormant_adaptive_policy() -> None:
    explicit = Profile(
        name="explicit",
        placement_targets={"dormant": PlacementTarget(engine="local")},
        eligible_targets=(),
    )
    snapshot = explicit.to_plan_snapshot()
    assert not set(snapshot) & {
        "execution_strategy",
        "placement_targets",
        "eligible_targets",
        "adaptive_fallback",
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"execution_strategy": "other"},
        {"adaptive_fallback": "other"},
        {"execution_strategy": "adaptive"},
        {
            "execution_strategy": "adaptive",
            "placement_targets": {"a": {"engine": "local", "unknown": True}},
            "eligible_targets": ("a",),
        },
        {
            "execution_strategy": "adaptive",
            "placement_targets": {"a": {"engine": "local"}},
            "eligible_targets": ("missing",),
        },
    ],
)
def test_invalid_adaptive_profile_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="PMADP"):
        Profile(name="invalid", **kwargs)  # type: ignore[arg-type]


def test_target_secret_like_field_rejected() -> None:
    with pytest.raises(ValueError, match="PMADP101"):
        PlacementTarget.from_dict(
            {"engine": "local", "version_constraints": {"api_token": "x"}}
        )


def test_adaptive_planning_fails_closed_until_solver_gate() -> None:
    with pytest.raises(PipelineValidationError, match="PMADP221"):
        Sample.plan(profile=_adaptive())


@pytest.mark.parametrize(
    "target, eligible",
    [
        ({"engine": "local", "compiler": ""}, ["local"]),
        ({"engine": "local"}, ["local", "local"]),
    ],
)
def test_profile_json_schema_rejects_python_invalid_adaptive_forms(
    target: dict[str, object], eligible: list[str]
) -> None:
    schema = json.loads(
        (ROOT / "src/etlantic/schemas/profile.schema.json").read_text(encoding="utf-8")
    )
    document = {
        "name": "adaptive-local",
        "security_mode": "development",
        "execution_strategy": "adaptive",
        "placement_targets": {"local": target},
        "eligible_targets": eligible,
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(document)
