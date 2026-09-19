"""Actual static lowering, native scan and physical-authority reference proof."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import anyio
import pytest

pytest.importorskip("polars")
pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

import polars as pl
from tests.runtime.physical.fusion_fixture_0_54 import Reference

from etlantic import PipelineRuntime, Profile, __version__
from etlantic.exceptions import PipelineExecutionError
from etlantic.io_policy import SafeIoPolicy
from etlantic.plan import plan_from_json, plan_pipeline, plan_to_json
from etlantic.planning.adaptive import _handoff_contract
from etlantic.profile import PlacementTarget
from etlantic.registry import BindingDescriptor, PlanningContext, PluginDescriptor
from etlantic.runtime.physical_operations import OPERATION_SCHEMA
from etlantic.runtime.request import RetryPolicy, RunRequest, TimeoutPolicy
from etlantic.runtime.scheduler import LocalScheduler
from etlantic.transform import FusionDescriptor, PortableFusionCompiler
from etlantic.transform.fusion import PARQUET_CAPABILITY_EVIDENCE, fusion_digest
from etlantic_pandas import create_plugin as pandas_plugin
from etlantic_polars import (
    create_parquet_storage,
    create_plugin,
    create_transform_compiler,
)

pytestmark = [pytest.mark.polars, pytest.mark.pandas]


def setup(tmp_path, request=None, *, pipeline=Reference):
    request = request or RunRequest()
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_plugin())
    runtime.register_dataframe_plugin("pandas", pandas_plugin())
    source = create_parquet_storage()
    runtime.register_storage("polars-parquet", source)
    runtime.registry.register_binding(
        BindingDescriptor(
            "raw",
            "polars-parquet",
            location="raw.parquet",
            format="parquet",
            provider_version=__version__,
            config=source.configuration(),
            config_fingerprint=fusion_digest(source.configuration()),
            metadata={
                "etlantic.parquet_capability_evidence": PARQUET_CAPABILITY_EVIDENCE
            },
            root_ref="workspace",
        )
    )
    targets = {
        "scan": PlacementTarget(engine="polars"),
        "consumer": PlacementTarget(engine="pandas"),
    }
    profile = Profile(
        name="fusion-candidate",
        execution_strategy="adaptive",
        portable_transform_policy="require",
        placement_targets=targets,
        eligible_targets=tuple(targets),
        implementation_overrides={
            n.name: "scan" if index < 3 else "consumer"
            for index, n in enumerate(pipeline.build_graph().nodes)
        },
        safe_io={
            **SafeIoPolicy.for_root(tmp_path).to_dict(),
            "root_refs": ["workspace"],
        },
    )
    context = PlanningContext.create(profile, registry=runtime.registry)
    context.registry.transform_compilers["polars"] = create_transform_compiler()
    graph = pipeline.build_graph()
    consumer_edge = next(
        edge for edge in graph.edges if edge.consumer_node == "consumer"
    )
    evidence = _handoff_contract(
        targets["scan"], targets["consumer"], consumer_edge, context
    )
    evidence["evidence_ref"] = (
        "sha256:" + hashlib.sha256(b"frozen-reference-arrow/1").hexdigest()
    )
    context.registry.register_plugin(
        PluginDescriptor(
            "reference-arrow",
            "handoff",
            metadata={"handoff_evidence": [evidence]},
        )
    )
    graph = replace(
        graph,
        nodes=tuple(
            replace(
                node,
                metadata={
                    "etlantic.validation_required": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "validation",
                        "port": "result",
                        "outcome": "fail",
                    }
                },
            )
            if node.name == "consumer"
            else node
            for node in graph.nodes
        ),
    )
    # This core fixture supplies a real validation boundary in its stored graph.
    scoped = type(
        "ScopedReference", (pipeline,), {"build_graph": classmethod(lambda cls: graph)}
    )
    plan = plan_pipeline(scoped, profile=profile, request=request, context=context)
    return runtime, profile, context, plan


def test_static_plan_without_source_file_and_roundtrip(tmp_path):
    runtime, _, _, plan = setup(tmp_path)
    fused = [unit for unit in plan.physical_dag.units if len(unit.logical_nodes) == 3]
    assert len(fused) == 1
    assert plan.metadata["etlantic.planner_version"] == "0.54"
    descriptor = FusionDescriptor.from_dict(fused[0].metadata["etlantic.fusion"])
    assert descriptor.logical_nodes == ("raw", "filtered", "projected")
    assert isinstance(create_transform_compiler(), PortableFusionCompiler)
    assert plan_from_json(plan_to_json(plan)).fingerprint == plan.fingerprint
    assert not list(tmp_path.iterdir())
    assert runtime.memory.get("out") == []


@pytest.mark.parametrize("rows", [[], [1, None, 2, 1], [None, None], [2, 3]])
def test_actual_fused_query_arrow_consumer_validation_publication(tmp_path, rows):
    pl.DataFrame(
        {"key": rows, "enabled": [True] * len(rows), "unused": [99] * len(rows)},
        schema={"key": pl.Int64, "enabled": pl.Boolean, "unused": pl.Int64},
    ).write_parquet(tmp_path / "raw.parquet")

    async def exercise():
        runtime, _, _, plan = setup(tmp_path)
        report = await LocalScheduler().execute(
            plan_from_json(plan_to_json(plan)),
            request=RunRequest(),
            runtime=runtime,
            workspace=tmp_path,
        )
        assert report.status.value == "succeeded", report.diagnostics
        assert [row.key for row in runtime.memory.get("out")] == [
            key for key in rows if key == 1
        ]
        trace = report.metadata["etlantic.physical_trace"]
        proof = next(item["fusion"] for item in trace if "fusion" in item)
        assert proof["scan_predicate"] and proof["scan_projection"]
        assert proof["main_collections"] == 1
        assert sum(item["kind"] == "transfer" for item in trace) == 1
        assert sum(item["kind"] == "validation" for item in trace) == 1
        assert all(step.status.value == "succeeded" for step in report.steps)
        assert not list(tmp_path.glob("etlantic-parquet-*"))

    anyio.run(exercise)


def _seed(tmp_path):
    pl.DataFrame(
        {"key": [1, None, 2, 1], "enabled": [True] * 4, "unused": [99] * 4},
        schema={"key": pl.Int64, "enabled": pl.Boolean, "unused": pl.Int64},
    ).write_parquet(tmp_path / "raw.parquet")


def test_real_dispatch_single_collect_no_intermediate_node_bodies(
    tmp_path, monkeypatch
):
    from etlantic.runtime.orchestrator import LocalOrchestrator
    from etlantic_pandas.compiler import PandasTransformCompiler
    from etlantic_polars.compiler import PolarsTransformCompiler

    _seed(tmp_path)
    calls = []
    original_collect = pl.LazyFrame.collect
    original_fusion = PolarsTransformCompiler.compile_fusion
    original_consumer = PandasTransformCompiler.execute
    original_node = LocalOrchestrator._execute_node

    def collect(self, *args, **kwargs):
        calls.append("collect")
        return original_collect(self, *args, **kwargs)

    def compile_fusion(self, *args, **kwargs):
        calls.append("compile_fusion")
        return original_fusion(self, *args, **kwargs)

    async def consume(self, *args, **kwargs):
        calls.append("pandas")
        return await original_consumer(self, *args, **kwargs)

    async def node(self, **kwargs):
        calls.append(kwargs["name"])
        assert kwargs["name"] not in {"raw", "filtered", "projected"}
        return await original_node(self, **kwargs)

    monkeypatch.setattr(pl.LazyFrame, "collect", collect)
    monkeypatch.setattr(PolarsTransformCompiler, "compile_fusion", compile_fusion)
    monkeypatch.setattr(PandasTransformCompiler, "execute", consume)
    monkeypatch.setattr(LocalOrchestrator, "_execute_node", node)

    async def exercise():
        runtime, _, _, plan = setup(tmp_path)
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
        )
        assert report.status.value == "succeeded", report.diagnostics
        assert (
            calls.count("collect")
            == calls.count("compile_fusion")
            == calls.count("pandas")
            == 1
        )
        assert "consumer" in calls and "out" in calls
        assert [
            artifact.logical_output
            for artifact in report.artifacts
            if artifact.logical_output.startswith(("raw.", "filtered.", "projected."))
        ] == ["projected.result"]

    anyio.run(exercise)


@pytest.mark.parametrize("kind", ["config", "binding", "source", "middleware"])
def test_drift_rejects_atomically_before_read(tmp_path, monkeypatch, kind):
    runtime, _, _, plan = setup(tmp_path)
    from etlantic_polars import PolarsParquetStorage

    reads = []
    original = PolarsParquetStorage.open_scan

    def read(*args, **kwargs):
        reads.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(PolarsParquetStorage, "open_scan", read)
    if kind == "config":
        runtime.register_storage("polars-parquet", PolarsParquetStorage(max_rows=1))
    elif kind == "binding":
        runtime.registry.register_binding(
            replace(runtime.registry.bindings["raw"], location="other.parquet")
        )
    elif kind == "source":
        runtime.register_storage("polars-parquet", object())
    else:

        async def middleware(context, next_):
            return await next_()

        runtime.step_middleware.add(middleware)

    async def exercise():
        with pytest.raises(PipelineExecutionError) as error:
            await LocalScheduler().execute(
                plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
            )
        assert error.value.code in {"PMADP501", "PMADP522"}
        assert reads == [] and runtime.memory.get("out") == []
        assert not list(tmp_path.iterdir())

    anyio.run(exercise)


def test_stored_fusion_internal_route_tamper(tmp_path):
    import json

    _, _, _, plan = setup(tmp_path)
    document = json.loads(plan_to_json(plan))
    fused = next(
        unit
        for unit in document["physical_dag"]["units"]
        if len(unit["logical_nodes"]) == 3
    )
    fused["metadata"]["etlantic.internal_edges"][0][2] = "unknown"
    with pytest.raises(ValueError, match="PMADP403"):
        plan_from_json(json.dumps(document), verify=False)


def test_snapshot_schema_fault_does_not_hide_dropped_column(tmp_path):
    pl.DataFrame(
        {"key": [2], "enabled": [True], "unused": ["row-secret-canary"]}
    ).write_parquet(tmp_path / "raw.parquet")

    async def exercise():
        runtime, _, _, plan = setup(tmp_path)
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
        )
        assert report.status.value == "failed"
        assert runtime.memory.get("out") == []
        assert report.steps[0].status.value == "failed"
        assert all(step.status.value == "skipped" for step in report.steps[1:])
        import json

        assert "row-secret-canary" not in json.dumps(report.to_dict())
        assert not list(tmp_path.glob("etlantic-parquet-*"))

    anyio.run(exercise)


def test_compile_failure_is_attributed_without_publication(tmp_path, monkeypatch):
    from etlantic_polars.compiler import PolarsTransformCompiler

    _seed(tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeError("native-query-secret-canary")

    monkeypatch.setattr(PolarsTransformCompiler, "compile_fusion", fail)

    async def exercise():
        runtime, _, _, plan = setup(tmp_path)
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
        )
        assert report.status.value == "failed"
        statuses = {step.step_name: step.status.value for step in report.steps}
        assert statuses["filtered"] == "failed"
        assert (
            statuses["projected"]
            == statuses["consumer"]
            == statuses["out"]
            == "skipped"
        )
        import json

        assert "secret-canary" not in json.dumps(report.to_dict())
        assert runtime.memory.get("out") == []
        assert not list(tmp_path.glob("etlantic-parquet-*"))

    anyio.run(exercise)


def test_fused_retry_ineligible_without_source_effects(tmp_path):
    runtime, _, _, plan = setup(tmp_path, RunRequest(retry=RetryPolicy(max_attempts=2)))
    assert not any(
        unit.metadata.get("etlantic.fusion") for unit in plan.physical_dag.units
    )
    assert not list(tmp_path.iterdir())
    assert runtime.memory.get("out") == []


def test_native_deadline_drains_and_fences_late_registration(tmp_path, monkeypatch):
    import threading
    from contextlib import contextmanager

    from etlantic.runtime.artifacts import ArtifactStore

    _seed(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    scopes = []
    original_timeout = anyio.fail_after
    original = pl.LazyFrame.collect

    @contextmanager
    def synchronized_timeout(seconds, *, shield=False):
        if seconds != 0.1:
            with original_timeout(seconds, shield=shield) as scope:
                yield scope
        else:
            with original_timeout(None, shield=shield) as scope:
                scopes.append(scope)
                yield scope

    monkeypatch.setattr(anyio, "fail_after", synchronized_timeout)

    def collect(self, *args, **kwargs):
        entered.set()
        assert release.wait(10), "test must release the owned native worker"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pl.LazyFrame, "collect", collect)

    async def exercise():
        request = RunRequest(timeout=TimeoutPolicy(step_seconds=0.1))
        runtime, _, _, plan = setup(tmp_path, request)
        artifacts = ArtifactStore()

        async def expire_at_boundary():
            with original_timeout(10):
                while not entered.is_set():
                    await anyio.sleep(0.001)
            assert len(scopes) == 1
            scopes[0].deadline = anyio.current_time() + 0.02
            await anyio.sleep(0.05)
            release.set()

        async with anyio.create_task_group() as group:
            group.start_soon(expire_at_boundary)
            report = await LocalScheduler().execute(
                plan,
                request=request,
                runtime=runtime,
                workspace=tmp_path,
                artifact_store=artifacts,
            )
        assert report.status.value == "failed"
        assert entered.is_set()
        assert not artifacts.has("projected.result")
        assert runtime.memory.get("out") == []
        assert not list(tmp_path.glob("etlantic-parquet-*"))

    anyio.run(exercise)
