"""Versioned optimization-pass protocol types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from etlantic.plan.freeze import deep_freeze, mutable_copy
from etlantic.plan.model import PipelinePlan
from etlantic.profile import Profile

OPTIMIZATION_SCHEMA = "etlantic.optimization/1"
OPTIMIZATION_PROTOCOL = "etlantic.optimization-pass/1"

RewriteKind = Literal[
    "pushdown",
    "pruning",
    "fusion",
    "materialization",
    "reuse",
    "repair_backfill",
    "implementation_selection",
    "cross_backend",
]
CandidateDecision = Literal["chosen", "rejected", "shadow"]
ProofStatus = Literal["proven", "rejected", "deferred"]
PolicyResult = Literal["accepted", "rejected", "not_evaluated"]
CapabilityResult = Literal["supported", "unsupported", "unknown"]


@dataclass(frozen=True, slots=True)
class PassPrerequisites:
    """Declared inputs a pass requires before proposing candidates."""

    requires_evidence_kinds: tuple[str, ...] = ()
    requires_engines: tuple[str, ...] = ()
    min_nodes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "requires_evidence_kinds": list(self.requires_evidence_kinds),
            "requires_engines": list(self.requires_engines),
            "min_nodes": self.min_nodes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PassPrerequisites:
        raw = dict(data or {})
        return cls(
            requires_evidence_kinds=tuple(
                str(x) for x in (raw.get("requires_evidence_kinds") or ())
            ),
            requires_engines=tuple(str(x) for x in (raw.get("requires_engines") or ())),
            min_nodes=int(raw.get("min_nodes") or 0),
        )


@dataclass(frozen=True, slots=True)
class PassMetadata:
    """Versioned identity and ordering for an optimization pass."""

    pass_id: str
    version: str
    rewrite_kinds: tuple[str, ...]
    protocol: str = OPTIMIZATION_PROTOCOL
    priority: int = 100
    prerequisites: PassPrerequisites = field(default_factory=PassPrerequisites)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_id": self.pass_id,
            "version": self.version,
            "rewrite_kinds": list(self.rewrite_kinds),
            "protocol": self.protocol,
            "priority": self.priority,
            "prerequisites": self.prerequisites.to_dict(),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PassMetadata:
        return cls(
            pass_id=str(data["pass_id"]),
            version=str(data.get("version") or "0.0.0"),
            rewrite_kinds=tuple(str(x) for x in (data.get("rewrite_kinds") or ())),
            protocol=str(data.get("protocol") or OPTIMIZATION_PROTOCOL),
            priority=int(data.get("priority") or 100),
            prerequisites=PassPrerequisites.from_dict(data.get("prerequisites")),
            description=str(data.get("description") or ""),
        )


@dataclass(frozen=True, slots=True)
class ProofObligation:
    """Semantic or security proof attached to a candidate."""

    kind: str
    status: ProofStatus
    detail: str = ""
    boundaries: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "detail": self.detail,
            "boundaries": list(self.boundaries),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProofObligation:
        status = str(data.get("status") or "deferred")
        if status not in {"proven", "rejected", "deferred"}:
            status = "deferred"
        return cls(
            kind=str(data["kind"]),
            status=status,  # type: ignore[arg-type]
            detail=str(data.get("detail") or ""),
            boundaries=tuple(str(x) for x in (data.get("boundaries") or ())),
        )


@dataclass(frozen=True, slots=True)
class OptimizationCandidate:
    """One proposed physical-plan change with evidence and proof."""

    candidate_id: str
    pass_id: str
    rewrite_kind: str
    decision: CandidateDecision
    expected_benefit: dict[str, Any]
    proofs: tuple[ProofObligation, ...]
    evidence_refs: tuple[dict[str, Any], ...]
    policy_result: PolicyResult
    capability_result: CapabilityResult
    reason: str
    cost_scores: dict[str, float] = field(default_factory=dict)
    hints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "pass_id": self.pass_id,
            "rewrite_kind": self.rewrite_kind,
            "decision": self.decision,
            "expected_benefit": mutable_copy(self.expected_benefit),
            "proofs": [p.to_dict() for p in self.proofs],
            "evidence_refs": mutable_copy(list(self.evidence_refs)),
            "policy_result": self.policy_result,
            "capability_result": self.capability_result,
            "reason": self.reason,
            "cost_scores": dict(self.cost_scores),
            "hints": mutable_copy(self.hints),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OptimizationCandidate:
        decision = str(data.get("decision") or "rejected")
        if decision not in {"chosen", "rejected", "shadow"}:
            decision = "rejected"
        policy = str(data.get("policy_result") or "not_evaluated")
        if policy not in {"accepted", "rejected", "not_evaluated"}:
            policy = "not_evaluated"
        capability = str(data.get("capability_result") or "unknown")
        if capability not in {"supported", "unsupported", "unknown"}:
            capability = "unknown"
        cand = cls(
            candidate_id=str(data["candidate_id"]),
            pass_id=str(data["pass_id"]),
            rewrite_kind=str(data["rewrite_kind"]),
            decision=decision,  # type: ignore[arg-type]
            expected_benefit=dict(data.get("expected_benefit") or {}),
            proofs=tuple(
                ProofObligation.from_dict(p) for p in (data.get("proofs") or ())
            ),
            evidence_refs=tuple(dict(x) for x in (data.get("evidence_refs") or ())),
            policy_result=policy,  # type: ignore[arg-type]
            capability_result=capability,  # type: ignore[arg-type]
            reason=str(data.get("reason") or ""),
            cost_scores={
                str(k): float(v) for k, v in dict(data.get("cost_scores") or {}).items()
            },
            hints=dict(data.get("hints") or {}),
        )
        object.__setattr__(cand, "expected_benefit", deep_freeze(cand.expected_benefit))
        object.__setattr__(cand, "hints", deep_freeze(cand.hints))
        return cand


@dataclass(frozen=True, slots=True)
class OptimizationContext:
    """Read-only host context available to passes (no secret/data authority)."""

    baseline: PipelinePlan
    profile: Profile
    evidence: Any  # EvidenceStore; typed loosely to avoid import cycle
    budgets: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class OptimizationPass(Protocol):
    """Protocol for advisory optimization passes."""

    @property
    def metadata(self) -> PassMetadata:
        """Return versioned pass identity."""

    def propose(
        self, context: OptimizationContext
    ) -> tuple[OptimizationCandidate, ...]:
        """Propose zero or more candidates for the baseline plan."""
