"""Built-in reference optimization passes (045-R)."""

from __future__ import annotations

from typing import Any

from etlantic.optimization.protocol import (
    OptimizationCandidate,
    OptimizationContext,
    PassMetadata,
    PassPrerequisites,
    ProofObligation,
)


def _base_proofs(
    *kinds: str, detail: str = "boundary preserved"
) -> tuple[ProofObligation, ...]:
    return tuple(
        ProofObligation(kind=kind, status="proven", detail=detail, boundaries=(kind,))
        for kind in kinds
    )


def _reject(
    *,
    pass_id: str,
    candidate_id: str,
    rewrite_kind: str,
    reason: str,
    capability: str = "unsupported",
) -> OptimizationCandidate:
    return OptimizationCandidate(
        candidate_id=candidate_id,
        pass_id=pass_id,
        rewrite_kind=rewrite_kind,
        decision="rejected",
        expected_benefit={},
        proofs=(
            ProofObligation(
                kind="boundary",
                status="rejected",
                detail=reason,
                boundaries=("capability",),
            ),
        ),
        evidence_refs=(),
        policy_result="rejected",
        capability_result=capability,  # type: ignore[arg-type]
        reason=reason,
    )


def _resolved_evidence_refs(
    context: OptimizationContext,
    *specs: tuple[str, str, float],
) -> tuple[dict[str, Any], ...]:
    """Include only evidence refs that resolve in the store."""
    refs: list[dict[str, Any]] = []
    for evidence_id, kind, confidence in specs:
        record = context.evidence.get(evidence_id)
        if record is None:
            continue
        refs.append(
            {
                "evidence_id": evidence_id,
                "kind": kind or record.kind,
                "confidence": confidence,
            }
        )
    return tuple(refs)


class _BasePass:
    metadata: PassMetadata

    def _prereq_ok(self, context: OptimizationContext) -> bool:
        pre = self.metadata.prerequisites
        plan = context.baseline
        if len(plan.logical_graph.nodes) < pre.min_nodes:
            return False
        if pre.requires_engines:
            engines = {r.engine for r in plan.regions}
            if not set(pre.requires_engines) & engines:
                return False
        if pre.requires_evidence_kinds:
            for kind in pre.requires_evidence_kinds:
                if not context.evidence.by_kind(kind):
                    return False
        return True


class PushdownPass(_BasePass):
    """Propose filter/projection pushdown when connector capability allows."""

    metadata = PassMetadata(
        pass_id="etlantic.pass.pushdown",
        version="1.0.0",
        rewrite_kinds=("pushdown",),
        priority=10,
        prerequisites=PassPrerequisites(min_nodes=1),
        description="Push filters/projections toward sources when supported",
    )

    def propose(
        self, context: OptimizationContext
    ) -> tuple[OptimizationCandidate, ...]:
        plan = context.baseline
        candidates: list[OptimizationCandidate] = []
        for decision in plan.capability_decisions:
            if not isinstance(decision, dict):
                continue
            caps = decision.get("capabilities") or decision
            if not isinstance(caps, dict):
                continue
            supported = bool(
                caps.get("source.filter_pushdown")
                or caps.get("source.projection_pushdown")
                or caps.get("pushdown")
            )
            node = str(decision.get("node") or decision.get("binding") or "source")
            if not supported:
                candidates.append(
                    _reject(
                        pass_id=self.metadata.pass_id,
                        candidate_id=f"pushdown-reject:{node}",
                        rewrite_kind="pushdown",
                        reason="connector does not advertise pushdown capability",
                    )
                )
                continue
            candidates.append(
                OptimizationCandidate(
                    candidate_id=f"pushdown:{node}",
                    pass_id=self.metadata.pass_id,
                    rewrite_kind="pushdown",
                    decision="chosen",
                    expected_benefit={"relative": 0.4, "kind": "io"},
                    proofs=_base_proofs("schema", "ordering", "side_effect"),
                    evidence_refs=(),  # justified by plan capability_decisions
                    policy_result="accepted",
                    capability_result="supported",
                    reason="connector advertises pushdown",
                    hints={"annotate": {"pushdown_nodes": [node]}},
                )
            )
        if not candidates and self._prereq_ok(context):
            # No capability evidence: safe no-op reject rather than invent pushdown.
            candidates.append(
                _reject(
                    pass_id=self.metadata.pass_id,
                    candidate_id="pushdown-none",
                    rewrite_kind="pushdown",
                    reason="no pushdown capability evidence on plan",
                    capability="unknown",
                )
            )
        return tuple(candidates)


