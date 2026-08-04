"""Delivery objective models (CP4)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)

DELIVERY_OBJECTIVE_SCHEMA = "etlantic.control_plane.delivery_objective/1"
OBJECTIVE_EVALUATION_SCHEMA = "etlantic.control_plane.objective_evaluation/1"
OBJECTIVE_NOTIFICATION_SCHEMA = "etlantic.control_plane.objective_notification/1"

ObjectiveReference = Literal[
    "scheduled", "queued", "started", "source_ready", "fixed_time"
]
ObjectiveSeverity = Literal["info", "warning", "critical"]
ObjectiveState = Literal["on_track", "warning", "breached", "recovered", "acknowledged"]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class DeliveryObjective:
    objective_id: str
    tenant_id: str
    workspace_id: str
    pipeline_id: str
    step_id: str | None
    version: str
    reference: ObjectiveReference
    warning_after_seconds: int
    hard_after_seconds: int
    grace_seconds: int = 0
    calendar: str = "UTC"
    owner: str | None = None
    severity: ObjectiveSeverity = "warning"
    fixed_time: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": DELIVERY_OBJECTIVE_SCHEMA,
            "objective_id": self.objective_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "pipeline_id": self.pipeline_id,
            "step_id": self.step_id,
            "version": self.version,
            "reference": self.reference,
            "warning_after_seconds": self.warning_after_seconds,
            "hard_after_seconds": self.hard_after_seconds,
            "grace_seconds": self.grace_seconds,
            "calendar": self.calendar,
            "owner": self.owner,
            "severity": self.severity,
            "fixed_time": self.fixed_time.isoformat() if self.fixed_time else None,
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }

    def deadline(self, reference_at: datetime, *, hard: bool = True) -> datetime:
        seconds = self.hard_after_seconds if hard else self.warning_after_seconds
        base = (
            self.fixed_time
            if self.reference == "fixed_time" and self.fixed_time
            else reference_at
        )
        return base + timedelta(seconds=seconds + self.grace_seconds)


@dataclass(frozen=True, slots=True)
class ObjectiveEvaluation:
    evaluation_id: str
    objective_id: str
    state: ObjectiveState
    reference_at: datetime
    evaluated_at: datetime
    dedupe_key: str
    submission_id: str | None = None
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": OBJECTIVE_EVALUATION_SCHEMA,
            "evaluation_id": self.evaluation_id,
            "objective_id": self.objective_id,
            "state": self.state,
            "reference_at": self.reference_at.isoformat(),
            "evaluated_at": self.evaluated_at.isoformat(),
            "dedupe_key": self.dedupe_key,
            "submission_id": self.submission_id,
            "reason": (redact_control_plane_text(self.reason) if self.reason else None),
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }


@dataclass(frozen=True, slots=True)
class ObjectiveNotification:
    notification_id: str
    evaluation_id: str
    channel: str
    destination_ref: str
    delivered: bool
    created_at: datetime = field(default_factory=_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": OBJECTIVE_NOTIFICATION_SCHEMA,
            "notification_id": self.notification_id,
            "evaluation_id": self.evaluation_id,
            "channel": self.channel,
            "destination_ref": self.destination_ref,
            "delivered": self.delivered,
            "created_at": self.created_at.isoformat(),
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }


__all__ = [
    "DELIVERY_OBJECTIVE_SCHEMA",
    "OBJECTIVE_EVALUATION_SCHEMA",
    "OBJECTIVE_NOTIFICATION_SCHEMA",
    "DeliveryObjective",
    "ObjectiveEvaluation",
    "ObjectiveNotification",
    "ObjectiveReference",
    "ObjectiveSeverity",
    "ObjectiveState",
]
