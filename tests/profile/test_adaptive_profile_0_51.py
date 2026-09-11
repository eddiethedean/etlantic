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


def test_profile_updates_preserve_dormant_adaptive_fields() -> None:
    explicit = Profile(
        name="explicit",
        placement_targets={"dormant": PlacementTarget(engine="local")},
        eligible_targets=(),
    )

    updated = explicit.with_updates(timeout_seconds=17)
    assert "dormant" in updated.placement_targets
    assert updated.timeout_seconds == 17


def test_profile_updates_can_activate_dormant_adaptive_fields() -> None:
    explicit = Profile(
        name="explicit",
        placement_targets={"dormant": PlacementTarget(engine="local")},
        eligible_targets=(),
    )

    updated = explicit.with_updates(
        execution_strategy="adaptive", eligible_targets=("dormant",)
    )
    assert updated.execution_strategy == "adaptive"
    assert updated.eligible_targets == ("dormant",)
    assert "dormant" in updated.placement_targets


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("resource", "postgres://user:pass@host/db"),
        ("resource", "postgres://token@host/db"),
        ("location", "s3://AKIA:secret@bucket/path"),
        ("compiler", "token=resolved-secret"),
        ("executor", "Bearer resolved-secret"),
    ],
)
def test_target_scalar_references_reject_credentials(field: str, value: str) -> None:
    with pytest.raises(ValueError, match="PMADP101"):
        PlacementTarget(engine="local", **{field: value})


def test_target_from_dict_rejects_credential_url() -> None:
    with pytest.raises(ValueError, match="PMADP101"):
        PlacementTarget.from_dict(
            {"engine": "local", "resource": "postgres://user:pass@host/db"}
        )


def test_target_from_dict_rejects_camel_case_secret_key() -> None:
    with pytest.raises(ValueError, match="PMADP101"):
        PlacementTarget.from_dict(
            {"engine": "local", "version_constraints": {"clientSecret": "x"}}
        )


def test_placement_target_version_constraints_are_immutable() -> None:
    target = PlacementTarget(
        engine="local",
        version_constraints={"local-portable": ">=0.50"},
    )
    original_identity = target.identity()

    with pytest.raises(TypeError):
        target.version_constraints["local-portable"] = ">=0.51"

    assert target.identity() == original_identity


@pytest.mark.parametrize("field", ["execution_strategy", "adaptive_fallback"])
def test_profile_from_dict_rejects_null_adaptive_policy(field: str) -> None:
    with pytest.raises(ValueError, match="PMADP100"):
        Profile.from_dict(
            {"name": "invalid", "security_mode": "development", field: None}
        )


def test_profile_from_dict_rejects_string_eligible_targets() -> None:
    with pytest.raises(ValueError, match="PMADP102"):
        Profile.from_dict(
            {
                "name": "invalid",
                "security_mode": "development",
                "execution_strategy": "adaptive",
                "placement_targets": {"l": {"engine": "local"}},
                "eligible_targets": "l",
            }
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


@pytest.mark.parametrize(
    "unsupported_mode",
    [
        {"orchestrator": "airflow"},
        {"spark_streaming": True},
    ],
)
def test_profile_json_schema_rejects_unsupported_adaptive_modes(
    unsupported_mode: dict[str, object],
) -> None:
    schema = json.loads(
        (ROOT / "src/etlantic/schemas/profile.schema.json").read_text(encoding="utf-8")
    )
    document = {
        "name": "adaptive-local",
        "security_mode": "development",
        "execution_strategy": "adaptive",
        "placement_targets": {"local": {"engine": "local"}},
        "eligible_targets": ["local"],
        **unsupported_mode,
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(document)