class PruningPass(_BasePass):
    """Propose pruning of unused logical branches when selection is present."""

    metadata = PassMetadata(
        pass_id="etlantic.pass.pruning",
        version="1.0.0",
        rewrite_kinds=("pruning",),
        priority=20,
        description="Prune unused nodes outside selected closure",
    )

    def propose(
        self, context: OptimizationContext
    ) -> tuple[OptimizationCandidate, ...]:
        plan = context.baseline
        if plan.selected_nodes is None:
            return (
                OptimizationCandidate(
                    candidate_id="pruning-skip",
                    pass_id=self.metadata.pass_id,
                    rewrite_kind="pruning",
                    decision="rejected",
                    expected_benefit={},
                    proofs=_base_proofs("dependency"),
                    evidence_refs=(),
                    policy_result="accepted",
                    capability_result="supported",
                    reason="full graph selected; nothing to prune",
                ),
            )
        all_nodes = {n.name for n in plan.logical_graph.nodes}
        unused = sorted(all_nodes - set(plan.selected_nodes))
        if not unused:
            return ()
        return (
            OptimizationCandidate(
                candidate_id="pruning:selected",
                pass_id=self.metadata.pass_id,
                rewrite_kind="pruning",
                decision="chosen",
                expected_benefit={"relative": 0.3, "nodes_removed": len(unused)},
                proofs=_base_proofs("dependency", "schema"),
                evidence_refs=(),  # justified by plan.selected_nodes
                policy_result="accepted",
                capability_result="supported",
                reason=f"prune {len(unused)} nodes outside selection",
                hints={"annotate": {"pruned_nodes": unused}},
            ),
        )


class FusionPass(_BasePass):
    """Promote existing sql/spark fusion evidence into an accepted rewrite hint."""

    metadata = PassMetadata(
        pass_id="etlantic.pass.fusion",
        version="1.0.0",
        rewrite_kinds=("fusion",),
        priority=30,
        description="Fuse adjacent same-engine units when plan metadata allows",
    )

    def propose(
        self, context: OptimizationContext
    ) -> tuple[OptimizationCandidate, ...]:
        plan = context.baseline
        meta = dict(plan.metadata or {})
        fusion = {}
        if meta.get("sql_fusion"):
            fusion["sql_fusion"] = meta["sql_fusion"]
        if meta.get("spark_fusion"):
            fusion["spark_fusion"] = meta["spark_fusion"]
        if not fusion:
            fusion_ev = context.evidence.get("plan-fusion")
            if fusion_ev is not None:
                fusion = dict(fusion_ev.value or {})
        if not fusion:
            return (
                OptimizationCandidate(
                    candidate_id="fusion-none",
                    pass_id=self.metadata.pass_id,
                    rewrite_kind="fusion",
                    decision="rejected",
                    expected_benefit={},
                    proofs=_base_proofs("ordering"),
                    evidence_refs=(),
                    policy_result="accepted",
                    capability_result="supported",
                    reason="no same-engine fusion evidence",
                ),
            )
        # Reject cross-engine fusion attempts.
        engines = {r.engine for r in plan.regions}
        if len(engines) > 1 and "cross_engine" in str(fusion):
            return (
                _reject(
                    pass_id=self.metadata.pass_id,
                    candidate_id="fusion-cross-engine",
                    rewrite_kind="fusion",
                    reason="refusing cross-engine fusion without proof",
                ),
            )
        return (
            OptimizationCandidate(
                candidate_id="fusion:metadata",
                pass_id=self.metadata.pass_id,
                rewrite_kind="fusion",
                decision="chosen",
                expected_benefit={"relative": 0.25},
                proofs=_base_proofs("ordering", "schema", "side_effect"),
                evidence_refs=_resolved_evidence_refs(
                    context, ("plan-fusion", "ordering", 0.7)
                ),
                policy_result="accepted",
                capability_result="supported",
                reason="same-engine fusion evidence present",
                hints={"annotate": {"fusion": fusion}},
            ),
        )


