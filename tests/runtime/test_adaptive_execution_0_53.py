# pyright: reportMissingParameterType=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Executable local adaptive physical-DAG behavior for phase 0.53."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import anyio
import pytest

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.authoring.normalize import definition_from_pipeline
from etlantic.exceptions import PipelineExecutionError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan import AdaptivePipelinePlan
from etlantic.plan.planner import plan_pipeline, plan_pipeline_with_report
from etlantic.planning.adaptive import _handoff_contract
from etlantic.profile import PlacementTarget, Profile
from etlantic.registry import BindingDescriptor, PlanningContext, PluginDescriptor
from etlantic.runtime.execute import arun_pipeline
from etlantic.runtime.request import InvalidationMode, RunRequest
from tests.plan.test_adaptive_planner_0_52 import Sample, adaptive_profile


def test_adaptive_plan_identity_survives_checkout_line_endings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = plan_pipeline(Sample, profile=adaptive_profile())
    read_bytes = Path.read_bytes

    def windows_checkout(path: Path) -> bytes:
        raw = read_bytes(path)
        if path.name == "adaptive_support.json":
            return raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        return raw

    monkeypatch.setattr(Path, "read_bytes", windows_checkout)
    after = plan_pipeline(Sample, profile=adaptive_profile())
    assert after.fingerprint == before.fingerprint


def test_adaptive_evidence_digest_survives_checkout_line_endings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/check_adaptive_0_53.py"
    source_revision = runpy.run_path(str(script))["source_revision"]
    before = source_revision()
    read_bytes = Path.read_bytes

    def windows_checkout(path: Path) -> bytes:
        return read_bytes(path).replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")

    monkeypatch.setattr(Path, "read_bytes", windows_checkout)
    assert source_revision() == before


class CrossRow(Data):
    id: int


class CrossStep(Transformation):
    source: Input[CrossRow]
    result: Output[CrossRow]


@CrossStep.portable
def cross_project(source):
    return source.select("id")


class CrossPipeline(Pipeline):
    raw: Extract[CrossRow] = Extract(asset="cross-rows")
    step = CrossStep.step(source=raw)
    out: Load[CrossRow] = Load(input=step.result, asset="cross-out")


def test_adaptive_asset_override_is_captured_before_admission(tmp_path: Path) -> None:
    async def run() -> None:
        destination = tmp_path / "destination.json"
        destination.write_text(json.dumps([{"id": 99}]))
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}, {"id": 2}])
        runtime.registry.register_binding(
            BindingDescriptor("destination", "json", location=str(destination))
        )
        report = await arun_pipeline(
            Sample,
            profile=adaptive_profile(),
            request=RunRequest(asset_overrides={"out": "destination"}),
            runtime=runtime,
        )
        assert report.status.value == "succeeded"
        assert json.loads(destination.read_text()) == [{"id": 1}, {"id": 2}]

    anyio.run(run)


def test_adaptive_definition_request_placement_overrides_are_persisted() -> None:
    """Definition planning has the same request precedence as class planning."""

    profile = adaptive_profile(
        placement_targets={
            "first": PlacementTarget(engine="local", location="primary"),
            "second": PlacementTarget(engine="local", location="alternate"),
        },
        eligible_targets=("first", "second"),
        implementation_overrides={"raw": "first", "out": "first"},
    )
    request = RunRequest(implementation_overrides={"raw": "second", "out": "second"})
    definition = definition_from_pipeline(Sample)

    for plan in (
        plan_pipeline(definition, profile=profile, request=request),
        plan_pipeline_with_report(definition, profile=profile, request=request)[0],
    ):
        assert isinstance(plan, AdaptivePipelinePlan)
        assert {
            decision.node_name: decision.target_id for decision in plan.decisions
        } == {
            "raw": "second",
            "out": "second",
        }


def test_executable_adaptive_plan_captures_request_and_runs_physical_units() -> None:
    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}, {"id": 2}])
        request = RunRequest(metadata={"concurrency": 1})
        report = await arun_pipeline(
            Sample,
            profile=adaptive_profile(),
            request=request,
            runtime=runtime,
        )
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("out")] == [1, 2]
        trace = report.metadata["etlantic.physical_trace"]
        assert [item["kind"] for item in trace] == [
            "compute",
            "compute",
            "publication",
        ]

    anyio.run(run)


def test_adaptive_unsupported_invalidation_rejects_before_runtime_effects() -> None:
    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        with pytest.raises(PipelineExecutionError) as error:
            await arun_pipeline(
                Sample,
                profile=adaptive_profile(),
                request=RunRequest(invalidation=InvalidationMode.TARGET),
                runtime=runtime,
            )
        assert error.value.code == "PMADP522"
        assert runtime.memory.get("out") == []

    anyio.run(run)


def test_adaptive_admission_rejects_invalid_concurrency_before_storage_effects() -> (
    None
):
    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        with pytest.raises(PipelineExecutionError) as error:
            await arun_pipeline(
                Sample,
                profile=adaptive_profile(),
                request=RunRequest(metadata={"concurrency": True}),
                runtime=runtime,
            )
        assert error.value.code == "PMADP522"
        assert runtime.memory.get("out") == []

    anyio.run(run)


def test_default_adaptive_plan_uses_executable_lowering() -> None:
    planning = plan_pipeline(Sample, profile=adaptive_profile())
    executable = plan_pipeline(Sample, profile=adaptive_profile(), request=RunRequest())
    assert planning.metadata["etlantic.execution"] == "local-static-batch/1"
    assert executable.metadata["etlantic.execution"] == "local-static-batch/1"
    assert planning.fingerprint == executable.fingerprint


def test_adaptive_physical_execution_routes_portable_polars_to_pandas() -> None:
    """A qualified directional handoff executes through the stored transfer."""
    polars = pytest.importorskip("etlantic_polars")
    pandas = pytest.importorskip("etlantic_pandas")

    targets = {
        "producer": PlacementTarget(engine="polars"),
        "consumer": PlacementTarget(engine="pandas"),
    }
    profile = Profile(
        name="adaptive-cross-runtime",
        execution_strategy="adaptive",
        portable_transform_policy="require",
        placement_targets=targets,
        eligible_targets=("producer", "consumer"),
        implementation_overrides={
            "raw": "producer",
            "step": "consumer",
            "out": "consumer",
        },
    )

    async def run() -> None:
        runtime = PipelineRuntime()
        runtime.register_dataframe_plugin("polars", polars.create_plugin())
        runtime.register_dataframe_plugin("pandas", pandas.create_plugin())
        context = PlanningContext.create(profile, registry=runtime.registry)
        edge = CrossPipeline.build_graph().edges[0]
        evidence = _handoff_contract(
            targets["producer"], targets["consumer"], edge, context
        )
        evidence["evidence_ref"] = "sha256:" + ("a" * 64)
        context.registry.register_plugin(
            PluginDescriptor(
                name="cross-runtime-handoff",
                kind="handoff",
                version="1",
                metadata={"handoff_evidence": [evidence]},
            )
        )
        runtime.memory.seed("cross-rows", [{"id": 1}, {"id": 2}])
        report = await arun_pipeline(
            CrossPipeline,
            profile=profile,
            context=context,
            request=RunRequest(metadata={"concurrency": 1}),
            runtime=runtime,
        )
        assert report.status.value == "succeeded"
        assert [row.id for row in runtime.memory.get("cross-out")] == [1, 2]
        trace = report.metadata["etlantic.physical_trace"]
        assert [item["kind"] for item in trace] == [
            "compute",
            "transfer",
            "compute",
            "compute",
            "publication",
        ]

    anyio.run(run)
