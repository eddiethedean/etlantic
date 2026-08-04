"""Approval request models (CP4 separation of duties)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)

APPROVAL_REQUEST_SCHEMA = "etlantic.control_plane.approval_request/1"
APPROVAL_DECISION_SCHEMA = "etlantic.control_plane.approval_decision/1"

ApprovalStatus = Literal["pending", "approved", "denied", "expired", "revoked", "stale"]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ApprovalDecisionRecord:
    decision_id: str
    approval_id: str
    effect: Literal["approved", "denied"]
    actor_subject: str
    actor_issuer: str | None
    created_at: datetime = field(default_factory=_now)
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": APPROVAL_DECISION_SCHEMA,
            "decision_id": self.decision_id,
            "approval_id": self.approval_id,
            "effect": self.effect,
            "actor_subject": self.actor_subject,
            "actor_issuer": self.actor_issuer,
            "created_at": self.created_at.isoformat(),
            "reason": (redact_control_plane_text(self.reason) if self.reason else None),
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    approval_id: str
    tenant_id: str
    workspace_id: str
    hook: str
    plan_fingerprint: str
    policy_fingerprint: str
    revision_id: str | None
    requester_subject: str
    requester_issuer: str | None
    status: ApprovalStatus = "pending"
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=_now)
    decided_at: datetime | None = None
    decisions: tuple[ApprovalDecisionRecord, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": APPROVAL_REQUEST_SCHEMA,
            "approval_id": self.approval_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "hook": self.hook,
            "plan_fingerprint": self.plan_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "revision_id": self.revision_id,
            "requester_subject": self.requester_subject,
            "requester_issuer": self.requester_issuer,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decisions": [d.to_dict() for d in self.decisions],
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }


__all__ = [
    "APPROVAL_DECISION_SCHEMA",
    "APPROVAL_REQUEST_SCHEMA",
    "ApprovalDecisionRecord",
    "ApprovalRequest",
    "ApprovalStatus",
]
