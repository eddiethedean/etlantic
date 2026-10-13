"""Versioned external schedule-trigger values.

These values contain opaque references and timestamps only. Authentication and
scope come from the trusted request context supplied by a transport adapter.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.schedule_models import FiringStatus

TRIGGER_ENVELOPE_SCHEMA = "etlantic.trigger_envelope/1"
TRIGGER_RECEIPT_SCHEMA = "etlantic.trigger_receipt/1"
MAX_TRIGGER_ENVELOPE_BYTES = 16 * 1024
MAX_TRIGGER_FUTURE_SKEW_SECONDS = 60
_ENVELOPE_FIELDS = frozenset(
    {
        "schema",
        "schedule_id",
        "schedule_revision_id",
        "timer_owner_generation",
        "occurrence_id",
        "scheduled_at",
        "delivery_attempt_id",
        "correlation_id",
    }
)
_ENVELOPE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": sorted(_ENVELOPE_FIELDS),
    "properties": {
        "schema": {"const": TRIGGER_ENVELOPE_SCHEMA},
        "schedule_id": {"type": "string", "minLength": 1, "maxLength": 512},
        "schedule_revision_id": {
            "type": "string",
            "minLength": 1,
            "maxLength": 512,
        },
        "timer_owner_generation": {"type": "integer", "minimum": 1},
        "occurrence_id": {
            "type": "string",
            "pattern": r"^occ-[0-9a-f]{64}$",
            "minLength": 68,
            "maxLength": 68,
        },
        "scheduled_at": {
            "type": "string",
            "format": "date-time",
            "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$",
        },
        "delivery_attempt_id": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256,
        },
        "correlation_id": {"type": "string", "minLength": 1, "maxLength": 256},
    },
}


def trigger_envelope_json_schema() -> dict[str, Any]:
    """Return the wire schema used by OpenAPI and generated consumers."""
    return json.loads(json.dumps(_ENVELOPE_JSON_SCHEMA))


def _unique_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("trigger envelope contains a duplicate field")
        result[key] = value
    return result


def external_occurrence_id(
    schedule_id: str, schedule_revision_id: str, scheduled_at: str
) -> str:
    """Derive a stable occurrence identity from its registered schedule slot."""
    semantic = json.dumps(
        [schedule_id, schedule_revision_id, scheduled_at],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "occ-" + hashlib.sha256(semantic.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class TriggerEnvelope:
    """Bounded request to admit one registered schedule occurrence."""

    schedule_id: str
    schedule_revision_id: str
    timer_owner_generation: int
    occurrence_id: str
    scheduled_at: str
    delivery_attempt_id: str
    correlation_id: str

    def __post_init__(self) -> None:
        for name in (
            "schedule_id",
            "schedule_revision_id",
            "occurrence_id",
            "scheduled_at",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 512:
                raise ValueError(f"{name} must contain 1 to 512 characters")
        if (
            type(self.timer_owner_generation) is not int
            or self.timer_owner_generation < 1
        ):
            raise ValueError("timer_owner_generation must be a positive integer")
        for name in ("delivery_attempt_id", "correlation_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{name} must contain 1 to 256 characters")
        try:
            scheduled = datetime.fromisoformat(self.scheduled_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("scheduled_at must be an ISO-8601 timestamp") from exc
        if scheduled.tzinfo is None or scheduled.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone")
        canonical = scheduled.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if self.scheduled_at != canonical:
            raise ValueError("scheduled_at must use canonical UTC ISO-8601 form")
        expected = external_occurrence_id(
            self.schedule_id, self.schedule_revision_id, self.scheduled_at
        )
        if self.occurrence_id != expected:
            raise ValueError(
                "occurrence_id does not match the registered schedule slot"
            )
        encoded_size = len(
            json.dumps(
                self.to_dict(),
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        )
        if encoded_size > MAX_TRIGGER_ENVELOPE_BYTES:
            raise ValueError("trigger envelope exceeds the size limit")

    @property
    def semantic_fingerprint(self) -> str:
        """Fingerprint stable intent; delivery and correlation IDs are excluded."""
        body = json.dumps(
            {
                "schema": TRIGGER_ENVELOPE_SCHEMA,
                "schedule_id": self.schedule_id,
                "schedule_revision_id": self.schedule_revision_id,
                "occurrence_id": self.occurrence_id,
                "scheduled_at": self.scheduled_at,
            },
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TRIGGER_ENVELOPE_SCHEMA,
            "schedule_id": self.schedule_id,
            "schedule_revision_id": self.schedule_revision_id,
            "timer_owner_generation": self.timer_owner_generation,
            "occurrence_id": self.occurrence_id,
            "scheduled_at": self.scheduled_at,
            "delivery_attempt_id": self.delivery_attempt_id,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TriggerEnvelope:
        if data.get("schema") != TRIGGER_ENVELOPE_SCHEMA:
            raise ControlPlaneError(
                "Unsupported trigger envelope version",
                code="PMTRG400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if frozenset(data) != _ENVELOPE_FIELDS:
            raise ControlPlaneError(
                "Trigger envelope fields are missing or unsupported",
                code="PMTRG400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        try:
            return cls(
                schedule_id=data["schedule_id"],
                schedule_revision_id=data["schedule_revision_id"],
                timer_owner_generation=data["timer_owner_generation"],
                occurrence_id=data["occurrence_id"],
                scheduled_at=data["scheduled_at"],
                delivery_attempt_id=data["delivery_attempt_id"],
                correlation_id=data["correlation_id"],
            )
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "Trigger envelope is malformed",
                code="PMTRG400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            ) from exc

    @classmethod
    def from_json(cls, body: bytes | str) -> TriggerEnvelope:
        """Decode a bounded UTF-8 JSON body before any scoped receipt lookup."""
        try:
            body_value = cast(object, body)
            raw_value: object = (
                body_value.encode("utf-8")
                if isinstance(body_value, str)
                else body_value
            )
        except UnicodeEncodeError as exc:
            raise ControlPlaneError(
                "Trigger envelope must be UTF-8 JSON",
                code="PMTRG400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            ) from exc
        if not isinstance(raw_value, bytes):
            raise ControlPlaneError(
                "Trigger envelope must be UTF-8 JSON",
                code="PMTRG400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        raw = raw_value
        if len(raw) > MAX_TRIGGER_ENVELOPE_BYTES:
            raise ControlPlaneError(
                "Trigger envelope exceeds the size limit",
                code="PMTRG413",
                status=413,
                title="Payload Too Large",
                type="etlantic.control_plane/payload_too_large",
            )
        try:
            data = json.loads(
                raw.decode("utf-8"), object_pairs_hook=_unique_object_pairs
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
            RecursionError,
        ) as exc:
            raise ControlPlaneError(
                "Trigger envelope must be UTF-8 JSON",
                code="PMTRG400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            ) from exc
        if not isinstance(data, Mapping):
            raise ControlPlaneError(
                "Trigger envelope must be a JSON object",
                code="PMTRG400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        return cls.from_dict(cast(Mapping[str, Any], data))


@dataclass(frozen=True, slots=True)
class TriggerReceipt:
    """Safe result of trigger delivery, separate from ETL completion."""

    status: Literal["pending", "accepted", "skipped"]
    firing_status: FiringStatus
    schedule_id: str
    schedule_revision_id: str
    occurrence_id: str
    submission_id: str | None = None
    run_id: str | None = None
    status_reference: str | None = None
    duplicate: bool = False

    def __post_init__(self) -> None:
        if self.status not in ("pending", "accepted", "skipped"):
            raise ValueError("trigger receipt status is unsupported")
        if self.firing_status not in (
            "accepted",
            "skipped_overlap",
            "skipped_misfire",
            "skipped_window",
            "failed_preparation",
        ):
            raise ValueError("trigger receipt firing_status is unsupported")
        if (self.status == "skipped") != (self.firing_status != "accepted"):
            raise ValueError("trigger receipt status conflicts with firing_status")
        if (self.status == "pending") != (
            self.firing_status == "accepted" and self.submission_id is None
        ):
            raise ValueError("trigger receipt status conflicts with submission_id")
        if self.status == "accepted" and self.submission_id is None:
            raise ValueError("accepted trigger receipt requires a submission_id")
        for name in (
            "schedule_id",
            "schedule_revision_id",
            "occurrence_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"trigger receipt {name} must be non-empty")
        for name in ("submission_id", "run_id", "status_reference"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"trigger receipt {name} must be non-empty when set")
        if type(self.duplicate) is not bool:
            raise ValueError("trigger receipt duplicate must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TRIGGER_RECEIPT_SCHEMA,
            "status": self.status,
            "firing_status": self.firing_status,
            "schedule_id": self.schedule_id,
            "schedule_revision_id": self.schedule_revision_id,
            "occurrence_id": self.occurrence_id,
            "submission_id": self.submission_id,
            "run_id": self.run_id,
            "status_reference": self.status_reference,
            "duplicate": self.duplicate,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TriggerReceipt:
        expected = {
            "schema",
            "status",
            "firing_status",
            "schedule_id",
            "schedule_revision_id",
            "occurrence_id",
            "submission_id",
            "run_id",
            "status_reference",
            "duplicate",
        }
        if data.get("schema") != TRIGGER_RECEIPT_SCHEMA or set(data) != expected:
            raise ControlPlaneError(
                "Trigger receipt version or fields are unsupported",
                code="PMTRG502",
                status=502,
                title="Bad Gateway",
                type="etlantic.control_plane/invalid_upstream_response",
            )
        try:
            return cls(
                status=data["status"],
                firing_status=data["firing_status"],
                schedule_id=data["schedule_id"],
                schedule_revision_id=data["schedule_revision_id"],
                occurrence_id=data["occurrence_id"],
                submission_id=data["submission_id"],
                run_id=data["run_id"],
                status_reference=data["status_reference"],
                duplicate=data["duplicate"],
            )
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "Trigger receipt is malformed",
                code="PMTRG502",
                status=502,
                title="Bad Gateway",
                type="etlantic.control_plane/invalid_upstream_response",
            ) from exc


__all__ = [
    "MAX_TRIGGER_ENVELOPE_BYTES",
    "MAX_TRIGGER_FUTURE_SKEW_SECONDS",
    "TRIGGER_ENVELOPE_SCHEMA",
    "TRIGGER_RECEIPT_SCHEMA",
    "TriggerEnvelope",
    "TriggerReceipt",
    "external_occurrence_id",
    "trigger_envelope_json_schema",
]
