"""Versioned policy decision envelopes (CP4 / ADR-019)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from etlantic.control_plane.governance_models import GovernanceConstraints
from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)

POLICY_DECISION_SCHEMA = "etlantic.control_plane.policy_decision/1"
POLICY_BUNDLE_SCHEMA = "etlantic.control_plane.policy_bundle/1"

PolicyEffect = Literal["allow", "deny", "require_approval"]
PolicyHook = Literal[
    "pre_plan",
    "post_plan",
    "pre_submit",
    "post_execution",
    "pre_promote",
    "pre_repair",
    "privileged_op",
]


def _now() -> datetime:
    return datetime.now(UTC)


def compute_policy_fingerprint(
    *,
    bundle_id: str,
    hook: str,
    plan_fingerprint: str | None,
    revision_id: str | None,
    constraints: Mapping[str, Any] | None = None,
) -> str:
    """Deterministic fingerprint for durable policy_fingerprint fields."""
    payload = {
        "bundle_id": bundle_id,
        "hook": hook,
        "plan_fingerprint": plan_fingerprint or "",
        "revision_id": revision_id or "",
        "constraints": dict(constraints or {}),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PolicyBundle:
    """Named, versioned set of policy rules (opaque to core)."""

    bundle_id: str
    version: str
    fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": POLICY_BUNDLE_SCHEMA,
            "bundle_id": self.bundle_id,
            "version": self.version,
            "fingerprint": self.fingerprint,
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Explicit, reproducible policy outcome for a single hook invocation."""

    decision_id: str
    hook: PolicyHook
    effect: PolicyEffect
    policy_bundle_id: str
    policy_fingerprint: str
    reasons: tuple[str, ...] = ()
    constraints: GovernanceConstraints = field(default_factory=GovernanceConstraints)
    evidence_refs: tuple[str, ...] = ()
    plan_fingerprint: str | None = None
    revision_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": POLICY_DECISION_SCHEMA,
            "decision_id": self.decision_id,
            "hook": self.hook,
            "effect": self.effect,
            "policy_bundle_id": self.policy_bundle_id,
            "policy_fingerprint": self.policy_fingerprint,
            "reasons": [redact_control_plane_text(r) for r in self.reasons],
            "constraints": self.constraints.to_dict(),
            "evidence_refs": list(self.evidence_refs),
            "plan_fingerprint": self.plan_fingerprint,
            "revision_id": self.revision_id,
            "created_at": self.created_at.isoformat(),
            "metadata": redact_control_plane_payload(dict(self.metadata)),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PolicyDecision:
        created = data.get("created_at")
        if isinstance(created, str):
            created_at = datetime.fromisoformat(created)
        elif isinstance(created, datetime):
            created_at = created
        else:
            created_at = _now()
        return cls(
            decision_id=str(data["decision_id"]),
            hook=str(data["hook"]),  # type: ignore[arg-type]
            effect=str(data["effect"]),  # type: ignore[arg-type]
            policy_bundle_id=str(data["policy_bundle_id"]),
            policy_fingerprint=str(data["policy_fingerprint"]),
            reasons=tuple(str(r) for r in (data.get("reasons") or ())),
            constraints=GovernanceConstraints.from_dict(data.get("constraints")),
            evidence_refs=tuple(str(r) for r in (data.get("evidence_refs") or ())),
            plan_fingerprint=(
                str(data["plan_fingerprint"])
                if data.get("plan_fingerprint") is not None
                else None
            ),
            revision_id=(
                str(data["revision_id"])
                if data.get("revision_id") is not None
                else None
            ),
            created_at=created_at,
            metadata=dict(data.get("metadata") or {}),
        )


def decision_allows(decision: PolicyDecision) -> bool:
    return decision.effect == "allow"


def decision_requires_approval(decision: PolicyDecision) -> bool:
    return decision.effect == "require_approval"


__all__ = [
    "POLICY_BUNDLE_SCHEMA",
    "POLICY_DECISION_SCHEMA",
    "PolicyBundle",
    "PolicyDecision",
    "PolicyEffect",
    "PolicyHook",
    "compute_policy_fingerprint",
    "decision_allows",
    "decision_requires_approval",
]
