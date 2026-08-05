"""Optimization engine: run passes, gate candidates, derive optimized plans."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from etlantic.optimization.cost import (
    CostBudget,
    CostProvider,
    RuleCostProvider,
    select_candidates,
)
from etlantic.optimization.diagnostics import optimization_diagnostic
from etlantic.optimization.evidence import EvidenceStore, evidence_fingerprint
from etlantic.optimization.protocol import (
    OPTIMIZATION_SCHEMA,
    OptimizationCandidate,
    OptimizationContext,
    OptimizationPass,
)
from etlantic.optimization.registry import (
    builtin_passes,
    discover_optimization_passes,
    resolve_pass_order,
)
from etlantic.plan.diff import PlanDiff, diff_plans
from etlantic.plan.freeze import deep_freeze, mutable_copy
from etlantic.plan.model import PipelinePlan
from etlantic.plan.serialize import plan_fingerprint
from etlantic.profile import Profile

OptimizationPolicy = Literal["off", "shadow", "apply_accepted"]

_SECRET_HINT_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "credential",
        "credentials",
        "private_key",
        "access_key",
        "secret_key",
    }
)


def sanitize_hints(hints: dict[str, Any] | None) -> dict[str, Any]:
    """Drop secret-like keys from rewrite hints before explain/emit."""
    if not hints:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in hints.items():
        key_l = str(key).lower()
        if key_l in _SECRET_HINT_KEYS or any(s in key_l for s in _SECRET_HINT_KEYS):
            continue
        if isinstance(value, dict):
            cleaned[key] = sanitize_hints(value)
        else:
            cleaned[key] = copy.deepcopy(value)
    return cleaned


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """Immutable optimization outcome (etlantic.optimization/1)."""

    schema: str
    baseline_fingerprint: str
    optimized_fingerprint: str | None
    result_fingerprint: str
    evidence_fingerprint: str
    policy: OptimizationPolicy
    applied: bool
    pass_order: tuple[str, ...]
    candidates: tuple[OptimizationCandidate, ...]
    diagnostics: tuple[Any, ...] = ()
    plan_diff: dict[str, Any] | None = None
    shadow: dict[str, Any] | None = None
    optimized_plan: PipelinePlan | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "baseline_fingerprint": self.baseline_fingerprint,
            "optimized_fingerprint": self.optimized_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
            "policy": self.policy,
            "applied": self.applied,
            "pass_order": list(self.pass_order),
            "candidates": [c.to_dict() for c in self.candidates],
            "diagnostics": [
                d.to_dict() if hasattr(d, "to_dict") else dict(d)
                for d in self.diagnostics
            ],
            "plan_diff": mutable_copy(self.plan_diff) if self.plan_diff else None,
            "shadow": mutable_copy(self.shadow) if self.shadow else None,
            "metadata": mutable_copy(self.metadata),
        }


def _result_fingerprint(
    *,
    baseline_fp: str,
    evidence_fp: str,
    pass_order: tuple[str, ...],
    candidates: tuple[OptimizationCandidate, ...],
    policy: str,
) -> str:
    payload = {
        "baseline_fingerprint": baseline_fp,
        "evidence_fingerprint": evidence_fp,
        "pass_order": list(pass_order),
        "candidates": [c.to_dict() for c in candidates],
        "policy": policy,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def derive_optimized_plan(
    baseline: PipelinePlan,
    candidates: tuple[OptimizationCandidate, ...],
) -> PipelinePlan:
    """Derive an optimized plan by annotating accepted rewrite hints.

    Does not mutate the baseline. Recomputes fingerprint after metadata merge.
    Annotations are advisory for host consumption — not a physical rewrite.
    """
    annotations: dict[str, Any] = {"etlantic.optimization": {"rewrites": []}}
    for candidate in candidates:
        if candidate.decision != "chosen":
            continue
        annotations["etlantic.optimization"]["rewrites"].append(
            {
                "candidate_id": candidate.candidate_id,
                "pass_id": candidate.pass_id,
                "rewrite_kind": candidate.rewrite_kind,
                "hints": sanitize_hints(dict(candidate.hints or {})),
                "reason": candidate.reason,
            }
        )
        annotate = (candidate.hints or {}).get("annotate") or {}
        if isinstance(annotate, dict):
            for key, value in annotate.items():
                annotations[f"etlantic.optimization.{key}"] = copy.deepcopy(value)

    meta = mutable_copy(dict(baseline.metadata or {}))
    meta.update(annotations)
    data = baseline.to_dict()
    data["metadata"] = meta
    data["fingerprint"] = ""  # recomputed
    plan = PipelinePlan.from_dict(data, verify=False)
    fp = plan_fingerprint(plan)
    object.__setattr__(plan, "fingerprint", fp)
    # Ensure nested freeze
    object.__setattr__(plan, "metadata", deep_freeze(dict(plan.metadata)))
    return plan


def _is_dominated(candidate: OptimizationCandidate) -> bool:
    hints = candidate.hints or {}
    return bool(hints.get("dominated")) or str(candidate.reason or "").startswith(
        "dominated by "
    )


def optimize_plan(
    baseline: PipelinePlan,
    *,
    profile: Profile | None = None,
    evidence: EvidenceStore | None = None,
    passes: tuple[OptimizationPass, ...] | list[OptimizationPass] | None = None,
    cost_provider: CostProvider | None = None,
    budget: CostBudget | None = None,
    policy: OptimizationPolicy | None = None,
    include_entry_points: bool = True,
    prior_report_summary: dict[str, Any] | None = None,
    budgets: dict[str, float] | None = None,
) -> OptimizationResult:
    """Run the advisory optimization pipeline on a baseline plan."""
    if profile is None:
        snap = dict(baseline.profile_snapshot or {})
        if snap:
            profile = Profile.from_plan_snapshot(snap)
        else:
            from etlantic.profile import development_profile

            profile = development_profile()

    resolved_policy: OptimizationPolicy = policy or getattr(
        profile, "optimization_policy", "off"
    )  # type: ignore[assignment]
    if resolved_policy not in {"off", "shadow", "apply_accepted"}:
        resolved_policy = "off"

    store = evidence or EvidenceStore.from_plan(
        baseline, prior_report_summary=prior_report_summary
    )
    ev_fp = evidence_fingerprint(store)

    if resolved_policy == "off":
        empty = _result_fingerprint(
            baseline_fp=baseline.fingerprint,
            evidence_fp=ev_fp,
            pass_order=(),
            candidates=(),
            policy="off",
        )
        return OptimizationResult(
            schema=OPTIMIZATION_SCHEMA,
            baseline_fingerprint=baseline.fingerprint,
            optimized_fingerprint=None,
            result_fingerprint=empty,
            evidence_fingerprint=ev_fp,
            policy="off",
            applied=False,
            pass_order=(),
            candidates=(),
            diagnostics=(),
            metadata={"note": "optimization_policy=off"},
        )

    discovered = (
        tuple(passes)
        if passes is not None
        else discover_optimization_passes(
            include_entry_points=include_entry_points,
            include_builtin=True,
            profile=profile,
        )
        or builtin_passes()
    )
    ordered, allow_diags = resolve_pass_order(discovered, profile=profile)
    diagnostics: list[Any] = list(allow_diags)
    production = str(getattr(profile, "security_mode", "development")) == "production"

    context = OptimizationContext(
        baseline=baseline,
        profile=profile,
        evidence=store,
        budgets=dict(budgets or {}),
    )

    raw_candidates: list[OptimizationCandidate] = []
    for pass_obj in ordered:
        pre = pass_obj.metadata.prerequisites
        if pre.requires_evidence_kinds:
            missing = [k for k in pre.requires_evidence_kinds if not store.by_kind(k)]
            if missing:
                diagnostics.append(
                    optimization_diagnostic(
                        "pass_prereq_unmet",
                        f"Pass {pass_obj.metadata.pass_id} missing evidence {missing}",
                        path=("optimization", "prereq", pass_obj.metadata.pass_id),
                    )
                )
                continue
        try:
            proposed = pass_obj.propose(context)
        except Exception as exc:
            diagnostics.append(
                optimization_diagnostic(
                    "pass_prereq_unmet",
                    f"Pass {pass_obj.metadata.pass_id} propose failed: {exc}",
                    severity="error" if production else "warning",
                    path=("optimization", "pass", pass_obj.metadata.pass_id),
                    metadata={"exception_type": type(exc).__name__},
                )
            )
            continue
        raw_candidates.extend(proposed)

    scored, cost_diags = select_candidates(
        tuple(raw_candidates),
        plan=baseline,
        evidence=store,
        provider=cost_provider or RuleCostProvider(),
        budget=budget or CostBudget(limits=dict(budgets or {})),
    )
    diagnostics.extend(cost_diags)

    # Capture would-apply set before shadow-policy demotion (excludes dominated).
    would_apply = tuple(
        c for c in scored if c.decision == "chosen" and not _is_dominated(c)
    )

    # In shadow policy, demote chosen → shadow (do not apply).
    final_candidates: list[OptimizationCandidate] = []
    for candidate in scored:
        if resolved_policy == "shadow" and candidate.decision == "chosen":
            final_candidates.append(
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
                    reason=f"shadow: {candidate.reason}",
                    cost_scores=dict(candidate.cost_scores),
                    hints={
                        **dict(candidate.hints),
                        "would_apply": True,
                    },
                )
            )
        else:
            final_candidates.append(candidate)

    candidates_t = tuple(final_candidates)
    pass_order = tuple(p.metadata.pass_id for p in ordered)
    result_fp = _result_fingerprint(
        baseline_fp=baseline.fingerprint,
        evidence_fp=ev_fp,
        pass_order=pass_order,
        candidates=candidates_t,
        policy=resolved_policy,
    )

    chosen = tuple(c for c in candidates_t if c.decision == "chosen")
    optimized: PipelinePlan | None = None
    plan_diff_dict: dict[str, Any] | None = None
    applied = False
    optimized_fp: str | None = None
    metadata: dict[str, Any] = {}

    if chosen and resolved_policy == "apply_accepted":
        optimized = derive_optimized_plan(baseline, chosen)
        optimized_fp = optimized.fingerprint
        applied = True
        metadata["apply_mode"] = "annotations"
        diff: PlanDiff = diff_plans(baseline, optimized)
        plan_diff_dict = diff.to_dict()
    elif would_apply:
        # Materialize only would-apply candidates for shadow comparison.
        synthetic = tuple(
            OptimizationCandidate(
                candidate_id=c.candidate_id,
                pass_id=c.pass_id,
                rewrite_kind=c.rewrite_kind,
                decision="chosen",
                expected_benefit=dict(c.expected_benefit),
                proofs=c.proofs,
                evidence_refs=c.evidence_refs,
                policy_result=c.policy_result,
                capability_result=c.capability_result,
                reason=c.reason,
                cost_scores=dict(c.cost_scores),
                hints=sanitize_hints(dict(c.hints)),
            )
            for c in would_apply
            if c.policy_result == "accepted"
            and c.capability_result == "supported"
            and all(p.status == "proven" for p in c.proofs)
        )
        if synthetic:
            optimized = derive_optimized_plan(baseline, synthetic)
            optimized_fp = optimized.fingerprint
            plan_diff_dict = diff_plans(baseline, optimized).to_dict()

    # Determinism check + shadow attachment (lazy import avoids cycle).
    from etlantic.optimization.shadow import compare_shadow

    shadow_compare = compare_shadow(baseline, optimized)
    shadow_dict = shadow_compare.to_dict()
    # Re-run fingerprint stability for the same inputs.
    rerun = _result_fingerprint(
        baseline_fp=baseline.fingerprint,
        evidence_fp=ev_fp,
        pass_order=pass_order,
        candidates=candidates_t,
        policy=resolved_policy,
    )
    if rerun != result_fp:
        diagnostics.append(
            optimization_diagnostic(
                "determinism_mismatch",
                "Optimization result fingerprint diverged on recompute",
                severity="error",
                path=("optimization", "determinism"),
            )
        )

    return OptimizationResult(
        schema=OPTIMIZATION_SCHEMA,
        baseline_fingerprint=baseline.fingerprint,
        optimized_fingerprint=optimized_fp,
        result_fingerprint=result_fp,
        evidence_fingerprint=ev_fp,
        policy=resolved_policy,
        applied=applied,
        pass_order=pass_order,
        candidates=candidates_t,
        diagnostics=tuple(diagnostics),
        plan_diff=plan_diff_dict,
        shadow=shadow_dict,
        optimized_plan=optimized,
        metadata=metadata,
    )
