from __future__ import annotations

import pytest

from etlantic.runtime.request import (
    InvalidationMode,
    MaterializationPolicy,
    RetryPolicy,
    RunIntent,
    RunRequest,
    RunSelection,
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
    )

    restored = RunRequest.from_dict(request.to_dict())

    assert restored.to_dict() == request.to_dict()


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
