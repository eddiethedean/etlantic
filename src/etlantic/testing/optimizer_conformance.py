"""Optimizer pass conformance suite (0.45)."""

from __future__ import annotations

from etlantic.optimization.cost import CostBudget, RuleCostProvider
from etlantic.optimization.engine import optimize_plan
from etlantic.optimization.evidence import EvidenceRecord, EvidenceStore
from etlantic.optimization.protocol import OptimizationPass
from etlantic.optimization.shadow import ShadowThresholds, compare_shadow
from etlantic.plan.model import PLAN_SCHEMA, PipelinePlan
from etlantic.plan.serialize import plan_fingerprint
from etlantic.profile import Profile, development_profile


def _minimal_plan(*, fingerprint: str = "pending") -> PipelinePlan:
    from etlantic.model import LogicalGraph, Node, NodeKind

    nodes = (
        Node(name="extract", kind=NodeKind.SOURCE, identity="extract"),
        Node(name="transform", kind=NodeKind.STEP, identity="transform"),
        Node(name="load", kind=NodeKind.SINK, identity="load"),
    )
    graph = LogicalGraph(
        pipeline_id="opt-conformance",
        pipeline_name="OptConformance",
        nodes=nodes,
        edges=(),
    )
    plan = PipelinePlan(
        schema=PLAN_SCHEMA,
        plan_id="opt-conformance",
        pipeline_id="opt-conformance",
        pipeline_name="OptConformance",
        profile_name="development",
        fingerprint=fingerprint,
        logical_graph=graph,
        metadata={
            "etlantic.statistics": {"extract": {"kind": "cardinality", "value": 100}}
        },
    )
    fp = plan_fingerprint(plan)
    object.__setattr__(plan, "fingerprint", fp)
    return plan


def run_optimizer_conformance_suite(
    pass_obj: OptimizationPass,
    *,
    profile: Profile | None = None,
) -> None:
    """Assert a pass is deterministic, proof-gated, and non-authoritative.

    Raises:
        AssertionError: When a conformance check fails.
    """
    profile = profile or development_profile(
        optimization_policy="shadow",
        optimization_pass_allowlist={
            pass_obj.metadata.pass_id: pass_obj.metadata.version
        },
    )
    baseline = _minimal_plan()
    evidence = EvidenceStore.from_plan(baseline)
    evidence.add(
        EvidenceRecord(
            evidence_id="conformance-card",
            kind="cardinality",
            subject="extract",
            value=100,
            confidence=0.9,
            provenance="conformance",
        )
    )

    first = optimize_plan(
        baseline,
        profile=profile,
        evidence=evidence,
        passes=(pass_obj,),
        cost_provider=RuleCostProvider(),
        budget=CostBudget(),
        include_entry_points=False,
    )
    second = optimize_plan(
        baseline,
        profile=profile,
        evidence=evidence,
        passes=(pass_obj,),
        cost_provider=RuleCostProvider(),
        budget=CostBudget(),
        include_entry_points=False,
    )
    assert first.result_fingerprint == second.result_fingerprint, (
        "optimizer pass must be deterministic for identical plan+evidence"
    )
    assert first.baseline_fingerprint == baseline.fingerprint

    for candidate in first.candidates:
        assert candidate.candidate_id
        assert candidate.pass_id == pass_obj.metadata.pass_id
        assert candidate.reason
        assert candidate.policy_result in {"accepted", "rejected", "not_evaluated"}
        assert candidate.capability_result in {"supported", "unsupported", "unknown"}
        if candidate.decision == "chosen":
            assert candidate.proofs, "chosen candidates require proof obligations"
            assert all(p.status == "proven" for p in candidate.proofs), (
                "chosen candidates must have proven proofs"
            )

    # Passes must not mutate the baseline fingerprint by side effect.
    # Passes must not mutate the baseline content fingerprint.
    assert baseline.fingerprint == plan_fingerprint(baseline)

    shadow = compare_shadow(
        baseline,
        first.optimized_plan,
        thresholds=ShadowThresholds(),
        result=first,
    )
    assert isinstance(shadow.passed, bool)
    assert shadow.baseline_fingerprint == baseline.fingerprint

    # Production allowlist fail-closed: undeclared pass rejected.
    prod = Profile(
        name="production",
        security_mode="production",
        plugin_allowlist={"local": None},
        optimization_policy="shadow",
        optimization_pass_allowlist={},
    )
    denied = optimize_plan(
        baseline,
        profile=prod,
        evidence=evidence,
        passes=(pass_obj,),
        include_entry_points=False,
    )
    assert pass_obj.metadata.pass_id not in denied.pass_order
    assert any(
        getattr(d, "code", None) == "PMOPT140"
        or (isinstance(d, dict) and d.get("code") == "PMOPT140")
        for d in denied.diagnostics
    )


__all__ = ["run_optimizer_conformance_suite"]
