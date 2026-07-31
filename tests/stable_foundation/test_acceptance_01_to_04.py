"""Stable-foundation acceptance items 1-4 (contracts, results, selective run)."""

from __future__ import annotations

from pathlib import Path

from examples.memory_customers import CustomerPipeline, RawCustomer

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    Transformation,
)
from etlantic.interchange import graphs_equivalent, load_bundle, write_contracts
from etlantic.plan import plan_pipeline, run_one_selection
from etlantic.runtime.request import RunRequest, RunSelection
from etlantic.runtime.state import RunStatus


class _Sf03Row(Data):
    id: int


class _Sf03Double(Transformation):
    rows: Input[_Sf03Row]
    result: Output[_Sf03Row]


@_Sf03Double.implementation("local")
def _sf03_double_local(rows: list[_Sf03Row]) -> list[_Sf03Row]:
    return [_Sf03Row(id=r.id * 2) for r in rows]


class _Sf03AddOne(Transformation):
    rows: Input[_Sf03Row]
    result: Output[_Sf03Row]


@_Sf03AddOne.implementation("local")
def _sf03_add_one_local(rows: list[_Sf03Row]) -> list[_Sf03Row]:
    return [_Sf03Row(id=r.id + 1) for r in rows]


class _Sf03Chain(Pipeline):
    raw: Extract[_Sf03Row] = Extract(asset="rows")
    doubled = _Sf03Double.step(rows=raw)
    bumped = _Sf03AddOne.step(rows=doubled.result)
    out: Load[_Sf03Row] = Load(input=bumped.result, asset="out")


def test_sf_01_code_first_generates_odcs_dtcs_dpcs(tmp_path: Path) -> None:
    """Item 1: code-first pipeline generates ODCS, DTCS, and DPCS."""
    bundle = write_contracts(CustomerPipeline, tmp_path)
    keys = set(bundle.documents.keys())
    assert any(k.startswith("data/") for k in keys), "expected ODCS data docs"
    assert any(k.startswith("transformations/") for k in keys), "expected DTCS"
    assert any(k.startswith("pipelines/") for k in keys), "expected DPCS"
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "transformations").is_dir()
    assert (tmp_path / "pipelines").is_dir()
    assert list((tmp_path / "data").glob("*.yaml"))
    assert list((tmp_path / "transformations").glob("*.yaml"))
    assert list((tmp_path / "pipelines").glob("*.yaml"))


def test_sf_02_contract_first_normalizes_to_same_logical_model(tmp_path: Path) -> None:
    """Item 2: contract-first bundle normalizes to the same logical model."""
    write_contracts(CustomerPipeline, tmp_path)
    loaded = load_bundle(tmp_path)
    assert loaded.pipeline is not None
    assert graphs_equivalent(CustomerPipeline.inspect(), loaded.pipeline.inspect())
    assert loaded.pipeline.validate().valid


def test_sf_03_direct_consumption_of_prior_named_result() -> None:
    """Item 3: a later step consumes a prior step's named result port."""
    edges = _Sf03Chain.inspect().edges
    assert any(
        e.producer_node == "doubled"
        and e.producer_port == "result"
        and e.consumer_node == "bumped"
        for e in edges
    )
    member = _Sf03Chain.__pipeline_members__["bumped"]
    assert member.bindings["rows"].port_name == "result"

    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [_Sf03Row(id=3)])
    report = _Sf03Chain.run(profile="development", runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED
    assert [r.id for r in runtime.memory.get("out")] == [7]


def test_sf_04_selective_local_execution_dependency_closure_and_report() -> None:
    """Item 4: selective local run includes upstream closure and a full report."""
    graph = CustomerPipeline.build_graph()
    selected = run_one_selection(graph, "normalized")
    assert selected == ("raw", "normalized")

    plan = plan_pipeline(
        CustomerPipeline,
        profile="development",
        selection={"run_one": "normalized"},
    )
    assert plan.selected_nodes == selected

    runtime = PipelineRuntime()
    runtime.memory.seed(
        "customer_source",
        [
            RawCustomer(customer_id=1, first_name="Ada", last_name="Lovelace"),
        ],
    )
    report = CustomerPipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(selection=RunSelection.only("normalized")),
    )
    assert report.status is RunStatus.SUCCEEDED
    assert report.run_id
    step_names = {s.step_name for s in report.steps}
    assert step_names == {"raw", "normalized"}
    assert "curated" not in step_names
    assert any(
        s.step_name == "normalized" and s.status.value == "succeeded"
        for s in report.steps
    )
