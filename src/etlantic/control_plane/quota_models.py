"""Quota and fairness models (CP4)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from etlantic.control_plane.redaction import redact_control_plane_payload

QUOTA_BUDGET_SCHEMA = "etlantic.control_plane.quota_budget/1"
QUOTA_DECISION_SCHEMA = "etlantic.control_plane.quota_decision/1"
QUOTA_STATE_SCHEMA = "etlantic.control_plane.quota_state/1"

QuotaResource = Literal[
    "concurrency",
    "preview",
    "events",
    "repair",
    "storage_bytes",
]
QuotaEffect = Literal["allow", "deny", "suspended", "contained"]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class QuotaBudget:
    resource: QuotaResource
    limit: int
    weight: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": QUOTA_BUDGET_SCHEMA,
            "resource": self.resource,
            "limit": self.limit,
            "weight": self.weight,
        }


@dataclass(frozen=True, slots=True)
class QuotaState:
    tenant_id: str
    workspace_id: str
    suspended: bool = False
    contained: bool = False
    usage: Mapping[str, int] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": QUOTA_STATE_SCHEMA,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "suspended": self.suspended,
            "contained": self.contained,
            "usage": dict(self.usage),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class QuotaDecision:
    effect: QuotaEffect
    resource: QuotaResource
    limit: int
    used: int
    reason: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": QUOTA_DECISION_SCHEMA,
            "effect": self.effect,
            "resource": self.resource,
            "limit": self.limit,
            "used": self.used,
            "reason": self.reason,
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }


__all__ = [
    "QUOTA_BUDGET_SCHEMA",
    "QUOTA_DECISION_SCHEMA",
    "QUOTA_STATE_SCHEMA",
    "QuotaBudget",
    "QuotaDecision",
    "QuotaEffect",
    "QuotaResource",
    "QuotaState",
]
