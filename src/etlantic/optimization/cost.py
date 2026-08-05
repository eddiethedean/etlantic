"""Cost providers and multi-objective candidate selection."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol, runtime_checkable

from etlantic.optimization.diagnostics import optimization_diagnostic
from etlantic.optimization.evidence import EvidenceStore
from etlantic.optimization.protocol import OptimizationCandidate
from etlantic.plan.model import PipelinePlan


@dataclass(frozen=True, slots=True)
class CostScore:
    """Named cost vector for a candidate (provider-local units)."""

    provider_id: str
    scores: dict[str, float]
    objectives: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "scores": dict(self.scores),
            "objectives": list(self.objectives),
        }


@dataclass(frozen=True, slots=True)
class CostBudget:
    """Upper bounds on named cost dimensions."""

    limits: dict[str, float] = field(default_factory=dict)

    def exceeds(self, scores: dict[str, float]) -> tuple[str, ...]:
        breached: list[str] = []
        for key, limit in self.limits.items():
            if key in scores and scores[key] > limit:
                breached.append(key)
        return tuple(breached)

    def to_dict(self) -> dict[str, Any]:
        return {"limits": dict(self.limits)}


@runtime_checkable
class CostProvider(Protocol):
    """Pluggable cost model (scores comparable within a provider only)."""

    @property
    def provider_id(self) -> str:
        """Stable provider identity."""

    def score(
        self,
        candidate: OptimizationCandidate,
        *,
        plan: PipelinePlan,
        evidence: EvidenceStore,
    ) -> CostScore:
        """Estimate cost / benefit for a candidate."""


class RuleCostProvider:
    """Deterministic rule-based costs from rewrite kind and plan size."""

    provider_id = "etlantic.rule_cost/1"

    _BASE: ClassVar[dict[str, dict[str, float]]] = {
        "pushdown": {"cpu": 0.2, "io": -1.0, "latency": -0.5},
        "pruning": {"cpu": -0.5, "io": -0.5, "latency": -0.3},
        "fusion": {"cpu": -0.4, "io": 0.0, "latency": -0.2},
        "materialization": {"cpu": 0.1, "io": 0.5, "latency": -0.4},
        "reuse": {"cpu": -0.3, "io": -0.8, "latency": -0.6},
        "repair_backfill": {"cpu": 1.0, "io": 1.0, "latency": 0.5},
        "implementation_selection": {"cpu": -0.2, "io": 0.0, "latency": -0.1},
        "cross_backend": {"cpu": 0.3, "io": 0.8, "latency": 0.2},
    }

    def score(
        self,
        candidate: OptimizationCandidate,
        *,
        plan: PipelinePlan,
        evidence: EvidenceStore,
    ) -> CostScore:
        base = dict(
            self._BASE.get(
                candidate.rewrite_kind, {"cpu": 0.0, "io": 0.0, "latency": 0.0}
            )
        )
        scale = max(1.0, len(plan.logical_graph.nodes) / 10.0)
        benefit = float(candidate.expected_benefit.get("relative", 0.0) or 0.0)
        scores = {
            "cpu": base.get("cpu", 0.0) * scale - benefit,
            "io": base.get("io", 0.0) * scale - benefit * 0.5,
            "latency": base.get("latency", 0.0) - benefit * 0.25,
            "benefit": -benefit,
        }
        # Prefer higher confidence evidence by slightly reducing cost.
        conf = 0.0
        for ref in candidate.evidence_refs:
            conf = max(conf, float(ref.get("confidence") or 0.0))
        if conf:
            for key in ("cpu", "io", "latency"):
                scores[key] *= 1.0 - 0.1 * conf
        _ = evidence  # plan-time only; provider must not fetch live data
        return CostScore(
            provider_id=self.provider_id,
            scores=scores,
            objectives=(
                "minimize_cpu",
                "minimize_io",
                "minimize_latency",
                "maximize_benefit",
            ),
        )


class StatisticalCostProvider:
    """Cost estimates weighted by cardinality / locality evidence when present."""

    provider_id = "etlantic.statistical_cost/1"

    def score(
        self,
        candidate: OptimizationCandidate,
        *,
        plan: PipelinePlan,
        evidence: EvidenceStore,
    ) -> CostScore:
        rule = RuleCostProvider().score(candidate, plan=plan, evidence=evidence)
        card = evidence.by_kind("cardinality")
        locality = evidence.by_kind("locality")
        card_factor = 1.0
        if card:
            values = []
            for record in card:
                try:
                    values.append(float(record.value))
                except (TypeError, ValueError):
                    if isinstance(record.value, dict) and "rows" in record.value:
                        with contextlib.suppress(TypeError, ValueError):
                            values.append(float(record.value["rows"]))
            if values:
                card_factor = max(0.1, min(10.0, sum(values) / (1000.0 * len(values))))
        locality_bonus = -0.2 * len(locality)
        scores = {}
        for key, value in rule.scores.items():
            scaled = value * card_factor if key != "benefit" else value
            if key == "latency":
                scaled += locality_bonus
            scores[key] = scaled
        return CostScore(
            provider_id=self.provider_id,
            scores=scores,
            objectives=rule.objectives,
        )


def _reject_candidate(
    candidate: OptimizationCandidate,
    *,
    reason: str,
    policy: str = "rejected",
    cost_scores: dict[str, float] | None = None,
) -> OptimizationCandidate:
    return OptimizationCandidate(
        candidate_id=candidate.candidate_id,
        pass_id=candidate.pass_id,
        rewrite_kind=candidate.rewrite_kind,
        decision="rejected",
        expected_benefit=dict(candidate.expected_benefit),
        proofs=candidate.proofs,
        evidence_refs=candidate.evidence_refs,
        policy_result=policy,  # type: ignore[arg-type]
        capability_result=candidate.capability_result,
        reason=reason,
        cost_scores=dict(
            cost_scores if cost_scores is not None else candidate.cost_scores
        ),
        hints=dict(candidate.hints),
    )


def _candidate_evidence_issues(
    candidate: OptimizationCandidate,
    *,
    evidence: EvidenceStore,
    stale_ids: set[str],
) -> tuple[str | None, str]:
    """Return (diagnostic_key, reason) when evidence does not justify accept."""
    if not candidate.evidence_refs:
        return None, ""
    missing_ids: list[str] = []
    missing_kinds: list[str] = []
    stale_for_candidate: list[str] = []
    for ref in candidate.evidence_refs:
        eid = str(ref.get("evidence_id") or "")
        kind = str(ref.get("kind") or "")
        if not eid:
            continue
        record = evidence.get(eid)
        if record is None:
            missing_ids.append(eid)
            if kind:
                missing_kinds.append(kind)
            continue
        if eid in stale_ids or record.is_stale():
            stale_for_candidate.append(eid)
        if (
            kind
            and record.kind != kind
            and kind not in {r.kind for r in evidence.by_kind(kind)}
            and not evidence.by_kind(kind)
        ):
            missing_kinds.append(kind)
    if missing_ids:
        return (
            "missing_evidence",
            f"unresolved evidence ids: {', '.join(sorted(set(missing_ids)))}",
        )
    if missing_kinds:
        return (
            "missing_evidence",
            f"missing evidence kinds: {', '.join(sorted(set(missing_kinds)))}",
        )
    if stale_for_candidate:
        return (
            "stale_evidence",
            f"stale evidence ids: {', '.join(sorted(set(stale_for_candidate)))}",
        )
    return None, ""


def select_candidates(
    candidates: tuple[OptimizationCandidate, ...],
    *,
    plan: PipelinePlan,
    evidence: EvidenceStore,
    provider: CostProvider | None = None,
    budget: CostBudget | None = None,
    objective: str = "benefit",
) -> tuple[tuple[OptimizationCandidate, ...], tuple[Any, ...]]:
    """Attach cost scores and choose among policy/capability-accepted candidates.

    Missing, stale, or unresolved evidence rejects; budget breaches reject.
    """
    cost_provider: CostProvider = provider or RuleCostProvider()
    budget = budget or CostBudget()
    diagnostics: list[Any] = []
    scored: list[OptimizationCandidate] = []

    stats = evidence.statistics(
        required_kinds=tuple(
            {
                kind
                for c in candidates
                for ref in c.evidence_refs
                for kind in [str(ref.get("kind") or "")]
                if kind
            }
        )
    )
    stale_ids = set(stats.stale_ids)
    if stats.missing_kinds:
        diagnostics.append(
            optimization_diagnostic(
                "missing_evidence",
                f"Missing evidence kinds: {', '.join(stats.missing_kinds)}; rejecting unjustified rewrites",
                path=("optimization", "evidence"),
            )
        )
    if stats.stale_ids:
        diagnostics.append(
            optimization_diagnostic(
                "stale_evidence",
                f"Stale evidence ids: {', '.join(stats.stale_ids)}; rejecting unjustified rewrites",
                path=("optimization", "evidence"),
            )
        )
    if stats.conflicting_subjects:
        diagnostics.append(
            optimization_diagnostic(
                "conflicting_evidence",
                f"Conflicting evidence subjects: {', '.join(stats.conflicting_subjects)}; rejecting unjustified rewrites",
                severity="error",
                path=("optimization", "evidence"),
            )
        )

    for candidate in candidates:
        if stats.conflicting_subjects and candidate.decision != "rejected":
            scored.append(
                _reject_candidate(
                    candidate, reason="rejected due to conflicting evidence"
                )
            )
            continue

        evidence_key, evidence_reason = _candidate_evidence_issues(
            candidate, evidence=evidence, stale_ids=stale_ids
        )
        if evidence_key and candidate.decision == "chosen":
            diagnostics.append(
                optimization_diagnostic(
                    evidence_key,
                    f"Candidate {candidate.candidate_id}: {evidence_reason}",
                    path=("optimization", "evidence", candidate.candidate_id),
                )
            )
            scored.append(
                _reject_candidate(
                    candidate, reason=f"rejected due to {evidence_reason}"
                )
            )
            continue

        cost = cost_provider.score(candidate, plan=plan, evidence=evidence)
        breached = budget.exceeds(cost.scores)
        decision = candidate.decision
        policy = candidate.policy_result
        reason = candidate.reason
        if breached:
            decision = "rejected"
            policy = "rejected"
            reason = f"budget exceeded: {', '.join(breached)}"
            diagnostics.append(
                optimization_diagnostic(
                    "budget_exceeded",
                    reason,
                    path=("optimization", "budget", candidate.candidate_id),
                    metadata={
                        "limits": dict(budget.limits),
                        "scores": dict(cost.scores),
                    },
                )
            )
        # Gate: missing proof or rejected proof cannot be chosen.
        if any(p.status == "rejected" for p in candidate.proofs):
            decision = "rejected"
            policy = "rejected"
            reason = "proof rejected"
            diagnostics.append(
                optimization_diagnostic(
                    "proof_rejected",
                    reason,
                    severity="error",
                    path=("optimization", "proof", candidate.candidate_id),
                )
            )
        elif not candidate.proofs or any(
            p.status == "deferred" for p in candidate.proofs
        ):
            if decision == "chosen":
                decision = "rejected"
                reason = "missing or deferred semantic proof"
                diagnostics.append(
                    optimization_diagnostic(
                        "missing_proof",
                        reason,
                        path=("optimization", "proof", candidate.candidate_id),
                    )
                )
        if candidate.capability_result != "supported" and decision == "chosen":
            decision = "rejected"
            reason = (
                "backend capability unsupported"
                if candidate.capability_result == "unsupported"
                else f"capability not confirmed ({candidate.capability_result})"
            )
            diagnostics.append(
                optimization_diagnostic(
                    "capability_rejected",
                    reason,
                    severity="error",
                    path=("optimization", "capability", candidate.candidate_id),
                )
            )
        if candidate.policy_result != "accepted" and decision == "chosen":
            decision = "rejected"
            policy = "rejected"
            reason = (
                "policy rejected"
                if candidate.policy_result == "rejected"
                else f"policy not accepted ({candidate.policy_result})"
            )
            diagnostics.append(
                optimization_diagnostic(
                    "policy_rejected",
                    reason,
                    severity="error",
                    path=("optimization", "policy", candidate.candidate_id),
                )
            )

        scored.append(
            OptimizationCandidate(
                candidate_id=candidate.candidate_id,
                pass_id=candidate.pass_id,
                rewrite_kind=candidate.rewrite_kind,
                decision=decision,
                expected_benefit=dict(candidate.expected_benefit),
                proofs=candidate.proofs,
                evidence_refs=candidate.evidence_refs,
                policy_result=policy,
                capability_result=candidate.capability_result,
                reason=reason,
                cost_scores=dict(cost.scores),
                hints=dict(candidate.hints),
            )
        )

    # Multi-objective: pick lowest objective among chosen; mark others dominated.
    chosen = [c for c in scored if c.decision == "chosen"]
    if len(chosen) > 1:
        key = "benefit" if objective == "benefit" else objective
        best = min(chosen, key=lambda c: c.cost_scores.get(key, 0.0))
        refined: list[OptimizationCandidate] = []
        for candidate in scored:
            if (
                candidate.decision == "chosen"
                and candidate.candidate_id != best.candidate_id
            ):
                refined.append(
                    OptimizationCandidate(
                        candidate_id=candidate.candidate_id,
                        pass_id=candidate.pass_id,
                        rewrite_kind=candidate.rewrite_kind,
                        decision="shadow",
                        expected_benefit=dict(candidate.expected_benefit),
                        proofs=candidate.proofs,
                        evidence_refs=candidate.evidence_refs,
                        policy_result=candidate.policy_result,
                        capability_result=candidate.capability_result,
                        reason=f"dominated by {best.candidate_id} on {key}",
                        cost_scores=dict(candidate.cost_scores),
                        hints={
                            **dict(candidate.hints),
                            "dominated": True,
                            "dominated_by": best.candidate_id,
                        },
                    )
                )
            else:
                refined.append(candidate)
        scored = refined

    return tuple(scored), tuple(diagnostics)
