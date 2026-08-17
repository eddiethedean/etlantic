"""Wave 2: optimizer rewrite reject, compiler reject, crash/restart fixtures."""

from __future__ import annotations

from etlantic.capabilities import PluginCapabilities
from etlantic.model import LogicalGraph, Node, NodeKind
from etlantic.optimization.cost import select_candidates
from etlantic.optimization.evidence import EvidenceStore
from etlantic.optimization.protocol import OptimizationCandidate, ProofObligation
from etlantic.orchestration import (
    CompilationContext,
    OrchestrationCompilationError,
    compile_plan,
)
from etlantic.orchestration.protocol import (
    CompiledOrchestrationArtifact,
    OrchestratorPluginInfo,
)
from etlantic.plan.model import PLAN_SCHEMA, PipelinePlan
from etlantic.plan.serialize import plan_fingerprint
from etlantic.streaming.envelope import ChangeEnvelopeMetadata, ChangeOp
from etlantic.streaming.errors import (
    OffsetAdvanceRule,
    RecordErrorOutcome,
    RecordErrorPolicy,
)
from etlantic.streaming.fixtures import InMemoryRecord, InMemoryStreamSource
from etlantic.testing.optimizer_conformance import _minimal_plan


class _StaticOrch:
    def __init__(self, *, extras: frozenset[str] = frozenset()) -> None:
        self._caps = PluginCapabilities(engine="stub", extras=extras)
        self.info = OrchestratorPluginInfo(
            name="stub", engine="stub", version="0.0.0", capabilities=self._caps
        )

    def capabilities(self) -> PluginCapabilities:
        return self._caps

    def compile(self, plan, *, context):
        return CompiledOrchestrationArtifact(
            target=context.target,
            dag_id=plan.plan_id,
            plan_id=plan.plan_id,
            pipeline_id=plan.pipeline_id,
            fingerprint=plan.fingerprint,
            source="# stub",
        )

    def explain(self, artifact):
        return {"target": artifact.target}


def _plan_with_map() -> PipelinePlan:
    graph = LogicalGraph(
        pipeline_id="dyn",
        pipeline_name="Dyn",
        nodes=(
            Node(
                name="fanout",
                kind=NodeKind.MAP,
                identity="fanout",
                metadata={
                    "etlantic.expansion": {
                        "keys": ["a", "b"],
                        "collection_identity": "parts",
                    }
                },
            ),
        ),
        edges=(),
    )
    plan = PipelinePlan(
        schema=PLAN_SCHEMA,
        plan_id="dyn",
        pipeline_id="dyn",
        pipeline_name="Dyn",
        profile_name="development",
        fingerprint="pending",
        logical_graph=graph,
    )
    fp = plan_fingerprint(plan)
    data = plan.to_dict()
    data["fingerprint"] = fp
    return PipelinePlan.from_dict(data, verify=False)


def test_unknown_rewrite_kind_rejected() -> None:
    plan = _minimal_plan()
    store = EvidenceStore()
    candidate = OptimizationCandidate(
        candidate_id="expand",
        pass_id="illegal",
        rewrite_kind="expansion",
        decision="chosen",
        expected_benefit={},
        proofs=(ProofObligation(kind="identity", status="proven"),),
        evidence_refs=(),
        policy_result="accepted",
        capability_result="supported",
        reason="must fail",
    )
    scored, diags = select_candidates((candidate,), plan=plan, evidence=store)
    assert scored[0].decision == "rejected"
    assert any(d.code == "PMOPT112" for d in diags)


def test_compile_rejects_map_without_capability() -> None:
    plan = _plan_with_map()
    try:
        compile_plan(plan, target="stub", plugin=_StaticOrch())
        raise AssertionError("expected OrchestrationCompilationError")
    except OrchestrationCompilationError as exc:
        assert any(d.code == "PMDYN130" for d in exc.diagnostics)


def test_compile_accepts_when_extra_claimed() -> None:
    plan = _plan_with_map()
    artifact = compile_plan(
        plan,
        target="stub",
        plugin=_StaticOrch(extras=frozenset({"control.expansion"})),
        context=CompilationContext(target="stub"),
    )
    assert artifact.plan_id == "dyn"


def test_crash_does_not_advance_uncommitted_poison() -> None:
    policy = RecordErrorPolicy(
        outcome=RecordErrorOutcome.FAIL,
        max_retries=0,
        offset_advance=OffsetAdvanceRule.NEVER,
    )
    env = ChangeEnvelopeMetadata(
        op=ChangeOp.INSERT,
        source_position="1",
        order_key="1",
        schema_identity="s",
    )
    src = InMemoryStreamSource(
        identity="src",
        records=[
            InMemoryRecord(identity="r1", envelope=env, payload={"x": 1}),
            InMemoryRecord(
                identity="bad", envelope=env, payload={"secret": "nope"}, poison=True
            ),
        ],
        policy=policy,
    )
    assert src.next_envelope() is not None
    src.commit()
    assert src.next_envelope() is None
    src.crash()
    report = src.report_fields()
    assert "payload" not in str(report).lower() or "etlantic.streaming" in str(report)
    assert "secret" not in str(report)
    assert src.committed_cursor == 1
    assert src.cursor == 1
