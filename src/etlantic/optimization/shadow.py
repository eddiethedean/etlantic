"""Shadow comparison of baseline vs optimized plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etlantic.optimization.diagnostics import optimization_diagnostic
from etlantic.optimization.engine import OptimizationResult
from etlantic.plan.diff import diff_plans
from etlantic.plan.model import PipelinePlan


@dataclass(frozen=True, slots=True)
class ShadowThresholds:
    """Regression thresholds for shadow comparison."""

    max_changed_steps: int | None = None
    max_changed_regions: int | None = None
    max_changed_boundaries: int | None = None
    require_equal_logical_nodes: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_changed_steps": self.max_changed_steps,
            "max_changed_regions": self.max_changed_regions,
            "max_changed_boundaries": self.max_changed_boundaries,
            "require_equal_logical_nodes": self.require_equal_logical_nodes,
        }


@dataclass(frozen=True, slots=True)
class ShadowCompareResult:
    """Outcome of comparing baseline and candidate plans."""

    passed: bool
    baseline_fingerprint: str
    candidate_fingerprint: str | None
    plan_diff: dict[str, Any]
    regressions: tuple[str, ...] = ()
    diagnostics: tuple[Any, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "baseline_fingerprint": self.baseline_fingerprint,
            "candidate_fingerprint": self.candidate_fingerprint,
            "plan_diff": dict(self.plan_diff),
            "regressions": list(self.regressions),
            "diagnostics": [
                d.to_dict() if hasattr(d, "to_dict") else dict(d)
                for d in self.diagnostics
            ],
            "metadata": dict(self.metadata),
        }


def compare_shadow(
    baseline: PipelinePlan,
    candidate: PipelinePlan | None,
    *,
    thresholds: ShadowThresholds | None = None,
    result: OptimizationResult | None = None,
) -> ShadowCompareResult:
    """Compare baseline and optimized plans against regression thresholds.

    Plan-only by default. Does not execute pipelines.
    """
    thresholds = thresholds or ShadowThresholds()
    if candidate is None:
        diff = {
            "equal": True,
            "left_fingerprint": baseline.fingerprint,
            "right_fingerprint": None,
            "changed_steps": [],
            "changed_regions": [],
            "changed_boundaries": [],
            "changed_capability_decisions": [],
        }
        return ShadowCompareResult(
            passed=True,
            baseline_fingerprint=baseline.fingerprint,
            candidate_fingerprint=None,
            plan_diff=diff,
            metadata={"note": "no candidate plan"},
        )

    plan_diff = diff_plans(baseline, candidate).to_dict()
    regressions: list[str] = []
    diagnostics: list[Any] = []

    if thresholds.require_equal_logical_nodes:
        left = {n.name for n in baseline.logical_graph.nodes}
        right = {n.name for n in candidate.logical_graph.nodes}
        # Allow pruning annotations but logical graph identity should match unless pruning applied.
        opt_meta = (candidate.metadata or {}).get("etlantic.optimization.pruned_nodes")
        if opt_meta is None and left != right:
            regressions.append("logical_node_set_changed")

    if (
        thresholds.max_changed_steps is not None
        and len(plan_diff.get("changed_steps") or []) > thresholds.max_changed_steps
    ):
        regressions.append("too_many_changed_steps")
    if (
        thresholds.max_changed_regions is not None
        and len(plan_diff.get("changed_regions") or []) > thresholds.max_changed_regions
    ):
        regressions.append("too_many_changed_regions")
    if (
        thresholds.max_changed_boundaries is not None
        and len(plan_diff.get("changed_boundaries") or [])
        > thresholds.max_changed_boundaries
    ):
        regressions.append("too_many_changed_boundaries")

    if result is not None:
        for candidate_rec in result.candidates:
            if candidate_rec.decision == "chosen" and any(
                p.status != "proven" for p in candidate_rec.proofs
            ):
                regressions.append(f"unproven:{candidate_rec.candidate_id}")

    passed = not regressions
    if not passed:
        diagnostics.append(
            optimization_diagnostic(
                "shadow_regression",
                f"Shadow comparison regressions: {', '.join(regressions)}",
                severity="error",
                path=("optimization", "shadow"),
                metadata={"regressions": list(regressions)},
            )
        )

    return ShadowCompareResult(
        passed=passed,
        baseline_fingerprint=baseline.fingerprint,
        candidate_fingerprint=candidate.fingerprint,
        plan_diff=plan_diff,
        regressions=tuple(regressions),
        diagnostics=tuple(diagnostics),
        metadata={"thresholds": thresholds.to_dict()},
    )