class MaterializationPass(_BasePass):
    """Cost-aware materialization boundary reinforcement."""

    metadata = PassMetadata(
        pass_id="etlantic.pass.materialization",
        version="1.0.0",
        rewrite_kinds=("materialization",),
        priority=40,
        description="Reinforce durable materialization where reuse/fan-out requires it",
    )

    def propose(
        self, context: OptimizationContext
    ) -> tuple[OptimizationCandidate, ...]:
        plan = context.baseline
        reusable = [
            b
            for b in plan.materialization_boundaries
            if b.reason in {"fan_out_reuse", "cross_engine", "sink_publication"}
        ]
        if not reusable:
            return (
                OptimizationCandidate(
                    candidate_id="materialization-none",
                    pass_id=self.metadata.pass_id,
                    rewrite_kind="materialization",
                    decision="rejected",
                    expected_benefit={},
                    proofs=_base_proofs("idempotency", "side_effect"),
                    evidence_refs=(),
                    policy_result="accepted",
                    capability_result="supported",
                    reason="no materialization candidates",
                ),
            )
        ids = [b.identity for b in reusable]
        return (
            OptimizationCandidate(
                candidate_id="materialization:boundaries",
                pass_id=self.metadata.pass_id,
                rewrite_kind="materialization",
                decision="chosen",
                expected_benefit={"relative": 0.35, "boundaries": len(ids)},
                proofs=_base_proofs("idempotency", "side_effect", "ordering"),
                evidence_refs=tuple(
                    ref
                    for identity in ids
                    for ref in _resolved_evidence_refs(
                        context, (f"boundary:{identity}", "reuse", 0.8)
                    )
                ),
                policy_result="accepted",
                capability_result="supported",
                reason="reinforce durable handoff boundaries",
                hints={"annotate": {"materialize": ids}},
            ),
        )


class ReusePass(_BasePass):
    """Artifact reuse when fan-out boundaries exist."""

    metadata = PassMetadata(
        pass_id="etlantic.pass.reuse",
        version="1.0.0",
        rewrite_kinds=("reuse",),
        priority=50,
        description="Reuse durable artifacts across fan-out consumers",
    )

    def propose(
        self, context: OptimizationContext
    ) -> tuple[OptimizationCandidate, ...]:
        plan = context.baseline
        fanout = [b for b in plan.materialization_boundaries if "reuse" in b.reason]
        if not fanout:
            return (
                OptimizationCandidate(
                    candidate_id="reuse-none",
                    pass_id=self.metadata.pass_id,
                    rewrite_kind="reuse",
                    decision="rejected",
                    expected_benefit={},
                    proofs=_base_proofs("freshness"),
                    evidence_refs=(),
                    policy_result="accepted",
                    capability_result="supported",
                    reason="no fan-out reuse boundaries",
                ),
            )
        return (
            OptimizationCandidate(
                candidate_id="reuse:fanout",
                pass_id=self.metadata.pass_id,
                rewrite_kind="reuse",
                decision="chosen",
                expected_benefit={"relative": 0.45},
                proofs=_base_proofs("freshness", "identity", "side_effect"),
                evidence_refs=tuple(
                    ref
                    for b in fanout
                    for ref in _resolved_evidence_refs(
                        context, (f"boundary:{b.identity}", "reuse", 0.8)
                    )
                ),
                policy_result="accepted",
                capability_result="supported",
                reason="reuse durable fan-out artifacts",
                hints={
                    "annotate": {
                        "reuse_boundaries": [b.identity for b in fanout],
                    }
                },
            ),
        )


class RepairBackfillPass(_BasePass):
    """Cost-aware repair/backfill selection hints from plan intents."""

    metadata = PassMetadata(
        pass_id="etlantic.pass.repair_backfill",
        version="1.0.0",
        rewrite_kinds=("repair_backfill",),
        priority=60,
        description="Select repair/backfill closure under cost budgets",
    )

    def propose(
        self, context: OptimizationContext
    ) -> tuple[OptimizationCandidate, ...]:
        intents = dict(context.baseline.intents or {})
        repair = intents.get("repair") or intents.get("backfill")
        if not repair:
            return (
                OptimizationCandidate(
                    candidate_id="repair-none",
                    pass_id=self.metadata.pass_id,
                    rewrite_kind="repair_backfill",
                    decision="rejected",
                    expected_benefit={},
                    proofs=_base_proofs("idempotency"),
                    evidence_refs=(),
                    policy_result="accepted",
                    capability_result="supported",
                    reason="no repair/backfill intent on plan",
                ),
            )
        budget = float(context.budgets.get("repair_cost", 1.0))
        estimated = float(
            (repair or {}).get("estimated_cost", 0.5)
            if isinstance(repair, dict)
            else 0.5
        )
        if estimated > budget:
            return (
                OptimizationCandidate(
                    candidate_id="repair-over-budget",
                    pass_id=self.metadata.pass_id,
                    rewrite_kind="repair_backfill",
                    decision="rejected",
                    expected_benefit={"relative": -estimated},
                    proofs=_base_proofs("idempotency"),
                    evidence_refs=(),
                    policy_result="rejected",
                    capability_result="supported",
                    reason="repair/backfill exceeds cost budget",
                    cost_scores={"cpu": estimated},
                ),
            )
        return (
            OptimizationCandidate(
                candidate_id="repair:intent",
                pass_id=self.metadata.pass_id,
                rewrite_kind="repair_backfill",
                decision="chosen",
                expected_benefit={"relative": 0.2, "estimated_cost": estimated},
                proofs=_base_proofs("idempotency", "side_effect", "ordering"),
                evidence_refs=_resolved_evidence_refs(
                    context, ("prior-report", "freshness", 0.6)
                ),
                policy_result="accepted",
                capability_result="supported",
                reason="repair/backfill within budget",
                hints={"annotate": {"repair_intent": repair}},
            ),
        )


