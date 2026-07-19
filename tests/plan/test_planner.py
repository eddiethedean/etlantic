"""PipelinePlan planner acceptance tests for 0.3."""

from __future__ import annotations

import json

import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelinePlan,
    PlanningContext,
    SecretRef,
    Transformation,
)
from etlantic.exceptions import PipelineValidationError
from etlantic.plan import (
    explain_plan,
    plan_fingerprint,
    plan_from_json,
    plan_pipeline,
    plan_to_json,
    run_one_selection,
    run_until_selection,
)
from etlantic.plan.artifacts import ArtifactStrategy
from etlantic.profile import Profile


class Customer(Data):
    id: int
    name: str


class Normalize(Transformation):
    customers: Input[Customer]
    result: Output[Customer]


class Enrich(Transformation):
    customers: Input[Customer]
    result: Output[Customer]


class Audit(Transformation):
    customers: Input[Customer]
    result: Output[Customer]


class CustomerPipeline(Pipeline):
    raw: Extract[Customer] = Extract(asset="customers")
    normalized = Normalize.step(customers=raw)
    enriched = Enrich.step(customers=normalized.result)
    out: Load[Customer] = Load(input=enriched.result, asset="curated")


class ParallelPipeline(Pipeline):
    """raw fans out to step then audit; audit is declared after step."""

    raw: Extract[Customer] = Extract(asset="customers")
    step = Normalize.step(customers=raw)
    audit = Audit.step(customers=raw)
    out: Load[Customer] = Load(input=step.result, asset="curated")


def test_plan_is_deterministic() -> None:
    context = PlanningContext.create(profile="local")
    left = plan_pipeline(CustomerPipeline, context=context)
    right = plan_pipeline(CustomerPipeline, context=context)
    assert left.fingerprint == right.fingerprint
    assert left.plan_id == right.plan_id
    assert plan_to_json(left) == plan_to_json(right)


def test_plan_round_trip_json() -> None:
    plan = plan_pipeline(CustomerPipeline, profile="local")
    restored = plan_from_json(plan_to_json(plan))
    assert isinstance(restored, PipelinePlan)
    assert restored.fingerprint == plan.fingerprint
    assert restored.pipeline_id == plan.pipeline_id
    assert restored.logical_graph.nodes[0].contract_id is not None


def test_plan_contains_no_secret_values() -> None:
    profile = Profile(
        name="secure",
        resources={"db": "warehouse"},
        secrets={
            "db": SecretRef(provider="env-secrets", name="db", key="password"),
        },
    )
    plan = plan_pipeline(
        CustomerPipeline, context=PlanningContext.create(profile=profile)
    )
    blob = plan_to_json(plan)
    assert "password" in blob  # key name may appear
    secret_ref = plan.resource_refs["secret:db"]
    assert secret_ref["key"] == "password"
    assert "value" not in secret_ref
    assert "secret_value" not in secret_ref
    # unused secrets are not embedded
    unused = Profile(
        name="unused",
        secrets={
            "orphan": SecretRef(provider="env", name="x", key="token"),
        },
    )
    unused_plan = plan_pipeline(
        CustomerPipeline, context=PlanningContext.create(profile=unused)
    )
    assert "secret:orphan" not in unused_plan.resource_refs


def test_run_one_includes_upstream_closure() -> None:
    graph = CustomerPipeline.build_graph()
    selected = run_one_selection(graph, "enriched")
    assert selected == ("raw", "normalized", "enriched")
    plan = plan_pipeline(
        CustomerPipeline,
        profile="local",
        selection={"run_one": "enriched"},
    )
    assert plan.selected_nodes == selected
    assert [n.name for n in plan.logical_graph.nodes] == list(selected)


def test_run_until_includes_declaration_prefix() -> None:
    graph = ParallelPipeline.build_graph()
    selected = run_until_selection(graph, "audit")
    assert selected == ("raw", "step", "audit")
    # run_one for audit should NOT include step (sibling, not upstream)
    one = run_one_selection(graph, "audit")
    assert one == ("raw", "audit")


def test_unknown_selection_fails_closed() -> None:
    with pytest.raises(PipelineValidationError) as exc:
        plan_pipeline(
            CustomerPipeline,
            profile="local",
            selection={"run_one": "does_not_exist"},
        )
    assert any(d.code == "PMPLAN501" for d in exc.value.report.errors)


def test_multi_engine_overrides_split_regions() -> None:
    profile = Profile(
        name="multi",
        dataframe_engine="local",
        implementation_overrides={"normalized": "null", "enriched": "local"},
    )
    plan = plan_pipeline(
        CustomerPipeline, context=PlanningContext.create(profile=profile)
    )
    engines = {r.engine for r in plan.regions}
    assert engines == {"local", "null"}
    by_port = {
        (o.node_name, o.port_name): o.artifact.strategy for o in plan.output_resolutions
    }
    # Cross-engine handoff stays in-memory; conversion happens at the boundary
    # without forcing durable record materialization.
    assert by_port[("normalized", "result")] is ArtifactStrategy.IN_MEMORY
    assert any(
        b.reason == "cross_engine" and b.producer_node == "normalized"
        for b in plan.materialization_boundaries
    )


def test_fingerprint_changes_with_profile_timeout() -> None:
    left = plan_pipeline(
        CustomerPipeline,
        context=PlanningContext.create(
            profile=Profile(name="a", timeout_seconds=30),
        ),
    )
    right = plan_pipeline(
        CustomerPipeline,
        context=PlanningContext.create(
            profile=Profile(name="a", timeout_seconds=60),
        ),
    )
    assert left.fingerprint != right.fingerprint
    assert left.profile_snapshot["timeout_seconds"] == 30
    assert right.execution_settings["timeout_seconds"] == 60


def test_lazy_strategy_inside_region() -> None:
    plan = plan_pipeline(CustomerPipeline, profile="local")
    by_port = {
        (o.node_name, o.port_name): o.artifact.strategy for o in plan.output_resolutions
    }
    assert by_port[("normalized", "result")] is ArtifactStrategy.LAZY


def test_explain_plan_structure() -> None:
    plan = plan_pipeline(CustomerPipeline, profile="local")
    explained = explain_plan(plan)
    assert explained["plan_id"] == plan.plan_id
    assert explained["fingerprint"] == plan.fingerprint
    assert len(explained["steps"]) == len(plan.logical_graph.nodes)


def test_fingerprint_helper_matches_plan() -> None:
    plan = plan_pipeline(CustomerPipeline, profile="local")
    assert plan_fingerprint(plan) == plan.fingerprint


def test_invalid_pipeline_does_not_plan() -> None:
    class Broken(Transformation):
        customers: Input[Customer]
        result: Output[Customer]

    class BrokenPipeline(Pipeline):
        raw: Extract[Customer] = Extract(asset="customers")
        broken = Broken.step()  # type: ignore[call-arg]
        out: Load[Customer] = Load(input=raw, asset="out")

    report = BrokenPipeline.validate()
    assert report.has_errors
    with pytest.raises(PipelineValidationError) as exc:
        BrokenPipeline.plan(profile="local")
    assert exc.value.report is not None
    assert exc.value.report.has_errors


def test_tampered_fingerprint_rejected() -> None:
    plan = plan_pipeline(CustomerPipeline, profile="local")
    data = json.loads(plan_to_json(plan))
    data["fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        plan_from_json(json.dumps(data))
