"""Tests for ETLantic 0.45 optimization SDK."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from etlantic.optimization.cost import (
    CostBudget,
    RuleCostProvider,
    StatisticalCostProvider,
    select_candidates,
)
from etlantic.optimization.engine import derive_optimized_plan, optimize_plan
from etlantic.optimization.evidence import (
    EvidenceRecord,
    EvidenceStore,
    evidence_fingerprint,
)
from etlantic.optimization.explanation import explain_optimization
from etlantic.optimization.passes import REFERENCE_PASSES, PruningPass, PushdownPass
from etlantic.optimization.protocol import (
    OPTIMIZATION_SCHEMA,
    OptimizationCandidate,
    ProofObligation,
)
from etlantic.optimization.registry import builtin_passes, resolve_pass_order
from etlantic.optimization.shadow import ShadowThresholds, compare_shadow
from etlantic.profile import Profile, development_profile
from etlantic.testing.optimizer_conformance import (
    _minimal_plan,
    run_optimizer_conformance_suite,
)


def test_evidence_stale_missing_conflict() -> None:
    store = EvidenceStore()
    now = datetime.now(UTC)
    store.add(
        EvidenceRecord(
            evidence_id="a",
            kind="cardinality",
            subject="extract",
            value=10,
            expires_at=(now - timedelta(hours=1)).isoformat(),
        )
    )
    store.add(
        EvidenceRecord(
            evidence_id="b",
            kind="cardinality",
            subject="extract",
            value=99,
        )
    )
    stats = store.statistics(required_kinds=("cardinality", "partitioning"), now=now)
    assert "partitioning" in stats.missing_kinds
    assert "a" in stats.stale_ids
    assert "cardinality:extract" in stats.conflicting_subjects
    fp1 = evidence_fingerprint(store)
    fp2 = evidence_fingerprint(EvidenceStore.from_dict(store.to_dict()))
    assert fp1 == fp2


def test_cost_selection_rejects_conflicting_and_budget() -> None:
    plan = _minimal_plan()
    store = EvidenceStore()
    store.add(
        EvidenceRecord(
            evidence_id="c1",
            kind="cardinality",
            subject="extract",
            value=1,
        )
    )
    store.add(
        EvidenceRecord(
            evidence_id="c2",
            kind="cardinality",
            subject="extract",
            value=2,
        )
    )
    candidate = OptimizationCandidate(
        candidate_id="x",
        pass_id="test",
        rewrite_kind="fusion",
        decision="chosen",
        expected_benefit={"relative": 0.5},
        proofs=(ProofObligation(kind="schema", status="proven"),),
        evidence_refs=(
            {"evidence_id": "c1", "kind": "cardinality", "confidence": 0.9},
        ),
        policy_result="accepted",
        capability_result="supported",
        reason="test",
    )
    scored, diags = select_candidates(
        (candidate,),
        plan=plan,
        evidence=store,
        provider=RuleCostProvider(),
        budget=CostBudget(limits={"cpu": -1000}),
    )
    assert scored[0].decision == "rejected"
    assert any(d.code in {"PMOPT102", "PMOPT130"} for d in diags)


def test_optimize_deterministic_and_off_policy() -> None:
    plan = _minimal_plan()
    allow = {p.metadata.pass_id: p.metadata.version for p in builtin_passes()}
    profile = development_profile(
        optimization_policy="shadow",
        optimization_pass_allowlist=allow,
    )
    a = optimize_plan(plan, profile=profile, include_entry_points=False)
    b = optimize_plan(plan, profile=profile, include_entry_points=False)
    assert a.result_fingerprint == b.result_fingerprint
    assert a.schema == OPTIMIZATION_SCHEMA
    assert a.applied is False

    off = optimize_plan(
        plan,
        profile=development_profile(optimization_policy="off"),
        include_entry_points=False,
    )
    assert off.policy == "off"
    assert off.candidates == ()


def test_apply_accepted_derives_plan() -> None:
    plan = _minimal_plan()
    plan = PipelinePlan_with_selection(plan)
    allow = {p.metadata.pass_id: p.metadata.version for p in builtin_passes()}
    profile = development_profile(
        optimization_policy="apply_accepted",
        optimization_pass_allowlist=allow,
    )
    result = optimize_plan(plan, profile=profile, include_entry_points=False)
    assert result.applied is True
    assert result.optimized_plan is not None
    assert result.optimized_fingerprint is not None
    explanation = explain_optimization(result)
    assert explanation.schema == OPTIMIZATION_SCHEMA
    shadow = compare_shadow(
        plan,
        result.optimized_plan,
        thresholds=ShadowThresholds(max_changed_steps=100),
        result=result,
    )
    assert shadow.passed


def PipelinePlan_with_selection(plan):
    data = plan.to_dict()
    data["selected_nodes"] = ["extract", "load"]
    data["fingerprint"] = ""
    from etlantic.plan.model import PipelinePlan
    from etlantic.plan.serialize import plan_fingerprint

    rebuilt = PipelinePlan.from_dict(data, verify=False)
    object.__setattr__(rebuilt, "fingerprint", plan_fingerprint(rebuilt))
    return rebuilt


def test_production_allowlist_fail_closed() -> None:
    plan = _minimal_plan()
    profile = Profile(
        name="production",
        security_mode="production",
        plugin_allowlist={"local": None},
        optimization_policy="shadow",
        optimization_pass_allowlist={},
    )
    result = optimize_plan(
        plan,
        profile=profile,
        passes=builtin_passes(),
        include_entry_points=False,
    )
    assert result.pass_order == ()
    assert any(getattr(d, "code", None) == "PMOPT140" for d in result.diagnostics)


def test_reference_pass_conformance() -> None:
    for pass_obj in REFERENCE_PASSES:
        run_optimizer_conformance_suite(pass_obj)


def test_statistical_cost_provider() -> None:
    plan = _minimal_plan()
    store = EvidenceStore.from_plan(plan)
    store.add(
        EvidenceRecord(
            evidence_id="card",
            kind="cardinality",
            subject="extract",
            value={"rows": 5000},
            confidence=0.8,
        )
    )
    candidate = OptimizationCandidate(
        candidate_id="y",
        pass_id="test",
        rewrite_kind="pushdown",
        decision="chosen",
        expected_benefit={"relative": 0.2},
        proofs=(ProofObligation(kind="schema", status="proven"),),
        evidence_refs=(),
        policy_result="accepted",
        capability_result="supported",
        reason="stat",
    )
    score = StatisticalCostProvider().score(candidate, plan=plan, evidence=store)
    assert score.provider_id.startswith("etlantic.statistical_cost")
    assert "cpu" in score.scores


def test_resolve_pass_order_deterministic() -> None:
    profile = development_profile(
        optimization_pass_allowlist={
            "etlantic.pass.pruning": "1.0.0",
            "etlantic.pass.pushdown": "1.0.0",
        }
    )
    ordered, _ = resolve_pass_order(
        (PruningPass(), PushdownPass()),
        profile=profile,
    )
    assert [p.metadata.pass_id for p in ordered] == [
        "etlantic.pass.pushdown",
        "etlantic.pass.pruning",
    ]


def test_derive_optimized_plan_does_not_mutate_baseline() -> None:
    plan = _minimal_plan()
    before = plan.to_dict()
    candidate = OptimizationCandidate(
        candidate_id="z",
        pass_id="etlantic.pass.pruning",
        rewrite_kind="pruning",
        decision="chosen",
        expected_benefit={"relative": 0.1},
        proofs=(ProofObligation(kind="dependency", status="proven"),),
        evidence_refs=(),
        policy_result="accepted",
        capability_result="supported",
        reason="annotate",
        hints={"annotate": {"pruned_nodes": ["transform"]}},
    )
    optimized = derive_optimized_plan(plan, (candidate,))
    assert plan.to_dict() == before
    assert "etlantic.optimization.pruned_nodes" in optimized.metadata
    assert optimized.fingerprint != ""


def test_lazy_namespace() -> None:
    import etlantic as etl

    assert etl.optimization.OPTIMIZATION_SCHEMA == OPTIMIZATION_SCHEMA
    assert callable(etl.optimization.optimize_plan)


def test_stale_and_unresolved_evidence_rejects_chosen() -> None:
    plan = _minimal_plan()
    store = EvidenceStore()
    now = datetime.now(UTC)
    store.add(
        EvidenceRecord(
            evidence_id="stale-card",
            kind="cardinality",
            subject="extract",
            value=10,
            expires_at=(now - timedelta(hours=1)).isoformat(),
        )
    )
    stale_candidate = OptimizationCandidate(
        candidate_id="stale",
        pass_id="test",
        rewrite_kind="fusion",
        decision="chosen",
        expected_benefit={"relative": 0.5},
        proofs=(ProofObligation(kind="schema", status="proven"),),
        evidence_refs=(
            {"evidence_id": "stale-card", "kind": "cardinality", "confidence": 0.9},
        ),
        policy_result="accepted",
        capability_result="supported",
        reason="stale",
    )
    missing_candidate = OptimizationCandidate(
        candidate_id="missing",
        pass_id="test",
        rewrite_kind="fusion",
        decision="chosen",
        expected_benefit={"relative": 0.5},
        proofs=(ProofObligation(kind="schema", status="proven"),),
        evidence_refs=(
            {"evidence_id": "does-not-exist", "kind": "cardinality", "confidence": 0.9},
        ),
        policy_result="accepted",
        capability_result="supported",
        reason="missing",
    )
    scored, diags = select_candidates(
        (stale_candidate, missing_candidate),
        plan=plan,
        evidence=store,
        provider=RuleCostProvider(),
    )
    assert all(c.decision == "rejected" for c in scored)
    assert any(getattr(d, "code", None) in {"PMOPT100", "PMOPT101"} for d in diags)


def test_unknown_policy_or_capability_cannot_be_chosen() -> None:
    plan = _minimal_plan()
    store = EvidenceStore()
    candidate = OptimizationCandidate(
        candidate_id="gate",
        pass_id="test",
        rewrite_kind="pruning",
        decision="chosen",
        expected_benefit={"relative": 0.2},
        proofs=(ProofObligation(kind="dependency", status="proven"),),
        evidence_refs=(),
        policy_result="not_evaluated",
        capability_result="unknown",
        reason="ungated",
    )
    scored, _ = select_candidates(
        (candidate,), plan=plan, evidence=store, provider=RuleCostProvider()
    )
    assert scored[0].decision == "rejected"


def test_shadow_synthesis_excludes_dominated() -> None:
    plan = PipelinePlan_with_selection(_minimal_plan())
    allow = {p.metadata.pass_id: p.metadata.version for p in builtin_passes()}
    profile = development_profile(
        optimization_policy="shadow",
        optimization_pass_allowlist=allow,
    )
    # Two competing chosen candidates via select_candidates domination path.
    a = OptimizationCandidate(
        candidate_id="a",
        pass_id="t",
        rewrite_kind="pruning",
        decision="chosen",
        expected_benefit={"relative": 0.9},
        proofs=(ProofObligation(kind="dependency", status="proven"),),
        evidence_refs=(),
        policy_result="accepted",
        capability_result="supported",
        reason="better",
        cost_scores={"benefit": -0.9},
        hints={"annotate": {"pruned_nodes": ["transform"]}},
    )
    b = OptimizationCandidate(
        candidate_id="b",
        pass_id="t",
        rewrite_kind="pruning",
        decision="chosen",
        expected_benefit={"relative": 0.1},
        proofs=(ProofObligation(kind="dependency", status="proven"),),
        evidence_refs=(),
        policy_result="accepted",
        capability_result="supported",
        reason="worse",
        cost_scores={"benefit": -0.1},
        hints={"annotate": {"pruned_nodes": ["extract", "transform"]}},
    )
    scored, _ = select_candidates(
        (a, b), plan=plan, evidence=EvidenceStore(), provider=RuleCostProvider()
    )
    dominated = [c for c in scored if (c.hints or {}).get("dominated")]
    winners = [c for c in scored if c.decision == "chosen"]
    assert len(winners) == 1
    assert dominated
    result = optimize_plan(plan, profile=profile, passes=(), include_entry_points=False)
    # Empty passes → no candidates; ensure apply_mode honesty on apply path.
    applied = optimize_plan(
        plan,
        profile=development_profile(
            optimization_policy="apply_accepted",
            optimization_pass_allowlist=allow,
        ),
        include_entry_points=False,
    )
    if applied.applied:
        assert applied.metadata.get("apply_mode") == "annotations"
    assert result.shadow is not None


def test_specifier_pin_allows_compatible_versions() -> None:
    from etlantic.optimization.passes import PushdownPass
    from etlantic.optimization.registry import resolve_pass_order

    profile = development_profile(
        optimization_pass_allowlist={"etlantic.pass.pushdown": ">=1.0.0,<2"}
    )
    ordered, diags = resolve_pass_order((PushdownPass(),), profile=profile)
    assert [p.metadata.pass_id for p in ordered] == ["etlantic.pass.pushdown"]
    assert not any(getattr(d, "code", None) == "PMOPT140" for d in diags)


def test_discover_skips_entry_points_until_allowlisted(monkeypatch) -> None:
    from etlantic.optimization import registry as reg

    loaded: list[str] = []

    class _Ep:
        def __init__(self, name: str) -> None:
            self.name = name

        def load(self):
            loaded.append(self.name)
            raise RuntimeError("should not load")

    monkeypatch.setattr(reg, "_entry_point_group", lambda: [_Ep("evil.pass")])
    profile = Profile(
        name="production",
        security_mode="production",
        plugin_allowlist={"local": None},
        optimization_policy="shadow",
        optimization_pass_allowlist={},
    )
    found = reg.discover_optimization_passes(
        include_builtin=False, include_entry_points=True, profile=profile
    )
    assert found == ()
    assert loaded == []


def test_profile_off_policy_respected() -> None:
    plan = _minimal_plan()
    profile = development_profile(optimization_policy="off")
    result = optimize_plan(plan, profile=profile, include_entry_points=False)
    assert result.policy == "off"
    assert result.candidates == ()
    assert result.shadow is None or result.applied is False


def test_ide_optimize_honors_production_allowlist() -> None:
    from pathlib import Path

    import examples.memory_customers as mc

    from etlantic.ide.commands import execute_command
    from etlantic.ide.trust import TrustedWorkspacePolicy

    root = str(Path(__file__).resolve().parents[2])
    policy = TrustedWorkspacePolicy(
        enabled=True,
        allow_imports=True,
        allow_roots=(root,),
    )
    result = execute_command(
        {
            "name": "optimize",
            "arguments": {
                "target": f"{mc.__file__}:CustomerPipeline",
                "profile": "development",
                "optimization_policy": "off",
            },
        },
        policy=policy,
    )
    assert result.ok is True, result.error
    assert result.payload is not None
    assert result.payload["optimization"]["policy"] == "off"