class ImplementationSelectionPass(_BasePass):
    """Prefer portable or lower-cost implementations when policy allows."""

    metadata = PassMetadata(
        pass_id="etlantic.pass.implementation_selection",
        version="1.0.0",
        rewrite_kinds=("implementation_selection",),
        priority=70,
        description="Cost-aware portable vs native implementation preference",
    )

    def propose(
        self, context: OptimizationContext
    ) -> tuple[OptimizationCandidate, ...]:
        plan = context.baseline
        policy = str(
            getattr(context.profile, "portable_transform_policy", "prefer") or "prefer"
        )
        portable = [
            name
            for name, impl in plan.implementations.items()
            if getattr(impl, "kind", "") == "portable"
        ]
        if policy == "native" or not portable:
            return (
                OptimizationCandidate(
                    candidate_id="impl-skip",
                    pass_id=self.metadata.pass_id,
                    rewrite_kind="implementation_selection",
                    decision="rejected",
                    expected_benefit={},
                    proofs=_base_proofs("schema"),
                    evidence_refs=(),
                    policy_result="accepted",
                    capability_result="supported",
                    reason="native policy or no portable implementations",
                ),
            )
        return (
            OptimizationCandidate(
                candidate_id="impl:portable",
                pass_id=self.metadata.pass_id,
                rewrite_kind="implementation_selection",
                decision="chosen",
                expected_benefit={"relative": 0.15, "portable_nodes": len(portable)},
                proofs=_base_proofs("schema", "ordering"),
                evidence_refs=(),
                policy_result="accepted",
                capability_result="supported",
                reason=f"prefer portable implementations under policy={policy}",
                hints={"annotate": {"prefer_portable": portable}},
            ),
        )


class CrossBackendPass(_BasePass):
    """Safe cross-backend region optimization via existing interchange boundaries."""

    metadata = PassMetadata(
        pass_id="etlantic.pass.cross_backend",
        version="1.0.0",
        rewrite_kinds=("cross_backend",),
        priority=80,
        description="Optimize cross-backend handoffs only at proven interchange boundaries",
    )

    def propose(
        self, context: OptimizationContext
    ) -> tuple[OptimizationCandidate, ...]:
        plan = context.baseline
        cross = [
            b for b in plan.materialization_boundaries if b.reason == "cross_engine"
        ]
        domains = {r.security_domain for r in plan.regions}
        if len(domains) > 1:
            return (
                _reject(
                    pass_id=self.metadata.pass_id,
                    candidate_id="cross-domain",
                    rewrite_kind="cross_backend",
                    reason="refusing to optimize across security domains without proof",
                ),
            )
        if not cross:
            return (
                OptimizationCandidate(
                    candidate_id="cross-none",
                    pass_id=self.metadata.pass_id,
                    rewrite_kind="cross_backend",
                    decision="rejected",
                    expected_benefit={},
                    proofs=_base_proofs("backend_capability"),
                    evidence_refs=(),
                    policy_result="accepted",
                    capability_result="supported",
                    reason="no cross-engine boundaries",
                ),
            )
        return (
            OptimizationCandidate(
                candidate_id="cross:interchange",
                pass_id=self.metadata.pass_id,
                rewrite_kind="cross_backend",
                decision="chosen",
                expected_benefit={"relative": 0.2},
                proofs=_base_proofs(
                    "backend_capability",
                    "schema",
                    "residency",
                    "classification",
                ),
                evidence_refs=tuple(
                    ref
                    for b in cross
                    for ref in _resolved_evidence_refs(
                        context, (f"boundary:{b.identity}", "locality", 0.85)
                    )
                ),
                policy_result="accepted",
                capability_result="supported",
                reason="optimize interchange at existing cross-engine boundaries",
                hints={
                    "annotate": {
                        "cross_backend_boundaries": [b.identity for b in cross],
                    }
                },
            ),
        )


REFERENCE_PASSES: tuple[Any, ...] = (
    PushdownPass(),
    PruningPass(),
    FusionPass(),
    MaterializationPass(),
    ReusePass(),
    RepairBackfillPass(),
    ImplementationSelectionPass(),
    CrossBackendPass(),
)

__all__ = [
    "REFERENCE_PASSES",
    "CrossBackendPass",
    "FusionPass",
    "ImplementationSelectionPass",
    "MaterializationPass",
    "PruningPass",
    "PushdownPass",
    "RepairBackfillPass",
    "ReusePass",
]
