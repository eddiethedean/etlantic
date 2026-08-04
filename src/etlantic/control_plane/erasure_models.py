"""Governed erasure models (CP4) — no subject values in evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)

ERASURE_REQUEST_SCHEMA = "etlantic.control_plane.erasure_request/1"
ERASURE_PLAN_SCHEMA = "etlantic.control_plane.erasure_plan/1"
ERASURE_REPORT_SCHEMA = "etlantic.control_plane.erasure_report/1"

ErasureAction = Literal["delete", "anonymize", "lookup", "proof", "retry"]
ErasureStatus = Literal[
    "pending",
    "planned",
    "in_progress",
    "completed",
    "partial",
    "blocked",
    "unsupported",
    "failed",
]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ErasureRequest:
    """Subject-key / field lineage request — never stores subject values."""

    request_id: str
    tenant_id: str
    workspace_id: str
    subject_key_fingerprint: str
    field_paths: tuple[str, ...]
    legal_hold: bool = False
    status: ErasureStatus = "pending"
    created_at: datetime = field(default_factory=_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ERASURE_REQUEST_SCHEMA,
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "subject_key_fingerprint": self.subject_key_fingerprint,
            "field_paths": list(self.field_paths),
            "legal_hold": self.legal_hold,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }


@dataclass(frozen=True, slots=True)
class ErasurePlanStep:
    step_id: str
    provider_id: str
    action: ErasureAction
    field_paths: tuple[str, ...]
    supported: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "provider_id": self.provider_id,
            "action": self.action,
            "field_paths": list(self.field_paths),
            "supported": self.supported,
            "reason": (redact_control_plane_text(self.reason) if self.reason else None),
        }


@dataclass(frozen=True, slots=True)
class ErasurePlan:
    plan_id: str
    request_id: str
    steps: tuple[ErasurePlanStep, ...]
    created_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ERASURE_PLAN_SCHEMA,
            "plan_id": self.plan_id,
            "request_id": self.request_id,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ErasureStepResult:
    step_id: str
    provider_id: str
    status: ErasureStatus
    proof_fingerprint: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "provider_id": self.provider_id,
            "status": self.status,
            "proof_fingerprint": self.proof_fingerprint,
            "reason": (redact_control_plane_text(self.reason) if self.reason else None),
        }


@dataclass(frozen=True, slots=True)
class ErasureReport:
    report_id: str
    request_id: str
    plan_id: str
    status: ErasureStatus
    results: tuple[ErasureStepResult, ...]
    reconciled: bool
    created_at: datetime = field(default_factory=_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ERASURE_REPORT_SCHEMA,
            "report_id": self.report_id,
            "request_id": self.request_id,
            "plan_id": self.plan_id,
            "status": self.status,
            "results": [r.to_dict() for r in self.results],
            "reconciled": self.reconciled,
            "created_at": self.created_at.isoformat(),
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }


def assert_no_subject_values(
    payload: Mapping[str, Any] | Sequence[Any] | str,
    *,
    forbidden: Sequence[str],
) -> None:
    """Raise AssertionError if any forbidden subject value appears."""
    blob = str(payload)
    for value in forbidden:
        if value and value in blob:
            raise AssertionError(f"subject value leaked: {value!r}")


__all__ = [
    "ERASURE_PLAN_SCHEMA",
    "ERASURE_REPORT_SCHEMA",
    "ERASURE_REQUEST_SCHEMA",
    "ErasureAction",
    "ErasurePlan",
    "ErasurePlanStep",
    "ErasureReport",
    "ErasureRequest",
    "ErasureStatus",
    "ErasureStepResult",
    "assert_no_subject_values",
]
