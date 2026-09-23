# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportMissingParameterType=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Exact candidate negative boundaries, parity, ownership and resource proofs."""

import json
import threading
from dataclasses import replace

import anyio
import pytest

pytest.importorskip("polars")
pytest.importorskip("pyarrow")
pytest.importorskip("pandas")

import polars as pl
from tests.runtime.physical.fusion_fixture_0_54 import (
    MULTILINE_COLUMN,
    MultilineReference,
    Reference,
)
from tests.runtime.physical.test_fusion_0_54 import _seed, setup

from etlantic import PipelineRuntime, Profile
from etlantic.exceptions import PipelineCancelledError, PipelineValidationError
from etlantic.io_policy import SafeIoPolicy
from etlantic.plan import plan_from_json, plan_to_json
from etlantic.planning.adaptive import _transform_map
from etlantic.planning.adaptive_budget import budget_scope, canonical_size
from etlantic.planning.fusion import lower_fusion, recognize_fusion
from etlantic.runtime import arun_pipeline
from etlantic.runtime.artifacts import ArtifactStore
from etlantic.runtime.request import RunRequest
from etlantic.runtime.scheduler import LocalScheduler
from etlantic.transform.fusion import FusionDescriptor, compose_fusion_definition
from etlantic_polars import create_parquet_storage

pytestmark = [pytest.mark.polars, pytest.mark.pandas]


@pytest.mark.parametrize(
    "boundary",
    [
        "source-metadata",
        "filter-metadata",
        "project-metadata",
        "missing-validation",
        "partial-placement",
    ],
)
def test_protected_candidate_boundaries_do_not_fuse(tmp_path, boundary):
    _, profile, context, plan = setup(tmp_path)
    graph = plan.logical_graph
    if boundary == "partial-placement":
        context = replace(
            context,
            profile=profile.with_updates(implementation_overrides={"raw": "scan"}),
        )
    else:
        index = {
            "source-metadata": 0,
            "filter-metadata": 1,
            "project-metadata": 2,
            "missing-validation": 3,
        }[boundary]
        graph = replace(
            graph,
            nodes=tuple(
                replace(
                    node, metadata={} if index == 3 else {"etlantic.observer": True}
                )
                if i == index
                else node
                for i, node in enumerate(graph.nodes)
            ),
        )
    targets = tuple(
        (key, target, None) for key, target in profile.placement_targets.items()
    )
    assert (
        recognize_fusion(
            graph,
            plan.decisions,
            targets,
            context,
            RunRequest(),
            _transform_map(Reference, None),
        )
        is None
    )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("bound", [True, 0, -1, 1000001])
def test_source_configuration_is_rejected_during_planning(tmp_path, bound):
    from etlantic.plan import plan_pipeline

    _, profile, context, _ = setup(tmp_path)
    binding = context.registry.bindings["raw"]
    context.registry.register_binding(
        replace(binding, config={**binding.config, "max_rows": bound})
    )
    with pytest.raises(PipelineValidationError) as error:
        plan_pipeline(Reference, profile=profile, context=context, request=RunRequest())
    assert "PMADP403" in str(error.value)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("rows", [[], [None, None], [1, None, 2, 1], [2, 3]])
def test_explicit_adaptive_typed_lifecycle_parity(tmp_path, rows):
    pl.DataFrame(
        {"key": rows, "enabled": [True] * len(rows), "unused": [99] * len(rows)},
        schema={"key": pl.Int64, "enabled": pl.Boolean, "unused": pl.Int64},
    ).write_parquet(tmp_path / "raw.parquet")

    async def exercise():
        runtime, _, _, plan = setup(tmp_path)
        adaptive = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
        )
        baseline = PipelineRuntime()
        baseline.register_storage("polars-parquet", create_parquet_storage())
        baseline.registry.register_binding(runtime.registry.bindings["raw"])
        explicit = await arun_pipeline(
            Reference,
            profile=Profile(
                name="explicit",
                dataframe_engine="polars",
                portable_transform_policy="require",
                safe_io=SafeIoPolicy.for_root(tmp_path).to_dict(),
                implementation_overrides={
                    n.name: "polars" if i < 3 else "pandas"
                    for i, n in enumerate(Reference.build_graph().nodes)
                },
            ),
            runtime=baseline,
            workspace=tmp_path,
        )
        assert adaptive.status == explicit.status
        assert adaptive.status.value == "succeeded", explicit.diagnostics
        assert [row.model_dump() for row in runtime.memory.get("out")] == [
            row.model_dump() for row in baseline.memory.get("out")
        ]
        assert [(s.step_name, s.status, s.attempts) for s in adaptive.steps] == [
            (s.step_name, s.status, s.attempts) for s in explicit.steps
        ]
        assert {
            v.node_name
            for v in adaptive.validations
            if v.boundary == "fused_schema" and v.status == "passed"
        } == {"raw", "filtered", "projected"}
        assert all(v.status in {"passed", "skipped"} for v in adaptive.validations)
        assert not list(tmp_path.glob("etlantic-parquet-*"))

    anyio.run(exercise)


