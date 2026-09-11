"""Structural plan diff helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etlantic.plan.adaptive_model import AdaptivePipelinePlan, PlanDocument
from etlantic.plan.model import PipelinePlan


@dataclass
class PlanDiff:
    """Comparison between two resolved pipeline plans."""

    equal: bool
    left_fingerprint: str
    right_fingerprint: str
    changed_steps: list[dict[str, Any]] = field(default_factory=list)
    changed_regions: list[dict[str, Any]] = field(default_factory=list)
    changed_boundaries: list[dict[str, Any]] = field(default_factory=list)
    changed_capability_decisions: list[dict[str, Any]] = field(default_factory=list)
    changed_adaptive: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "equal": self.equal,
            "left_fingerprint": self.left_fingerprint,
            "right_fingerprint": self.right_fingerprint,
            "changed_steps": self.changed_steps,
            "changed_regions": self.changed_regions,
            "changed_boundaries": self.changed_boundaries,
            "changed_capability_decisions": self.changed_capability_decisions,
            "changed_adaptive": self.changed_adaptive,
        }


def _step_signature(plan: PipelinePlan, node_name: str) -> dict[str, Any]:
    impl = plan.implementations.get(node_name)
    unit_id = plan.logical_to_physical.get(node_name)
    unit = next((u for u in plan.physical_units if u.identity == unit_id), None)
    return {
        "node": node_name,
        "engine": unit.engine if unit is not None else None,
        "implementation_kind": impl.kind if impl is not None else None,
        "implementation": impl.to_dict() if impl is not None else None,
    }


def _without_evidence(value: Any) -> Any:
    """Remove explanatory evidence while retaining semantic constraints."""
    if isinstance(value, dict):
        return {
            key: _without_evidence(item)
            for key, item in value.items()
            if key not in {"evidence_refs", "etlantic.handoff_evidence"}
        }
    if isinstance(value, list):
        return [_without_evidence(item) for item in value]
    return value


def diff_plans(left: PlanDocument, right: PlanDocument) -> PlanDiff:
    """Compare two plans for structural differences."""
    if isinstance(left, AdaptivePipelinePlan) or isinstance(
        right, AdaptivePipelinePlan
    ):
        if not isinstance(left, AdaptivePipelinePlan) or not isinstance(
            right, AdaptivePipelinePlan
        ):
            return PlanDiff(
                equal=False,
                left_fingerprint=left.fingerprint,
                right_fingerprint=right.fingerprint,
                changed_adaptive=[
                    {
                        "classification": "semantic",
                        "schema": {"left": left.schema, "right": right.schema},
                    }
                ],
            )
        left_data = left.to_dict()
        right_data = right.to_dict()
        changed: list[dict[str, Any]] = []
        for key in (
            "logical_graph",
            "inventory",
            "candidates",
            "decisions",
            "objective",
            "regions",
            "physical_dag",
            "profile_snapshot",
        ):
            if left_data.get(key) != right_data.get(key):
                left_value = left_data.get(key)
                right_value = right_data.get(key)
                classification = (
                    "explanatory"
                    if key in {"inventory", "candidates", "physical_dag"}
                    and _without_evidence(left_value) == _without_evidence(right_value)
                    else "semantic"
                )
                changed.append(
                    {
                        "classification": classification,
                        "field": key,
                        "left": left_value,
                        "right": right_value,
                    }
                )
        return PlanDiff(
            equal=left.fingerprint == right.fingerprint and not changed,
            left_fingerprint=left.fingerprint,
            right_fingerprint=right.fingerprint,
            changed_adaptive=changed,
        )
    equal_fp = left.fingerprint == right.fingerprint
    left_nodes = {n.name for n in left.logical_graph.nodes}
    right_nodes = {n.name for n in right.logical_graph.nodes}
    all_nodes = sorted(left_nodes | right_nodes)
    changed_steps: list[dict[str, Any]] = []
    for node in all_nodes:
        left_sig = _step_signature(left, node) if node in left_nodes else None
        right_sig = _step_signature(right, node) if node in right_nodes else None
        if left_sig != right_sig:
            changed_steps.append({"node": node, "left": left_sig, "right": right_sig})

    left_regions = [r.to_dict() for r in left.regions]
    right_regions = [r.to_dict() for r in right.regions]
    changed_regions: list[dict[str, Any]] = []
    if left_regions != right_regions:
        changed_regions.append({"left": left_regions, "right": right_regions})

    left_boundaries = [b.to_dict() for b in left.materialization_boundaries]
    right_boundaries = [b.to_dict() for b in right.materialization_boundaries]
    changed_boundaries: list[dict[str, Any]] = []
    if left_boundaries != right_boundaries:
        changed_boundaries.append({"left": left_boundaries, "right": right_boundaries})

    left_caps = [dict(c) for c in left.capability_decisions]
    right_caps = [dict(c) for c in right.capability_decisions]
    changed_caps: list[dict[str, Any]] = []
    if left_caps != right_caps:
        changed_caps.append({"left": left_caps, "right": right_caps})

    equal = (
        equal_fp
        and not changed_steps
        and not changed_regions
        and not changed_boundaries
        and not changed_caps
    )
    return PlanDiff(
        equal=equal,
        left_fingerprint=left.fingerprint,
        right_fingerprint=right.fingerprint,
        changed_steps=changed_steps,
        changed_regions=changed_regions,
        changed_boundaries=changed_boundaries,
        changed_capability_decisions=changed_caps,
    )


def render_plan_explain_human(explain: dict[str, Any]) -> str:
    """Render curated human narrative from explain_plan output."""
    lines: list[str] = []
    lines.append(f"plan_id: {explain.get('plan_id')}")
    lines.append(f"fingerprint: {explain.get('fingerprint')}")
    lines.append(f"profile: {explain.get('profile')}")
    lines.append("")
    lines.append("Capability decisions:")
    for item in explain.get("capability_decisions") or []:
        lines.append(
            f"  - {item.get('requirement')}: {item.get('decision')} "
            f"(engine={item.get('engine')}, fallback={item.get('fallback_engine')})"
        )
        if item.get("message"):
            lines.append(f"    why: {item['message']}")
    lines.append("")
    lines.append("Materialization boundaries:")
    for boundary in explain.get("materialization_boundaries") or []:
        lines.append(
            f"  - {boundary.get('node')}: {boundary.get('reason')} "
            f"({boundary.get('strategy')})"
        )
    lines.append("")
    lines.append("Steps:")
    for step in explain.get("steps") or []:
        lines.append(
            f"  - {step.get('node')} [{step.get('kind')}]: engine={step.get('engine')}, "
            f"implementation={step.get('implementation_kind')}"
        )
        impl = step.get("implementation") or {}
        if impl.get("fallback_reason"):
            lines.append(f"    fallback: {impl['fallback_reason']}")
        compiler = step.get("compiler") or {}
        if compiler.get("selection_reason"):
            lines.append(f"    compiler: {compiler.get('selection_reason')}")
    return "\n".join(lines)
