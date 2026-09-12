"""Behavioral regression proof for FINAL-052-015 through FINAL-052-018."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass

import pytest

from etlantic import Data, Extract, Load, Pipeline
from etlantic.exceptions import PipelineValidationError
from etlantic.plan import explain_plan, plan_from_json, plan_pipeline, plan_to_json
from etlantic.plan.physical import PhysicalDAG, PhysicalDependency, PhysicalUnit
from etlantic.planning.adaptive_budget import (
    MAX_TRANSIENT_BYTES,
    TransientBudget,
    budget_scope,
    canonical_chunks,
    canonical_size,
    materialize_wire,
    record,
    serialized_size,
    wire_view,
)
from etlantic.profile import PlacementTarget, Profile


class Row(Data):
    id: int


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    out: Load[Row] = Load(input=raw, asset="out")


def profile() -> Profile:
    return Profile(
        name="final-remediation",
        execution_strategy="adaptive",
        portable_transform_policy="require",
        placement_targets={"local": PlacementTarget(engine="local")},
        eligible_targets=("local",),
    )


def sign(data: dict) -> str:
    canonical = {k: v for k, v in data.items() if k not in {"fingerprint", "plan_id"}}
    digest = hashlib.sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    data.update(fingerprint=digest, plan_id=f"plan:{digest[:16]}")
    return json.dumps(data)


def test_final_052_016_historical_incomplete_topology_remains_readable() -> None:
    # The shipped 0.51 fixture intentionally has only the wire foundation's
    # short objective and no planner generation marker.
    from tests.plan.test_adaptive_wire_0_51 import _plan

    historical = _plan().to_dict()
    template = historical["physical_dag"]["units"][0]
    units = [
        dict(template, identity=f"unit-{n}", logical_nodes=[n], dependencies=[])
        for n in ("raw", "out")
    ]
    historical["physical_dag"] = {
        "units": units,
        "logical_to_physical": {n: f"unit-{n}" for n in ("raw", "out")},
        "topological_order": ["unit-raw", "unit-out"],
    }
    text = sign(historical)
    for verify in (True, False):
        restored = plan_from_json(text, verify=verify)
        assert restored.to_dict() == historical
        assert explain_plan(restored)["planning_only"]
        assert plan_from_json(plan_to_json(restored)).to_dict() == historical


@pytest.mark.parametrize("verify", [True, False])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "control-only"])
def test_final_052_017_generated_edge_requires_one_data_path(
    verify: bool, mutation: str
) -> None:
    data = plan_pipeline(Sample, profile=profile()).to_dict()
    dag = data["physical_dag"]
    source_id, sink_id = (dag["logical_to_physical"][n] for n in ("raw", "out"))
    sink = next(u for u in dag["units"] if u["identity"] == sink_id)
    sink["metadata"]["etlantic.logical_predecessors"] = []
    if mutation == "missing":
        sink["dependencies"] = []
    elif mutation == "control-only":
        sink["dependencies"][0]["kind"] = "control"
    else:
        branch = copy.deepcopy(
            next(u for u in dag["units"] if u["identity"] == source_id)
        )
        branch.update(
            identity="extra-route",
            kind="validation",
            logical_nodes=[],
            metadata={},
            dependencies=[{"unit_id": source_id, "kind": "data"}],
        )
        dag["units"].append(branch)
        sink["dependencies"].append({"unit_id": "extra-route", "kind": "data"})
        dag["topological_order"].insert(
            dag["topological_order"].index(sink_id), "extra-route"
        )
    with pytest.raises(ValueError, match="PMADP403"):
        plan_from_json(sign(data), verify=verify)


def test_final_052_017_logical_diamond_preserves_individual_edge_paths() -> None:
    edges = (("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d"))
    units = tuple(
        PhysicalUnit(
            identity=n,
            kind="compute",
            target_identity="t",
            logical_nodes=(n,),
            dependencies=tuple(PhysicalDependency(a) for a, b in edges if b == n),
        )
        for n in "abcd"
    )
    dag = PhysicalDAG(
        units=units,
        logical_to_physical={n: n for n in "abcd"},
        topological_order=tuple("abcd"),
    )
    dag.validate_logical_paths(edges)


@pytest.mark.parametrize(
    "value",
    ['a\n"\\☃😀' * 2000, {"x": [1, True, None, "é"], "z": {}}, [[], {"": ""}]],
    ids=("large-unicode", "nested-values", "empty-containers"),
)
def test_final_052_018_sizing_matches_public_json_without_large_buffers(
    value: object,
) -> None:
    compact = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()
    chunks = list(canonical_chunks(value))
    assert b"".join(chunks) == compact
    assert canonical_size(value) == len(compact)
    assert max(map(len, chunks)) <= 24576
    for indent in (None, 0, 2, 4):
        expected = json.dumps(
            value,
            sort_keys=True,
            indent=indent,
            **({"separators": (",", ":")} if indent is None else {}),
        )
        assert serialized_size(value, indent) == len(expected.encode())


@pytest.mark.parametrize(
    "category,overhead",
    [
        ("inventory", 64),
        ("candidate", 64),
        ("region", 64),
        ("boundary", 64),
        ("explain", 64),
        ("solver-frontier", 128),
        ("solver-incumbent", 128),
        ("oracle-frontier", 128),
        ("oracle-incumbent", 128),
        ("serialization-buffer", 0),
    ],
)
def test_final_052_018_each_owner_has_exact_before_at_after_limits(
    category: str, overhead: int
) -> None:
    payload = {"identity": "test-😀", "facts": [1, 2, 3]}
    cost = (
        len(
            json.dumps(
                payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        )
        + overhead
    )
    for limit in (cost - 1, cost, cost + 1):
        budget = TransientBudget(limit)
        reached = False
        try:
            with budget.allocation(payload, category, overhead):
                reached = True
                assert budget.live == cost
        except PipelineValidationError as exc:
            assert "PMADP303" in str(exc)
            assert limit == cost - 1
        assert reached == (limit >= cost)
        assert budget.live == 0
        assert not budget.charges
    frozen = TransientBudget()
    first = frozen.reserve(MAX_TRANSIENT_BYTES - 1, category)
    last = frozen.reserve(1, category)
    with pytest.raises(PipelineValidationError, match="PMADP303"):
        frozen.reserve(1, category)
    frozen.release(last)
    frozen.release(first)
    assert frozen.live == 0


def test_final_052_018_rejects_before_record_construction_and_releases_on_error() -> (
    None
):
    calls = []

    @dataclass
    class Sentinel:
        payload: str

        def __post_init__(self) -> None:
            calls.append(True)
            raise RuntimeError("constructor failure")

    with budget_scope(100) as budget:
        with pytest.raises(PipelineValidationError, match="PMADP303"):
            record(Sentinel, "candidate", payload="x" * 1000)
        assert calls == []
        assert budget.live == 0
    with budget_scope(1000) as budget:
        with pytest.raises(RuntimeError, match="constructor failure"):
            record(Sentinel, "candidate", payload="small")
        assert calls == [True]
        assert budget.live == 0


def test_final_052_018_public_pipeline_accounts_all_phases_and_cleans_owners() -> None:
    with budget_scope() as budget:
        plan = plan_pipeline(Sample, profile=profile())
        peak = budget.peak
        assert budget.live == 0
        assert budget.categories >= {
            "inventory",
            "inventory-resolution",
            "candidate",
            "region",
            "boundary",
            "solver-frontier",
            "solver-incumbent",
            "oracle-frontier",
            "oracle-incumbent",
            "plan",
            "serialization-buffer",
        }
        assert materialize_wire(wire_view(plan)) == plan.to_dict()
        explain_plan(plan)
        plan_to_json(plan)
        assert {"explain", "serialization-record"} <= budget.categories
        assert budget.live == 0
    for limit in (peak - 1, peak, peak + 1):
        with budget_scope(limit) as bounded:
            if limit < peak:
                with pytest.raises(PipelineValidationError, match="PMADP303"):
                    plan_pipeline(Sample, profile=profile())
            else:
                assert (
                    plan_pipeline(Sample, profile=profile()).fingerprint
                    == plan.fingerprint
                )
            assert bounded.live == 0


def test_final_052_018_output_allocations_reject_before_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = plan_pipeline(Sample, profile=profile())

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("output materialized before admission")

    monkeypatch.setattr("etlantic.plan.explain.materialize_wire", forbidden)
    monkeypatch.setattr("etlantic.plan.adaptive_serialize.materialize_wire", forbidden)
    with budget_scope(1):
        with pytest.raises(PipelineValidationError, match="PMADP303"):
            explain_plan(plan)
        with pytest.raises(PipelineValidationError, match="PMADP303"):
            plan_to_json(plan)


@pytest.mark.parametrize("size", [255, 256, 257])
def test_final_052_018_selected_node_limit(size: int) -> None:
    attrs = {
        "__module__": __name__,
        "__annotations__": {f"n{i}": Extract[Row] for i in range(size)},
    }
    attrs.update({f"n{i}": Extract(asset=f"a{i}") for i in range(size)})
    pipeline = type("NodeLimit", (Pipeline,), attrs)
    if size > 256:
        with pytest.raises(PipelineValidationError, match="PMADP300"):
            plan_pipeline(pipeline, profile=profile())
    else:
        assert len(plan_pipeline(pipeline, profile=profile()).decisions) == size


@pytest.mark.parametrize("count", [7, 8, 9])
def test_final_052_018_target_limit(count: int) -> None:
    targets = {
        f"t{i}": PlacementTarget(engine="local", location=f"place-{i}")
        for i in range(count)
    }
    configured = profile().with_updates(
        placement_targets=targets, eligible_targets=tuple(targets)
    )
    if count > 8:
        with pytest.raises(PipelineValidationError, match="PMADP100"):
            plan_pipeline(Sample, profile=configured)
    else:
        assert len(plan_pipeline(Sample, profile=configured).candidates) == 2 * count


def test_final_052_018_evidence_cap_boundaries() -> None:
    from etlantic.planning.adaptive import _bounded_evidence

    for count in (7, 8, 9):
        refs = [f"sha256:{i:064x}" for i in range(count)]
        actual = _bounded_evidence(list(reversed(refs)))
        assert len(actual) == min(count, 8)
        if count <= 8:
            assert actual == tuple(refs)
        else:
            assert actual == (*refs[:7], "etlantic.evidence-truncated/1:omitted=2")


@pytest.mark.parametrize(
    "caps,chosen",
    [
        ({"source.predicate_pushdown": True}, {"predicate"}),
        ({"source.projection_pushdown": True}, {"projection"}),
        (
            {"source.predicate_pushdown": True, "source.projection_pushdown": True},
            {"predicate", "projection"},
        ),
        ({}, set()),
        ({"source.predicate_pushdown": "unknown"}, set()),
        ({"pushdown": True, "source.filter_pushdown": True}, set()),
    ],
)
def test_final_052_015_pushdown_requires_independent_connector_evidence(
    caps: dict, chosen: set
) -> None:
    from dataclasses import replace

    from etlantic.optimization.evidence import EvidenceRecord, EvidenceStore
    from etlantic.optimization.passes import PushdownPass
    from etlantic.optimization.protocol import OptimizationContext
    from etlantic.testing.optimizer_conformance import _minimal_plan

    baseline = replace(
        _minimal_plan(),
        capability_decisions=(
            {
                "node": "extract",
                "capabilities": {
                    "source.predicate_pushdown": True,
                    "source.projection_pushdown": True,
                    "pushdown": True,
                },
            },
        ),
    )
    for evidence in (
        EvidenceStore(),
        EvidenceStore(
            [
                EvidenceRecord(
                    evidence_id="connector:extract",
                    kind="connector_capabilities",
                    subject="extract",
                    value=caps,
                )
            ]
        ),
    ):
        context = OptimizationContext(
            baseline=baseline, profile=Profile(name="pushdown-proof"), evidence=evidence
        )
        actual = PushdownPass().propose(context)
        assert len(actual) == 2
        assert {
            c.candidate_id.rsplit(":", 1)[1] for c in actual if c.decision == "chosen"
        } == (chosen if evidence.records() else set())
        assert actual == PushdownPass().propose(context)


def test_final_052_018_explain_exact_four_mib_boundary() -> None:
    plan = plan_pipeline(Sample, profile=profile())
    # Stored immutable payload is borrowed by explain; expanding it here avoids
    # conflating metadata validation with output-allocation admission.
    object.__setattr__(plan, "metadata", {"etlantic.padding": ""})
    overhead = canonical_size(explain_plan(plan))
    for delta in (-1, 0, 1):
        object.__setattr__(
            plan,
            "metadata",
            {"etlantic.padding": "x" * (4 * 1024 * 1024 - overhead + delta)},
        )
        result = explain_plan(plan)
        if delta > 0:
            assert result["diagnostic"]["code"] == "PMADP305"
            assert canonical_size(result) < 4 * 1024 * 1024
        else:
            assert "truncated" not in result
            assert canonical_size(result) == 4 * 1024 * 1024 + delta


def test_final_052_018_expansion_limit_checks_prospective_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from etlantic.planning import adaptive

    original = adaptive._check_expansion_limit
    original(999_999)
    original(1_000_000)
    with pytest.raises(PipelineValidationError, match="PMADP304"):
        original(1_000_001)
    seen = []

    def observe(prospective: int) -> None:
        seen.append(prospective)
        original(prospective)

    monkeypatch.setattr(adaptive, "_check_expansion_limit", observe)
    plan_pipeline(Sample, profile=profile())
    assert seen == list(range(1, len(seen) + 1))
    required = len(seen)
    for limit in (required - 1, required, required + 1):
        monkeypatch.setattr(adaptive, "MAX_SOLVER_EXPANSIONS", limit)
        if limit < required:
            with pytest.raises(PipelineValidationError, match="PMADP304"):
                plan_pipeline(Sample, profile=profile())
        else:
            assert plan_pipeline(Sample, profile=profile()).schema == "etlantic.plan/2"


def test_final_052_015_issue_ledger_rejects_missing_or_unexecuted_proof() -> None:
    from scripts.check_adaptive_0_52 import ISSUE_LEDGER, ROOT, _verify_issue_ledger

    ledger = json.loads((ROOT / ISSUE_LEDGER).read_text())
    passed = {proof for item in ledger["issues"] for proof in item["verification"]}
    assert len(_verify_issue_ledger(passed, ledger)) == 36
    with pytest.raises(RuntimeError, match="not executed"):
        _verify_issue_ledger(set(), ledger)
    for mutation in ("missing", "duplicate", "deferred", "symbol", "proof"):
        broken = copy.deepcopy(ledger)
        if mutation == "missing":
            broken["issues"].pop()
        elif mutation == "duplicate":
            broken["issues"].append(broken["issues"][0])
        elif mutation == "deferred":
            broken["issues"][0]["status"] = "deferred"
        elif mutation == "symbol":
            broken["issues"][0]["implementation"] = [
                "src/etlantic/planning/adaptive.py:missing_symbol"
            ]
        else:
            broken["issues"][0]["verification"] = ["unexecuted_test"]
        with pytest.raises(RuntimeError):
            _verify_issue_ledger(passed, broken)


def test_final_052_017_parallel_port_edges_are_distinct_realizations() -> None:
    edges = (("a", "b", "out", "left"), ("a", "b", "out", "right"))
    source = PhysicalUnit(
        identity="a", kind="compute", target_identity="t", logical_nodes=("a",)
    )
    transfers = tuple(
        PhysicalUnit(
            identity=f"transfer-{i}",
            kind="transfer",
            target_identity="t",
            dependencies=(PhysicalDependency("a"),),
            metadata={"etlantic.edge_ports": edge},
        )
        for i, edge in enumerate(edges)
    )
    sink = PhysicalUnit(
        identity="b",
        kind="compute",
        target_identity="t",
        logical_nodes=("b",),
        dependencies=tuple(PhysicalDependency(unit.identity) for unit in transfers),
    )
    dag = PhysicalDAG(
        units=(source, *transfers, sink),
        logical_to_physical={"a": "a", "b": "b"},
        topological_order=("a", "transfer-0", "transfer-1", "b"),
    )
    dag.validate_logical_paths(edges)
    from dataclasses import replace

    unknown = replace(
        transfers[1], metadata={"etlantic.edge_ports": ("a", "b", "out", "unknown")}
    )
    with pytest.raises(ValueError, match="unknown logical port"):
        replace(
            dag, units=(source, transfers[0], unknown, sink)
        ).validate_logical_paths(edges)
    duplicate = replace(transfers[1], metadata={"etlantic.edge_ports": edges[0]})
    with pytest.raises(ValueError, match="multiple physical"):
        replace(
            dag, units=(source, transfers[0], duplicate, sink)
        ).validate_logical_paths(edges)


def test_final_052_018_full_candidate_matrix_limit() -> None:
    names = [f"n{i}" for i in range(256)]
    attrs = {
        "__module__": __name__,
        "__annotations__": {name: Extract[Row] for name in names},
    }
    attrs.update({name: Extract(asset=name) for name in names})
    pipeline = type("MatrixLimit", (Pipeline,), attrs)
    targets = {
        f"t{i}": PlacementTarget(engine="local", location=f"place-{i}")
        for i in range(8)
    }
    configured = profile().with_updates(
        placement_targets=targets,
        eligible_targets=tuple(targets),
        implementation_overrides={name: "t0" for name in names},
    )
    result = plan_pipeline(pipeline, profile=configured)
    assert len(result.candidates) == 2048
    assert sum(item.status == "eligible" for item in result.candidates) == 256


def test_final_052_018_large_summary_fields_remain_bounded() -> None:
    plan = plan_pipeline(Sample, profile=profile())
    object.__setattr__(plan, "pipeline_id", "x" * (4 * 1024 * 1024))
    result = explain_plan(plan)
    assert result["diagnostic"]["code"] == "PMADP305"
    assert canonical_size(result) < 4 * 1024 * 1024
    assert len(result["omitted_sha256"]) == 64


def test_final_052_018_inventory_refuses_before_materializing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("inventory copied before budget admission")

    monkeypatch.setattr("etlantic.planning.adaptive.materialize_wire", forbidden)
    with budget_scope(1) as budget:
        with pytest.raises(PipelineValidationError, match="PMADP303"):
            plan_pipeline(Sample, profile=profile())
        assert budget.live == 0