def test_multiline_operator_identifier_stored_execution_matches_explicit(tmp_path):
    pl.DataFrame(
        {
            MULTILINE_COLUMN: [1, 2, 1],
            "enabled": [True, False, None],
            "unused": [9, 9, 9],
        }
    ).write_parquet(tmp_path / "raw.parquet")

    async def exercise():
        runtime, _, _, plan = setup(tmp_path, pipeline=MultilineReference)
        assert any(u.metadata.get("etlantic.fusion") for u in plan.physical_dag.units)
        stored = plan_from_json(plan_to_json(plan))
        adaptive = await LocalScheduler().execute(
            stored, request=RunRequest(), runtime=runtime, workspace=tmp_path
        )
        baseline = PipelineRuntime()
        baseline.register_storage("polars-parquet", create_parquet_storage())
        baseline.registry.register_binding(runtime.registry.bindings["raw"])
        explicit = await arun_pipeline(
            MultilineReference,
            profile=Profile(
                name="explicit-multiline",
                dataframe_engine="polars",
                portable_transform_policy="require",
                safe_io=SafeIoPolicy.for_root(tmp_path).to_dict(),
                implementation_overrides={
                    n.name: "polars" if i < 3 else "pandas"
                    for i, n in enumerate(MultilineReference.build_graph().nodes)
                },
            ),
            runtime=baseline,
            workspace=tmp_path,
        )
        assert adaptive.status == explicit.status
        assert adaptive.status.value == "succeeded"
        expected = [{MULTILINE_COLUMN: 1}, {MULTILINE_COLUMN: 1}]
        assert [row.model_dump() for row in runtime.memory.get("out")] == expected
        assert [row.model_dump() for row in baseline.memory.get("out")] == expected

    anyio.run(exercise)


def test_original_ir_alpha_renaming_and_objective_proof(tmp_path):
    _, _, _, plan = setup(tmp_path)
    unit = next(u for u in plan.physical_dag.units if u.metadata.get("etlantic.fusion"))
    descriptor = FusionDescriptor.from_dict(unit.metadata["etlantic.fusion"])
    before = descriptor.to_dict()
    region = next(
        r for r in plan.regions if r.logical_nodes == descriptor.logical_nodes
    )
    assert region.fused
    assert region.metadata["etlantic.fusion_evidence"] == descriptor.fingerprint
    from importlib.resources import files

    import jsonschema

    jsonschema.validate(
        before,
        json.loads(
            files("etlantic.schemas")
            .joinpath("portable-fusion.schema.json")
            .read_text()
        ),
    )
    composed = compose_fusion_definition(descriptor)
    assert [a["id"] for a in composed["actions"]] == ["fusion_filter", "fusion_project"]
    assert descriptor.to_dict() == before
    assert plan.objective[1] == -2 and plan.objective[5] == -2
    assert (
        sum(
            c.objective_facts["proven_pushdown_actions"]
            for c in plan.candidates
            if c.status == "eligible"
        )
        == 2
    )
    with pytest.raises(TypeError):
        descriptor.parameters["key"] = 2


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-descriptor",
        "unknown-field",
        "parameter-bool",
        "parameter-overflow",
        "wrong-member-order",
        "source-evidence",
        "member-ir",
    ],
)
def test_closed_descriptor_tamper_before_source(tmp_path, mutation):
    _, _, _, plan = setup(tmp_path)
    document = json.loads(plan_to_json(plan))
    unit = next(
        u
        for u in document["physical_dag"]["units"]
        if "etlantic.fusion" in u["metadata"]
    )
    fusion = unit["metadata"]["etlantic.fusion"]
    if mutation == "missing-descriptor":
        del unit["metadata"]["etlantic.fusion"]
    elif mutation == "unknown-field":
        fusion["unknown"] = 1
    elif mutation in {"parameter-bool", "parameter-overflow"}:
        fusion["parameters"]["key"] = True if mutation == "parameter-bool" else 2**63
    elif mutation == "wrong-member-order":
        fusion["member_order"].reverse()
    elif mutation == "source-evidence":
        fusion["proof_references"] = ["sha256:" + "0" * 64]
    else:
        fusion["members"][fusion["member_order"][0]]["ir_fingerprint"] = "0" * 64
    with pytest.raises((ValueError, KeyError)):
        plan_from_json(json.dumps(document), verify=False)
    assert not list(tmp_path.iterdir())


