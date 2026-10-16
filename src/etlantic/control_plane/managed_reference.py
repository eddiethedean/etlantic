"""Bounded public reference to immutable, canonically accepted managed work."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from etlantic.control_plane.execution_envelope import ExecutionEnvelope
from etlantic.plan.model import PLAN_SCHEMA

MANAGED_REFERENCE_SCHEMA = "etlantic.managed_reference/1"
PREFECT_MANAGED_REFERENCE_SCHEMA = "etlantic.prefect.managed_reference/1"
_REFERENCE_SCHEMAS = frozenset(
    {MANAGED_REFERENCE_SCHEMA, PREFECT_MANAGED_REFERENCE_SCHEMA}
)
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_MAX_REFERENCE_BYTES = 4096


@dataclass(frozen=True, slots=True)
class AcceptedExecutionReference:
    """Locator and content digests for one already accepted submission.

    This value carries no plan, credentials, parameters, or source data. The
    legacy Prefect schema remains accepted for installed deployments.
    """

    submission_id: str
    plan_fingerprint: str
    envelope_sha256: str
    schema: str = MANAGED_REFERENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema not in _REFERENCE_SCHEMAS:
            raise ValueError("unsupported managed execution reference schema")
        submission_id: object = cast(object, self.submission_id)
        if not isinstance(submission_id, str) or not submission_id.strip():
            raise ValueError("submission_id must be a non-empty string")
        if len(self.submission_id) > 512:
            raise ValueError("submission_id must contain at most 512 characters")
        if _FINGERPRINT.fullmatch(self.plan_fingerprint) is None:
            raise ValueError("plan_fingerprint must be a lowercase SHA-256 value")
        if _FINGERPRINT.fullmatch(self.envelope_sha256) is None:
            raise ValueError("envelope_sha256 must be a lowercase SHA-256 value")

    @classmethod
    def from_submission(
        cls, submission: Any, *, schema: str = MANAGED_REFERENCE_SCHEMA
    ) -> AcceptedExecutionReference:
        """Bind the reference to the accepted canonical execution envelope."""
        snapshot = getattr(submission, "input_snapshot", None)
        if not isinstance(snapshot, str) or not snapshot:
            raise ValueError("accepted submission has no immutable execution envelope")
        envelope = ExecutionEnvelope.from_json(snapshot)
        if envelope.plan_document.get("schema") != PLAN_SCHEMA:
            raise ValueError("managed worker supports only etlantic.plan/1")
        if envelope.plan_fingerprint != submission.plan_fingerprint:
            raise ValueError("accepted plan fingerprint does not match its envelope")
        return cls(
            submission_id=str(submission.submission_id),
            plan_fingerprint=str(submission.plan_fingerprint),
            envelope_sha256=hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
            schema=schema,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "submission_id": self.submission_id,
            "plan_fingerprint": self.plan_fingerprint,
            "envelope_sha256": self.envelope_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AcceptedExecutionReference:
        if set(value) != {
            "schema",
            "submission_id",
            "plan_fingerprint",
            "envelope_sha256",
        }:
            raise ValueError(
                "managed execution reference has unknown or missing fields"
            )
        try:
            encoded = json.dumps(
                dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("managed execution reference must be JSON data") from exc
        if len(encoded) > _MAX_REFERENCE_BYTES:
            raise ValueError("managed execution reference exceeds its size limit")
        schema = value.get("schema")
        submission_id = value.get("submission_id")
        plan_fingerprint = value.get("plan_fingerprint")
        envelope_sha256 = value.get("envelope_sha256")
        if not all(
            isinstance(item, str)
            for item in (schema, submission_id, plan_fingerprint, envelope_sha256)
        ):
            raise ValueError("managed execution reference fields must be strings")
        return cls(
            schema=cast(str, schema),
            submission_id=cast(str, submission_id),
            plan_fingerprint=cast(str, plan_fingerprint),
            envelope_sha256=cast(str, envelope_sha256),
        )


__all__ = [
    "MANAGED_REFERENCE_SCHEMA",
    "PREFECT_MANAGED_REFERENCE_SCHEMA",
    "AcceptedExecutionReference",
]
