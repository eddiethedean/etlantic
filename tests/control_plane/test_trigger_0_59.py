"""Wire contract coverage for external schedule triggers in 0.59."""

from __future__ import annotations

import json

import pytest

from etlantic.control_plane import (
    MAX_TRIGGER_ENVELOPE_BYTES,
    TRIGGER_ENVELOPE_SCHEMA,
    ControlPlaneError,
    TriggerEnvelope,
    TriggerReceipt,
    external_occurrence_id,
)


def _payload(**overrides: object) -> dict[str, object]:
    schedule_id = "nightly-refresh"
    revision_id = "revision-7"
    scheduled_at = "2026-10-01T14:00:00Z"
    return {
        "schema": TRIGGER_ENVELOPE_SCHEMA,
        "schedule_id": schedule_id,
        "schedule_revision_id": revision_id,
        "timer_owner_generation": 3,
        "occurrence_id": external_occurrence_id(schedule_id, revision_id, scheduled_at),
        "scheduled_at": scheduled_at,
        "delivery_attempt_id": "attempt-1",
        "correlation_id": "corr-1",
        **overrides,
    }


def test_envelope_round_trip_and_semantic_fingerprint_ignore_delivery_ids() -> None:
    first = TriggerEnvelope.from_json(json.dumps(_payload()))
    retry = TriggerEnvelope.from_dict(
        _payload(delivery_attempt_id="attempt-2", correlation_id="corr-2")
    )

    assert TriggerEnvelope.from_dict(first.to_dict()) == first
    assert first.occurrence_id == retry.occurrence_id
    assert first.semantic_fingerprint == retry.semantic_fingerprint


@pytest.mark.parametrize(
    "mutation",
    [
        "version",
        "unknown_field",
        "missing_field",
        "boolean_generation",
        "noncanonical_time",
        "mismatched_occurrence",
    ],
)
def test_malformed_or_unsupported_envelopes_fail_closed(
    mutation: str,
) -> None:
    payload = _payload()
    if mutation == "version":
        payload["schema"] = "etlantic.trigger_envelope/2"
    elif mutation == "unknown_field":
        payload["unregistered_field"] = "not allowed"
    elif mutation == "missing_field":
        payload.pop("correlation_id")
    elif mutation == "boolean_generation":
        payload["timer_owner_generation"] = True
    elif mutation == "noncanonical_time":
        payload["scheduled_at"] = "2026-10-01T14:00:00-04:00"
        payload["occurrence_id"] = external_occurrence_id(
            "nightly-refresh", "revision-7", "2026-10-01T18:00:00Z"
        )
    else:
        payload["occurrence_id"] = "occ-" + "0" * 64

    with pytest.raises(ControlPlaneError) as error:
        TriggerEnvelope.from_dict(payload)

    assert error.value.status == 400
    assert error.value.code == "PMTRG400"


def test_json_rejects_duplicate_keys_and_oversized_bodies() -> None:
    encoded = json.dumps(_payload())
    duplicate = encoded[:-1] + ',"schedule_id":"second"}'

    with pytest.raises(ControlPlaneError) as duplicate_error:
        TriggerEnvelope.from_json(duplicate)
    assert duplicate_error.value.code == "PMTRG400"

    with pytest.raises(ControlPlaneError) as size_error:
        TriggerEnvelope.from_json(b" " * (MAX_TRIGGER_ENVELOPE_BYTES + 1))
    assert size_error.value.status == 413
    assert size_error.value.code == "PMTRG413"


@pytest.mark.parametrize(
    "receipt",
    [
        TriggerReceipt(
            status="accepted",
            firing_status="accepted",
            schedule_id="nightly-refresh",
            schedule_revision_id="revision-7",
            occurrence_id="occ-" + "1" * 64,
            submission_id="submission-1",
            run_id="run-1",
            status_reference="/v1/schedules/nightly-refresh/occurrences/occ",
        ),
        TriggerReceipt(
            status="pending",
            firing_status="accepted",
            schedule_id="nightly-refresh",
            schedule_revision_id="revision-7",
            occurrence_id="occ-" + "2" * 64,
        ),
        TriggerReceipt(
            status="skipped",
            firing_status="skipped_overlap",
            schedule_id="nightly-refresh",
            schedule_revision_id="revision-7",
            occurrence_id="occ-" + "3" * 64,
            duplicate=True,
        ),
    ],
)
def test_trigger_receipt_round_trip_preserves_transport_status(
    receipt: TriggerReceipt,
) -> None:
    assert TriggerReceipt.from_dict(receipt.to_dict()) == receipt


def test_receipt_rejects_conflicting_status_and_firing_state() -> None:
    payload = TriggerReceipt(
        status="accepted",
        firing_status="accepted",
        schedule_id="nightly-refresh",
        schedule_revision_id="revision-7",
        occurrence_id="occ-" + "4" * 64,
        submission_id="submission-4",
    ).to_dict()
    payload["firing_status"] = "skipped_overlap"

    with pytest.raises(ControlPlaneError) as error:
        TriggerReceipt.from_dict(payload)

    assert error.value.status == 502
    assert error.value.code == "PMTRG502"