def test_descriptor_allocation_first_excess_and_release(tmp_path):
    _, _, _, plan = setup(tmp_path)
    unit = next(u for u in plan.physical_dag.units if u.metadata.get("etlantic.fusion"))
    descriptor = FusionDescriptor.from_dict(unit.metadata["etlantic.fusion"])
    size = canonical_size(descriptor.to_dict())
    with budget_scope(size - 1) as budget:
        with pytest.raises(PipelineValidationError) as error:
            lower_fusion(plan.physical_dag, descriptor)
        assert "PMADP303" in str(error.value)
        assert budget.live == 0
    with budget_scope(size) as budget:
        with budget.allocation(descriptor.to_dict(), "fusion-descriptor"):
            assert budget.live == size
        assert budget.live == 0


def test_concurrent_fused_invocations_own_snapshots(tmp_path):
    _seed(tmp_path)

    async def exercise():
        reports = []

        async def run():
            runtime, _, _, plan = setup(tmp_path)
            reports.append(
                await LocalScheduler().execute(
                    plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
                )
            )
            assert len(runtime.memory.get("out")) == 2

        async with anyio.create_task_group() as group:
            group.start_soon(run)
            group.start_soon(run)
        assert len(reports) == 2 and all(r.status.value == "succeeded" for r in reports)
        assert not list(tmp_path.glob("etlantic-parquet-*"))

    anyio.run(exercise)


def test_caller_cancel_drains_snapshot_and_never_registers(tmp_path, monkeypatch):
    _seed(tmp_path)
    entered, release, completed = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    original = pl.LazyFrame.collect

    def collect(self, *args, **kwargs):
        entered.set()
        assert release.wait(10)
        try:
            return original(self, *args, **kwargs)
        finally:
            completed.set()

    monkeypatch.setattr(pl.LazyFrame, "collect", collect)

    async def exercise():
        runtime, _, _, plan = setup(tmp_path)
        artifacts = ArtifactStore()
        returned = []

        async def run():
            try:
                returned.append(
                    await LocalScheduler().execute(
                        plan,
                        request=RunRequest(),
                        runtime=runtime,
                        workspace=tmp_path,
                        artifact_store=artifacts,
                    )
                )
            except PipelineCancelledError as error:
                assert error.report.status.value == "cancelled"

        async with anyio.create_task_group() as group:
            group.start_soon(run)
            with anyio.fail_after(10):
                while not entered.is_set():
                    await anyio.sleep(0.001)
            group.cancel_scope.cancel()
            release.set()
        assert completed.is_set()
        assert not artifacts.has("projected.result")
        assert runtime.memory.get("out") == []
        assert not list(tmp_path.glob("etlantic-parquet-*"))

    anyio.run(exercise)


def test_snapshot_cleanup_failure_retains_owner_and_blocks_sink(tmp_path, monkeypatch):
    # Historical catalogue ID retained. Buffer snapshots have no disk cleanup
    # failure: test actual native ownership through collection and release.
    import gc
    import weakref

    _seed(tmp_path)
    replacement = tmp_path / "replacement.parquet"
    pl.DataFrame({"key": [99], "enabled": [False], "unused": [0]}).write_parquet(
        replacement
    )
    original_scan = pl.scan_parquet
    original_collect = pl.LazyFrame.collect
    references = []
    collected = []

    def scan(source, *args, **kwargs):
        assert type(source) is bytes
        frame = original_scan(source, *args, **kwargs)
        references.append(weakref.ref(frame))
        return frame

    def collect(frame, *args, **kwargs):
        assert references and all(reference() is not None for reference in references)
        assert not list(tmp_path.glob("etlantic-parquet-*"))
        # The source writer replaces its input while native work owns the
        # snapshot. Collection and publication must still use the old bytes.
        replacement.replace(tmp_path / "raw.parquet")
        result = original_collect(frame, *args, **kwargs)
        collected.append(True)
        return result

    monkeypatch.setattr(pl, "scan_parquet", scan)
    monkeypatch.setattr(pl.LazyFrame, "collect", collect)

    async def exercise():
        runtime, _, _, plan = setup(tmp_path)
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
        )
        assert report.status.value == "succeeded", report.diagnostics
        assert not report.metadata.get("etlantic.cleanup_obligations")
        assert [row.key for row in runtime.memory.get("out")] == [1, 1]
        assert collected == [True]
        source = runtime.storage["polars-parquet"]
        assert not source.pending_snapshot_cleanups()
        return source

    source = anyio.run(exercise)
    gc.collect()
    assert not source.pending_snapshot_cleanups()
    assert not list(tmp_path.glob("etlantic-parquet-*"))
    assert all(reference() is None for reference in references)
    with pytest.raises(ValueError, match="Unknown snapshot"):
        source.reconcile_snapshot_cleanup("no-disk-snapshot")
