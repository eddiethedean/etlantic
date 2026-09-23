# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportMissingParameterType=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUnusedFunction=false
"""Sol contracts for SOL-052-018, SOL-052-022 and SOL-052-029 re-review.

These bounded tests intentionally fail while the remediation regressions remain.
Production implementation must preserve prospective budgeting, distinct logical
edge realizations, and the safe-I/O lock timeout.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.exceptions import PipelineValidationError
from etlantic.interchange.security import UnsafeLoadError
from etlantic.io_policy import _acquire_lock
from etlantic.plan import plan_pipeline
from etlantic.planning import adaptive
from etlantic.planning.adaptive_budget import budget_scope
from etlantic.profile import PlacementTarget, Profile
from etlantic.registry import PlanningContext, PluginDescriptor, builtin_stub_registry


class Row(Data):
    id: int


class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    out: Load[Row] = Load(input=raw, asset="out")


class Pair(Transformation):
    left: Input[Row]
    right: Input[Row]
    result: Output[Row]


@Pair.portable
def _pair(left, right):
    return left.select("id")


class ParallelSample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    pair = Pair.step(left=raw, right=raw)
    out: Load[Row] = Load(input=pair.result, asset="out")


def _profile() -> Profile:
    return Profile(
        name="sol-052-rereview",
        execution_strategy="adaptive",
        portable_transform_policy="require",
        placement_targets={"local": PlacementTarget(engine="local")},
        eligible_targets=("local",),
    )


def test_sol_052_018_lowering_rejects_before_identity_buffer_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exhausted lowering budget cannot allocate a canonical object buffer."""
    from etlantic.plan import physical

    profile = _profile()
    plan = plan_pipeline(Sample, profile=profile)
    original = physical.json.dumps

    def no_unadmitted_object_buffer(value: Any, *args: Any, **kwargs: Any) -> str:
        if isinstance(value, Mapping):
            pytest.fail(
                "lowering materialized an identity buffer before budget admission"
            )
        return original(value, *args, **kwargs)

    monkeypatch.setattr(physical.json, "dumps", no_unadmitted_object_buffer)
    with budget_scope(1), pytest.raises(PipelineValidationError, match="PMADP303"):
        adaptive._physical_dag(
            Sample.build_graph(),
            plan.decisions,
            tuple(
                (name, target, None)
                for name, target in profile.placement_targets.items()
            ),
            plan.regions,
        )


def test_sol_052_022_parallel_port_collections_remain_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two valid handoffs must retain their separate required collections."""
    graph = ParallelSample.build_graph()
    graph = replace(
        graph,
        nodes=tuple(
            replace(node, metadata={"etlantic.collection_required": True})
            if node.name == "pair"
            else node
            for node in graph.nodes
        ),
    )
    # Supply the declared collection fact on a real portable, two-input graph.
    monkeypatch.setattr(ParallelSample, "_cached_graph", graph)
    targets = {
        "producer": PlacementTarget(engine="local", location="producer"),
        "consumer": PlacementTarget(engine="local", location="consumer"),
    }
    profile = _profile().with_updates(
        placement_targets=targets,
        eligible_targets=tuple(targets),
        implementation_overrides={
            "raw": "producer",
            "pair": "consumer",
            "out": "consumer",
        },
    )
    context = PlanningContext.create(profile, registry=builtin_stub_registry())
    evidence = []
    for edge in graph.edges:
        if edge.producer_node != "raw":
            continue
        item = adaptive._handoff_contract(
            targets["producer"], targets["consumer"], edge, context
        )
        item["evidence_ref"] = (
            "sha256:" + hashlib.sha256(edge.consumer_port.encode()).hexdigest()
        )
        evidence.append(item)
    context.registry.register_plugin(
        PluginDescriptor(
            name="parallel-port-handoffs",
            kind="handoff",
            version="1",
            metadata={"handoff_evidence": evidence},
        )
    )
    dag = plan_pipeline(ParallelSample, context=context).physical_dag
    collections = [unit for unit in dag.units if unit.kind == "collection"]
    assert len(collections) == 2, (
        "distinct parallel handoffs lost a required collection boundary"
    )
    assert len({unit.dependencies[0].unit_id for unit in collections}) == 2
    dag.validate_generated_envelope()
    dag.validate_logical_paths(
        tuple(
            (
                edge.producer_node,
                edge.consumer_node,
                edge.producer_port,
                edge.consumer_port,
            )
            for edge in graph.edges
        )
    )


def test_sol_052_029_existing_lock_honors_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Persistent contention must time out instead of retrying indefinitely."""
    from etlantic import io_policy

    path = tmp_path / "report.json"
    path.with_suffix(".json.lock").touch()
    attempts = 0

    def contended(*args: Any, **kwargs: Any) -> int:
        nonlocal attempts
        attempts += 1
        # Bound the reproducer even when production bypasses its own timeout.
        assert attempts <= 3, "lock retries bypassed an expired deadline"
        raise FileExistsError("another writer holds the lock")

    times = iter((0.0, 2.0))
    monkeypatch.setattr(io_policy.os, "open", contended)
    monkeypatch.setattr(io_policy.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(io_policy.time, "sleep", lambda _: None)
    with pytest.raises(UnsafeLoadError, match="Timed out acquiring lock") as caught:
        _acquire_lock(path, timeout=1.0)
    assert caught.value.report.diagnostics[0].code == "PMSRC112"
