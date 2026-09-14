"""Executed five-family portable differential and boundary qualification."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import anyio
import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    Transformation,
    __version__,
)
from etlantic.exceptions import PipelineExecutionError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan import plan_from_json, plan_pipeline, plan_to_json
from etlantic.planning.adaptive import _handoff_contract
from etlantic.profile import PlacementTarget, Profile
from etlantic.registry import PlanningContext, PluginDescriptor
from etlantic.runtime.execute import arun_pipeline
from etlantic.runtime.physical_operations import OPERATION_SCHEMA
from etlantic.runtime.request import RetryPolicy, RunRequest, RunSelection
from etlantic.runtime.scheduler import LocalScheduler

pytestmark = [pytest.mark.polars, pytest.mark.pandas]


class Row(Data):
    id: int | None


class Project(Transformation):
    source: Input[Row]
    result: Output[Row]


@Project.portable
def project(source):
    return source.select("id")


class Pair(Transformation):
    source: Input[Row]
    left: Output[Row]
    right: Output[Row]


@Pair.portable
def pair(source):
    return {"left": source.select("id"), "right": source.select("id")}


class Join(Transformation):
    left: Input[Row]
    right: Input[Row]
    result: Output[Row]


@Join.portable
def join(left, right):
    return left.select("id")


class Chain(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    first = Project.step(source=raw)
    second = Project.step(source=first.result)
    out: Load[Row] = Load(input=second.result, asset="out")


class BindingAliasCollision(Pipeline):
    """Source asset intentionally overlaps the sink node name."""

    raw: Extract[Row] = Extract(asset="out")
    first = Project.step(source=raw)
    second = Project.step(source=first.result)
    out: Load[Row] = Load(input=second.result, asset="destination")


class Diamond(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    left = Project.step(source=raw)
    right = Project.step(source=raw)
    joined = Join.step(left=left.result, right=right.result)
    out: Load[Row] = Load(input=joined.result, asset="out")


class Fanout(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    shared = Project.step(source=raw)
    left = Project.step(source=shared.result)
    right = Project.step(source=shared.result)
    left_out: Load[Row] = Load(input=left.result, asset="left-out")
    right_out: Load[Row] = Load(input=right.result, asset="right-out")


class Dual(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    pair = Pair.step(source=raw)
    joined = Join.step(left=pair.left, right=pair.right)
    out: Load[Row] = Load(input=joined.result, asset="out")


def setup(
    pipeline: Any, families: tuple[str, ...], request: RunRequest
) -> tuple[Any, Any, Any]:
    import etlantic_pandas
    import etlantic_polars

    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", etlantic_polars.create_plugin())
    runtime.register_dataframe_plugin("pandas", etlantic_pandas.create_plugin())
    targets = {
        str(i): PlacementTarget(engine=family) for i, family in enumerate(families)
    }
    graph = pipeline.build_graph()
    assignments = {n.name: "0" for n in graph.nodes}
    if len(families) == 2:
        consumer = "joined" if pipeline is Dual else "second"
        after_cut = False
        for node in graph.nodes:
            after_cut = after_cut or node.name == consumer
            if after_cut:
                assignments[node.name] = "1"
    profile = Profile(
        name="qualification-0.53",
        execution_strategy="adaptive",
        portable_transform_policy="require",
        placement_targets=targets,
        eligible_targets=tuple(targets),
        implementation_overrides=assignments,
    )
    context = PlanningContext.create(profile, registry=runtime.registry)
    for edge in graph.edges:
        source, destination = (
            assignments[edge.producer_node],
            assignments[edge.consumer_node],
        )
        if source == destination:
            continue
        evidence = _handoff_contract(
            targets[source], targets[destination], edge, context
        )
        evidence["evidence_ref"] = (
            "sha256:"
            + hashlib.sha256(
                f"{source}:{destination}:{edge.producer_port}:{edge.consumer_port}".encode()
            ).hexdigest()
        )
        context.registry.register_plugin(
            PluginDescriptor(
                name=f"qualification-{edge.producer_port}-{edge.consumer_port}",
                kind="handoff",
                version="1",
                metadata={"handoff_evidence": [evidence]},
            )
        )
    plan = plan_pipeline(pipeline, profile=profile, request=request, context=context)
    return runtime, profile, plan


FAMILIES = [
    ("local",),
    ("polars",),
    ("pandas",),
    ("polars", "pandas"),
    ("pandas", "polars"),
]


@pytest.mark.parametrize("families", FAMILIES)
@pytest.mark.parametrize("rows", [[], [{"id": 1}, {"id": None}]])
def test_five_family_stored_differential(
    families: tuple[str, ...], rows: list[Any]
) -> None:
    async def exercise() -> None:
        request = RunRequest()
        runtime, _profile, plan = setup(Chain, families, request)
        runtime.memory.seed("rows", rows)
        report = await LocalScheduler().execute(
            plan_from_json(plan_to_json(plan)), request=request, runtime=runtime
        )
        baseline = PipelineRuntime()
        baseline.memory.seed("rows", rows)
        overrides = {
            n.name: families[1]
            if len(families) == 2 and n.name in {"second", "out"}
            else families[0]
            for n in Chain.build_graph().nodes
        }
        explicit = await arun_pipeline(
            Chain,
            profile=Profile(
                name="explicit-baseline",
                dataframe_engine=families[0],
                portable_transform_policy="require",
                implementation_overrides=overrides,
            ),
            runtime=baseline,
        )
        assert report.status == explicit.status
        assert [row.id for row in runtime.memory.get("out")] == [
            row.id for row in baseline.memory.get("out")
        ]
        assert [(s.step_name, s.status, s.attempts) for s in report.steps] == [
            (s.step_name, s.status, s.attempts) for s in explicit.steps
        ]
        assert report.summary.total_steps == 4
        assert report.metadata["etlantic.publication_receipts"]
        transfers = [
            t
            for t in report.metadata["etlantic.physical_trace"]
            if t["kind"] == "transfer"
        ]
        assert len(transfers) == (1 if len(families) == 2 else 0)

    anyio.run(exercise)


@pytest.mark.parametrize("pipeline", [Diamond, Fanout])
@pytest.mark.parametrize("family", ["local", "polars", "pandas"])
def test_exact_single_target_branch_families(pipeline: Any, family: str) -> None:
    async def exercise() -> None:
        request = RunRequest(metadata={"concurrency": 2})
        runtime, _, plan = setup(pipeline, (family,), request)
        runtime.memory.seed("rows", [{"id": 1}, {"id": None}])
        report = await LocalScheduler().execute(
            plan, request=request, runtime=runtime, pipeline_cls=pipeline
        )
        assert report.status.value == "succeeded", report.diagnostics
        bindings = ["out"] if pipeline is Diamond else ["left-out", "right-out"]
        assert all(
            [row.id for row in runtime.memory.get(binding)] == [1, None]
            for binding in bindings
        )
        assert report.summary.succeeded == len(plan.logical_graph.nodes)

    anyio.run(exercise)


@pytest.mark.parametrize("families", [("polars", "pandas"), ("pandas", "polars")])
def test_distinct_directional_ports(families: tuple[str, ...]) -> None:
    async def exercise() -> None:
        runtime, _, plan = setup(Dual, families, RunRequest())
        runtime.memory.seed("rows", [{"id": 1}, {"id": None}])
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime
        )
        assert report.status.value == "succeeded", report.diagnostics
        assert [row.id for row in runtime.memory.get("out")] == [1, None]
        transfers = [
            t
            for t in report.metadata["etlantic.physical_trace"]
            if t["kind"] == "transfer"
        ]
        assert len(transfers) == 2 and len({t["unit"] for t in transfers}) == 2

    anyio.run(exercise)


def test_partial_chain_ending_at_step() -> None:
    async def exercise() -> None:
        request = RunRequest(selection=RunSelection.until("first"))
        runtime, _, plan = setup(Chain, ("local",), request)
        runtime.memory.seed("rows", [{"id": 1}])
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert [(s.step_name, s.status.value) for s in report.steps] == [
            ("raw", "succeeded"),
            ("first", "succeeded"),
        ]
        assert runtime.memory.get("out") == []

    anyio.run(exercise)


def test_retry_safety_rejects_before_reads() -> None:
    async def exercise() -> None:
        request = RunRequest(retry=RetryPolicy(max_attempts=2))
        runtime, _, plan = setup(Chain, ("local",), request)
        with pytest.raises(PipelineExecutionError, match="retry safety"):
            await LocalScheduler().execute(plan, request=request, runtime=runtime)

    anyio.run(exercise)


@pytest.mark.parametrize("family", ["local", "polars", "pandas"])
def test_checkpoint_and_reuse_execute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, family: str
) -> None:
    graph = Chain.build_graph()
    graph = replace(
        graph,
        nodes=tuple(
            replace(
                node,
                metadata={
                    **dict(node.metadata),
                    "etlantic.materialization_required": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "materialization",
                        "checkpoint": "first",
                    },
                    "etlantic.reuse_artifact": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "reuse",
                        "checkpoint": "first",
                    },
                },
            )
            if node.name == "first"
            else node
            for node in graph.nodes
        ),
    )
    monkeypatch.setattr(Chain, "build_graph", classmethod(lambda cls: graph))

    async def exercise() -> None:
        runtime, _, plan = setup(Chain, (family,), RunRequest())
        runtime.memory.seed("rows", [{"id": 1}])
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime, workspace=tmp_path
        )
        assert report.status.value == "succeeded", report.diagnostics
        assert (tmp_path / "checkpoint-first.json").is_file()
        assert any(
            t.get("selection") == "checkpoint"
            for t in report.metadata["etlantic.physical_trace"]
        )

    anyio.run(exercise)


@pytest.mark.parametrize("families", FAMILIES)
@pytest.mark.parametrize("max_rows", [1, 2])
def test_collection_executes_bounds(families, max_rows, monkeypatch):
    graph = Chain.build_graph()
    graph = replace(
        graph,
        nodes=tuple(
            replace(
                node,
                metadata={
                    **dict(node.metadata),
                    "etlantic.collection_required": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "collection",
                        "max_rows": max_rows,
                        "max_bytes": 1024,
                    },
                },
            )
            if node.name == "second"
            else node
            for node in graph.nodes
        ),
    )
    monkeypatch.setattr(Chain, "build_graph", classmethod(lambda cls: graph))

    async def exercise():
        runtime, _, plan = setup(Chain, families, RunRequest())
        runtime.memory.seed("rows", [{"id": 1}, {"id": None}])
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime
        )
        collections = [
            trace
            for trace in report.metadata["etlantic.physical_trace"]
            if trace["kind"] == "collection"
        ]
        assert len(collections) == 1
        if max_rows == 1:
            assert collections[0]["status"] == "failed"
            assert runtime.memory.get("out") == []
        else:
            assert collections[0]["row_count"] == 2
            assert [row.id for row in runtime.memory.get("out")] == [1, None]

    anyio.run(exercise)


@pytest.mark.parametrize("families", FAMILIES)
def test_definite_publication_failure_through_admitted_provider(families, monkeypatch):
    async def exercise():
        runtime, _, plan = setup(Chain, families, RunRequest())
        runtime.memory.seed("rows", [{"id": 1}])
        calls = []

        async def fail(**kwargs):
            calls.append("write")
            raise ValueError("Definite failure before commit")

        monkeypatch.setattr(runtime.memory, "write", fail)
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime
        )
        assert calls == ["write"]
        assert runtime.memory.get("out") == []
        assert report.steps[-1].status.value == "failed"
        assert not report.metadata["etlantic.unknown_publications"]

    anyio.run(exercise)


@pytest.mark.parametrize("provider", ["json", "csv"])
def test_atomic_file_publication(provider, tmp_path):
    import csv
    import json

    from etlantic.io_policy import SafeIoPolicy
    from etlantic.runtime.adaptive_publication import publish_file

    async def exercise():
        destination = tmp_path / ("out." + provider)

        async def write(identifier, rows):
            receipt = await publish_file(
                provider=provider,
                location=str(destination),
                data=rows,
                contract_type=Row,
                policy=SafeIoPolicy.for_root(tmp_path),
                publication_id=identifier,
            )
            assert receipt.status == "committed"

        async with anyio.create_task_group() as group:
            group.start_soon(write, "pub:first", [{"id": 1}] * 200)
            group.start_soon(write, "pub:second", [{"id": 2}] * 200)
        if provider == "json":
            rows = json.loads(destination.read_text())
        else:
            rows = list(csv.DictReader(destination.open()))
        assert len(rows) == 200 and len({str(row["id"]) for row in rows}) == 1
        assert not list(tmp_path.glob("*.tmp"))

    anyio.run(exercise)


def test_qualified_executor_cancel_and_cleanup_drain() -> None:
    from etlantic.runtime.adaptive_support import support_row_for
    from etlantic.runtime.physical_protocol import (
        PhysicalExecutorInfo,
        PhysicalUnitSupport,
    )
    from etlantic.runtime.request import CancellationPolicy, TimeoutPolicy

    async def exercise():
        request = RunRequest(
            timeout=TimeoutPolicy(run_seconds=0.05),
            cancellation=CancellationPolicy(abandon_after_seconds=0.2),
        )
        runtime, _, plan = setup(Chain, ("local",), request)
        support = support_row_for(plan)
        calls = []

        class Executor:
            info = PhysicalExecutorInfo(
                "etlantic.physical.local/1",
                "etlantic",
                __version__,
                capability_fingerprint=plan.inventory.targets[0].capability_fingerprint,
                evidence_refs=support.evidence_refs,
            )

            def analyze(self, plan, unit):
                return PhysicalUnitSupport(True, self.info.identity)

            async def execute(self, context):
                calls.append("started")
                await anyio.sleep_forever()

            async def cancel(self, context):
                await anyio.sleep(0)
                calls.append("cancelled")

            async def cleanup(self, context, result):
                await anyio.sleep(0)
                calls.append("cleaned")
                return ()

        runtime.physical_executors = {"local": Executor()}
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert calls == ["started", "cancelled", "cleaned"]
        assert any(d.code == "PMEXEC408" for d in report.diagnostics)
        assert not report.metadata["etlantic.cleanup_obligations"]

    anyio.run(exercise)


def test_qualified_executor_routes_outputs_and_retains_lifetime() -> None:
    from etlantic.connectors.models import CommitReceipt
    from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
    from etlantic.runtime.adaptive_support import support_row_for
    from etlantic.runtime.physical_protocol import (
        PhysicalArtifactHandle,
        PhysicalExecutorInfo,
        PhysicalLogicalOutcome,
        PhysicalUnitResult,
        PhysicalUnitSupport,
    )

    async def exercise():
        request = RunRequest()
        runtime, _, plan = setup(Chain, ("local",), request)
        support = support_row_for(plan)
        calls = []

        class Executor:
            info = PhysicalExecutorInfo(
                "etlantic.physical.local/1",
                "etlantic",
                __version__,
                capability_fingerprint=plan.inventory.targets[0].capability_fingerprint,
                evidence_refs=support.evidence_refs,
            )

            def analyze(self, plan, unit):
                return PhysicalUnitSupport(True, self.info.identity)

            async def execute(self, context):
                unit = context.unit
                if unit.kind.value == "publication":
                    calls.append("published")
                    await runtime.memory.write(
                        binding="out",
                        location=None,
                        data=[{"id": 1}],
                        contract_type=Row,
                        context={},
                    )
                    return PhysicalUnitResult(
                        unit.identity,
                        unit.target_identity,
                        "succeeded",
                        commit_receipt=CommitReceipt(
                            "committed", publication_id="pub:test"
                        ),
                    )
                name = unit.logical_nodes[0]
                calls.append(name)
                node = context.plan.logical_graph.node_map()[name]
                if name != "raw":
                    assert context.inputs and context.adapters["dataframe"] is not None
                    assert all(
                        isinstance(handle.ref, ArtifactRef)
                        for handle in context.inputs.values()
                    )
                outputs = tuple(
                    PhysicalArtifactHandle(
                        ArtifactRef(
                            identity=f"artifact:{name}:{port.name}",
                            logical_output=f"{name}.{port.name}",
                            strategy=ArtifactStrategy.IN_MEMORY,
                        ),
                        [{"id": 1}],
                        unit.target_identity,
                    )
                    for port in node.outputs
                )
                return PhysicalUnitResult(
                    unit.identity,
                    unit.target_identity,
                    "succeeded",
                    outputs=outputs,
                    logical_outcomes=(
                        PhysicalLogicalOutcome(name, "succeeded", records_out=1),
                    ),
                )

            async def cancel(self, context):
                pass

            async def cleanup(self, context, result):
                assert "published" in calls
                calls.append("cleaned")
                return ()

        runtime.physical_executors = {"local": Executor()}
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert report.status.value == "succeeded", report.diagnostics
        assert [row.id for row in runtime.memory.get("out")] == [1]
        assert calls.count("cleaned") == len(plan.physical_dag.units)
        assert report.summary.succeeded == 4

    anyio.run(exercise)


@pytest.mark.parametrize("family", ["local", "polars", "pandas"])
@pytest.mark.parametrize("invalid", [False, True])
def test_physical_validation_is_executed(family, invalid, monkeypatch):
    graph = Chain.build_graph()
    graph = replace(
        graph,
        nodes=tuple(
            replace(
                node,
                metadata={
                    **dict(node.metadata),
                    "etlantic.validation_required": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "validation",
                        "port": "result",
                        "outcome": "fail",
                    },
                },
            )
            if node.name == "first"
            else node
            for node in graph.nodes
        ),
    )
    monkeypatch.setattr(Chain, "build_graph", classmethod(lambda cls: graph))

    async def exercise():
        runtime, _, plan = setup(Chain, (family,), RunRequest())
        runtime.memory.seed("rows", [{"id": 1}])
        from etlantic.runtime.dataframe_exec import resolve_dataframe_plugin

        plugin = resolve_dataframe_plugin(family, plugins=runtime.dataframe_plugins)
        runtime.dataframe_plugins[family] = plugin
        original = plugin.validate_frame
        calls = []

        def validate(value, **kwargs):
            context = kwargs["context"]
            if context.metadata.get("physical_unit"):
                calls.append("barrier")
                if invalid:
                    value = plugin.materialize_input(
                        [{"id": "invalid-integer"}],
                        contract_type=None,
                        context=context,
                        port_name="result",
                    )
            return original(value, **kwargs)

        monkeypatch.setattr(plugin, "validate_frame", validate)
        report = await LocalScheduler().execute(
            plan, request=RunRequest(), runtime=runtime
        )
        assert calls == ["barrier"]
        first = next(step for step in report.steps if step.step_name == "first")
        if invalid:
            assert (
                first.status.value == "failed" and first.failure_stage == "validation"
            )
            assert runtime.memory.get("out") == []
        else:
            assert report.status.value == "succeeded"
            assert [row.id for row in runtime.memory.get("out")] == [1]

    anyio.run(exercise)


@pytest.mark.parametrize("provider", ["json", "csv"])
def test_public_scheduler_file_receipt(provider, tmp_path):
    import csv
    import json

    from etlantic.registry import BindingDescriptor

    async def exercise():
        destination = tmp_path / ("out." + provider)
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}, {"id": None}])
        runtime.registry.register_binding(
            BindingDescriptor("out", provider, location=str(destination))
        )
        profile = Profile(
            name="file-qualified",
            execution_strategy="adaptive",
            portable_transform_policy="require",
            placement_targets={"local": PlacementTarget(engine="local")},
            eligible_targets=("local",),
        )
        request = RunRequest()
        context = PlanningContext.create(profile, registry=runtime.registry)
        plan = plan_pipeline(Chain, profile=profile, request=request, context=context)
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert report.status.value == "succeeded", report.diagnostics
        assert (
            report.metadata["etlantic.publication_receipts"][0]["status"] == "committed"
        )
        if provider == "json":
            assert json.loads(destination.read_text()) == [{"id": 1}, {"id": None}]
        else:
            with destination.open() as stream:
                assert list(csv.DictReader(stream)) == [{"id": "1"}, {"id": ""}]

    anyio.run(exercise)


def test_missing_captured_binding_rejects_before_physical_effects(tmp_path):
    """A removed explicit binding cannot silently fall back to memory."""
    from etlantic.registry import BindingDescriptor

    async def exercise():
        destination = tmp_path / "out.json"
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        runtime.registry.register_binding(
            BindingDescriptor("out", "json", location=str(destination))
        )
        profile = Profile(
            name="missing-binding",
            execution_strategy="adaptive",
            portable_transform_policy="require",
            placement_targets={"local": PlacementTarget(engine="local")},
            eligible_targets=("local",),
        )
        request = RunRequest()
        plan = plan_pipeline(
            Chain,
            profile=profile,
            request=request,
            context=PlanningContext.create(profile, registry=runtime.registry),
        )
        runtime.registry.bindings.pop("out")
        starts: list[str] = []
        original_emit = runtime.events.emit

        def emit(event):
            if event.kind == "physical_unit_started":
                starts.append(event.kind)
            original_emit(event)

        runtime.events.emit = emit
        with pytest.raises(PipelineExecutionError) as exc_info:
            await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert exc_info.value.code == "PMADP501"
        assert exc_info.value.stage == "admission"
        assert starts == []
        assert not destination.exists()
        assert runtime.memory.get("out") == []

    anyio.run(exercise)


def test_admitted_binding_snapshot_survives_post_admission_registry_mutation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """The host executes the descriptor admitted for this invocation."""
    from etlantic.registry import BindingDescriptor
    from etlantic.runtime import physical_host

    async def exercise():
        destination = tmp_path / "admitted.json"
        replacement = tmp_path / "replacement.json"
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        runtime.registry.register_binding(
            BindingDescriptor("out", "json", location=str(destination))
        )
        profile = Profile(
            name="binding-snapshot",
            execution_strategy="adaptive",
            portable_transform_policy="require",
            placement_targets={"local": PlacementTarget(engine="local")},
            eligible_targets=("local",),
        )
        request = RunRequest()
        plan = plan_pipeline(
            Chain,
            profile=profile,
            request=request,
            context=PlanningContext.create(profile, registry=runtime.registry),
        )
        original_build = physical_host.pipeline_plan_for_adaptive

        def mutate_registry_after_admission(*args, **kwargs):
            runtime.registry.register_binding(
                BindingDescriptor("out", "json", location=str(replacement))
            )
            return original_build(*args, **kwargs)

        monkeypatch.setattr(
            physical_host, "pipeline_plan_for_adaptive", mutate_registry_after_admission
        )
        await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert destination.exists()
        assert not replacement.exists()
        assert runtime.memory.get("out") == []

    anyio.run(exercise)


def test_implicit_source_cannot_resolve_another_node_binding(tmp_path):
    """Node-keyed adaptive pins never become an asset-name lookup table."""
    import json

    from etlantic.registry import BindingDescriptor

    async def exercise():
        destination = tmp_path / "destination.json"
        destination.write_text('[{"id": 99}]')
        runtime = PipelineRuntime()
        runtime.memory.seed("out", [{"id": 1}])
        runtime.registry.register_binding(
            BindingDescriptor("destination", "json", location=str(destination))
        )
        profile = Profile(
            name="binding-alias-collision",
            execution_strategy="adaptive",
            portable_transform_policy="require",
            placement_targets={"local": PlacementTarget(engine="local")},
            eligible_targets=("local",),
        )
        request = RunRequest()
        plan = plan_pipeline(
            BindingAliasCollision,
            profile=profile,
            request=request,
            context=PlanningContext.create(profile, registry=runtime.registry),
        )
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert report.status.value == "succeeded", report.diagnostics
        assert json.loads(destination.read_text()) == [{"id": 1}]

    anyio.run(exercise)
