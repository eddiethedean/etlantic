"""Human/machine optimization explanation artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from etlantic.optimization.engine import OptimizationResult
from etlantic.plan.freeze import mutable_copy


@dataclass(frozen=True, slots=True)
class OptimizationExplanation:
    """Stable explanation schema shared by CLI, API, and IDE."""

    schema: str
    baseline_fingerprint: str
    optimized_fingerprint: str | None
    result_fingerprint: str
    policy: str
    applied: bool
    pass_order: tuple[str, ...]
    chosen: tuple[dict[str, Any], ...]
    rejected: tuple[dict[str, Any], ...]
    shadowed: tuple[dict[str, Any], ...]
    diagnostics: tuple[dict[str, Any], ...]
    plan_diff: dict[str, Any] | None
    expected_benefit_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "baseline_fingerprint": self.baseline_fingerprint,
            "optimized_fingerprint": self.optimized_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "policy": self.policy,
            "applied": self.applied,
            "pass_order": list(self.pass_order),
            "chosen": mutable_copy(list(self.chosen)),
            "rejected": mutable_copy(list(self.rejected)),
            "shadowed": mutable_copy(list(self.shadowed)),
            "diagnostics": mutable_copy(list(self.diagnostics)),
            "plan_diff": mutable_copy(self.plan_diff) if self.plan_diff else None,
            "expected_benefit_summary": mutable_copy(self.expected_benefit_summary),
        }


def explain_optimization(result: OptimizationResult) -> OptimizationExplanation:
    """Project an OptimizationResult into the shared explanation schema."""
    chosen = []
    rejected = []
    shadowed = []
    benefit_acc: dict[str, float] = {}
    for candidate in result.candidates:
        payload = candidate.to_dict()
        if candidate.decision == "chosen":
            chosen.append(payload)
            for key, value in (candidate.expected_benefit or {}).items():
                try:
                    benefit_acc[str(key)] = benefit_acc.get(str(key), 0.0) + float(
                        value
                    )
                except (TypeError, ValueError):
                    continue
        elif candidate.decision == "shadow":
            shadowed.append(payload)
        else:
            rejected.append(payload)

    diagnostics = tuple(
        d.to_dict() if hasattr(d, "to_dict") else dict(d) for d in result.diagnostics
    )
    return OptimizationExplanation(
        schema=result.schema,
        baseline_fingerprint=result.baseline_fingerprint,
        optimized_fingerprint=result.optimized_fingerprint,
        result_fingerprint=result.result_fingerprint,
        policy=result.policy,
        applied=result.applied,
        pass_order=result.pass_order,
        chosen=tuple(chosen),
        rejected=tuple(rejected),
        shadowed=tuple(shadowed),
        diagnostics=diagnostics,
        plan_diff=result.plan_diff,
        expected_benefit_summary=benefit_acc,
    )
