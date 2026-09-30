from __future__ import annotations

import pytest

from etlantic.runtime.request import (
    InvalidationMode,
    MaterializationPolicy,
    RetryPolicy,
    RunIntent,
    RunRequest,
    RunSelection,
    TimeoutPolicy,
    request_setting_provenance,
    resolve_request_policies,
)


def test_run_request_wire_round_trip_preserves_all_controls() -> None:
    request = RunRequest(
        selection=RunSelection.between("extract", "load"),
        intent=RunIntent.INCREMENTAL,
        materialization=MaterializationPolicy.DURABLE,
        retry=RetryPolicy(max_attempts=4, backoff_seconds=0.5, retry_on=("timeout",)),
        parameter_overrides={"transform": {"cutoff": "2026-01-01"}},
        asset_overrides={"extract": "source-v2"},
        implementation_overrides={"normalize": "duckdb"},
        invalidation=InvalidationMode.DOWNSTREAM,
        metadata={"request_source": "api"},
        extensions={"plugin:example/limits": {"window": 12}},
    )

    restored = RunRequest.from_dict(request.to_dict())

    assert restored.to_dict() == request.to_dict()
    assert restored.extensions == request.extensions
    assert restored.explicit_settings == request.explicit_settings


def test_run_request_wire_rejects_unknown_semantics() -> None:
    with pytest.raises(ValueError, match="Unknown run-request field"):
        RunRequest.from_dict({"future_control": True})

    with pytest.raises(ValueError, match="Unknown retry field"):
        RunRequest.from_dict({"retry": {"retry_everything": True}})


def test_run_request_wire_rejects_malformed_overrides() -> None:
    with pytest.raises(
        TypeError, match="parameter_overrides must map strings to objects"
    ):
        RunRequest.from_dict({"parameter_overrides": {"node": "not-an-object"}})

    with pytest.raises(TypeError, match="asset_overrides must map strings to strings"):
        RunRequest.from_dict({"asset_overrides": {"node": 3}})


def test_run_request_extensions_require_namespaces_and_secret_free_json() -> None:
    with pytest.raises(ValueError, match="namespaces"):
        RunRequest(extensions={"vendor_option": True})

    with pytest.raises(ValueError, match="secret"):
        RunRequest(extensions={"plugin:example/auth": {"api_key": "hidden"}})


def test_run_request_isolates_nested_input_and_export_mappings() -> None:
    parameters = {"transform": {"cutoff": [1, 2]}}
    extensions = {"etlantic.sample": {"flags": ["fast"]}}
    request = RunRequest(parameter_overrides=parameters, extensions=extensions)

    parameters["transform"]["cutoff"].append(3)
    extensions["etlantic.sample"]["flags"].append("unsafe")
    assert request.parameter_overrides["transform"]["cutoff"] == [1, 2]
    assert request.extensions["etlantic.sample"]["flags"] == ("fast",)

    wire = request.to_dict()
    wire["parameter_overrides"]["transform"]["cutoff"].append(4)
    wire["extensions"]["etlantic.sample"]["flags"].append("changed")
    assert request.parameter_overrides["transform"]["cutoff"] == [1, 2]
    assert request.extensions["etlantic.sample"]["flags"] == ("fast",)


def test_run_request_rejects_unknown_constructor_arguments() -> None:
    with pytest.raises(TypeError, match="unexpected keyword"):
        RunRequest(future_option=True)


def test_request_policy_precedence_records_explicit_default_values() -> None:
    settings = {
        "retry_max_attempts": 5,
        "retry_backoff_seconds": 3.5,
        "timeout_seconds": 120,
        "step_timeout_seconds": 15,
    }
    inherited = RunRequest()
    effective = resolve_request_policies(inherited, settings)
    assert effective.retry == RetryPolicy(max_attempts=5, backoff_seconds=3.5)
    assert effective.timeout == TimeoutPolicy(run_seconds=120, step_seconds=15)

    explicit_defaults = RunRequest(retry=RetryPolicy(), timeout=TimeoutPolicy())
    explicit_effective = resolve_request_policies(explicit_defaults, settings)
    assert explicit_effective.retry == RetryPolicy()
    assert explicit_effective.timeout == TimeoutPolicy()
    assert explicit_effective.explicit_settings == frozenset(
        {
            "retry.max_attempts",
            "retry.backoff_seconds",
            "retry.retry_on",
            "timeout.run_seconds",
            "timeout.step_seconds",
        }
    )

    restored = RunRequest.from_dict(explicit_defaults.to_dict())
    assert resolve_request_policies(restored, settings).to_dict() == (
        explicit_effective.to_dict()
    )
    provenance = request_setting_provenance(
        restored, settings, profile_name="qualified"
    )
    assert provenance["request.retry.max_attempts"] == "request"
    assert provenance["request.timeout.run_seconds"] == "request"


def test_legacy_request_wire_infers_only_non_default_policy_overrides() -> None:
    legacy = RunRequest.from_dict(
        {"retry": {"max_attempts": 4, "backoff_seconds": 0.0}}
    )
    assert legacy.explicit_settings == frozenset({"retry.max_attempts"})
