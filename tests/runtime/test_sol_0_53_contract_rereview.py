"""Independent checks of unresolved phase 0.53 contract invariants.

These retain the original FINAL IDs and supplement the focused reproducers.
They intentionally fail only for in-scope release blockers.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import anyio
import pytest

from etlantic import Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.exceptions import PipelineExecutionError, PipelineValidationError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan import plan_pipeline
from etlantic.profile import Profile
from etlantic.runtime.adaptive_support import support_row_for
from etlantic.runtime.physical_protocol import (
    PhysicalExecutorInfo,
    PhysicalUnitFailure,
    PhysicalUnitResult,
    PhysicalUnitSupport,
)
from etlantic.runtime.request import RunRequest, RunSelection, TimeoutPolicy
from etlantic.runtime.scheduler import LocalScheduler
from tests.plan.test_adaptive_planner_0_52 import Sample, adaptive_profile
from tests.runtime.test_adaptive_execution_0_53 import CrossRow, CrossStep
from tests.runtime.test_sol_0_53_rereview import Fanout


class Join(Transformation):
    left: Input[CrossRow]
    right: Input[CrossRow]
    result: Output[CrossRow]


@Join.portable
def join_project(left, right):
    return left.select("id")


class Diamond(Pipeline):
    raw: Extract[CrossRow] = Extract(asset="cross-rows")
    left = CrossStep.step(source=raw)
    right = CrossStep.step(source=raw)
    joined = Join.step(left=left.result, right=right.result)
    out: Load[CrossRow] = Load(input=joined.result, asset="cross-out")


def test_final_002_exact_required_diamond_is_qualified() -> None:
    plan = plan_pipeline(Diamond, profile=adaptive_profile(), request=RunRequest())
    assert len(plan.logical_graph.nodes) == 5
    assert len(plan.logical_graph.edges) == 5
    row = support_row_for(plan)
    assert row is not None and row.pattern == "diamond/1"


def test_final_001_executor_replacement_after_admission_is_never_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exercise() -> None:
        runtime = PipelineRuntime()
        request = RunRequest()
        plan = plan_pipeline(Sample, profile=adaptive_profile(), request=request)
        calls: list[str] = []

        class Executor:
            def __init__(self, identity: str) -> None:
                self.info = PhysicalExecutorInfo(identity, "sol-sentinel", "1")

            def analyze(self, plan: Any, unit: Any) -> PhysicalUnitSupport:
                calls.append("analyze:" + self.info.identity)
                return PhysicalUnitSupport(True, self.info.identity)

            async def execute(self, context: Any) -> PhysicalUnitResult:
                calls.append("execute:" + self.info.identity)
                return PhysicalUnitResult(
                    context.unit.identity, context.unit.target_identity, "failed"
                )

        runtime.physical_executors = {"local": Executor("admitted")}  # type: ignore[attr-defined]

        from etlantic.runtime.events import EventBus

        original_emit = EventBus.emit

        def emit(bus: Any, event: Any) -> None:
            if event.kind == "run_started":
                runtime.physical_executors["local"] = Executor("replacement")  # type: ignore[attr-defined]
            original_emit(bus, event)

        monkeypatch.setattr(EventBus, "emit", emit)
        try:
            await LocalScheduler().execute(plan, request=request, runtime=runtime)
        except PipelineExecutionError as exc:
            assert exc.stage == "admission"
        assert "execute:replacement" not in calls, calls

    anyio.run(exercise)


@pytest.mark.polars
@pytest.mark.pandas
def test_final_007_post_compile_schema_deadline_fences_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The member deadline covers schema work before exposing compiler outputs."""
    from tests.runtime.physical.test_qualification_0_53 import Chain, setup

    async def exercise() -> None:
        request = RunRequest(timeout=TimeoutPolicy(step_seconds=0.1))
        runtime, _, plan = setup(Chain, ("polars",), request)
        runtime.memory.seed("rows", [{"id": 1}])
        plugin = runtime.dataframe_plugins["polars"]
        original = plugin.inspect_schema
        entered: list[str] = []

        def inspect_schema(*args: Any, **kwargs: Any) -> Any:
            if kwargs.get("identity") == "observed:first":
                # Preserve the admitted compiler, schema operation and output;
                # inject latency at the real post-compile inspection boundary.
                entered.append("first_schema")
                time.sleep(0.3)
            return original(*args, **kwargs)

        monkeypatch.setattr(plugin, "inspect_schema", inspect_schema)
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        first = next(step for step in report.steps if step.step_name == "first")
        assert entered, "The post-compile schema operation must be exercised"
        assert first.status.value == "timed_out", first
        assert first.attempts == 1
        assert (
            next(
                step for step in report.steps if step.step_name == "second"
            ).status.value
            == "skipped"
        )
        assert not any(a.logical_output == "first.result" for a in report.artifacts)
        assert runtime.memory.get("out") == []
        assert report.status.value != "succeeded"

    anyio.run(exercise)


@pytest.mark.polars
@pytest.mark.pandas
def test_final_007_boundary_deadline_cannot_register_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A boundary's private side effects also need the run visibility fence."""
    from etlantic.runtime.physical_operations import OPERATION_SCHEMA
    from tests.runtime.physical.test_qualification_0_53 import Chain, setup

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
                        "checkpoint": "memory",
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
        request = RunRequest(timeout=TimeoutPolicy(run_seconds=2.0))
        runtime, _, plan = setup(Chain, ("polars",), request)
        runtime.memory.seed("rows", [{"id": 1}])
        plugin = runtime.dataframe_plugins["polars"]
        original = plugin.ensure_ownership
        entered: list[str] = []

        def ensure_ownership(value: Any, **kwargs: Any) -> Any:
            copied = original(value, **kwargs)
            context = kwargs["context"]
            if context.step_name == "first" and "physical_unit" in context.metadata:
                entered.append("materialization")
                # Cross the actual deadline inside the admitted operation;
                # retain its real result rather than replacing it with a fake.
                time.sleep(
                    max(0.0, anyio.current_effective_deadline() - anyio.current_time())
                    + 0.05
                )
            return copied

        monkeypatch.setattr(plugin, "ensure_ownership", ensure_ownership)
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert entered, "The admitted materialization must be exercised"
        assert report.status.value != "succeeded"
        assert runtime.memory.get("out") == []
        assert any(d.code == "PMEXEC408" for d in report.diagnostics)
        assert not any(
            ref.identity.startswith("checkpoint:") for ref in report.artifacts
        ), "An expired boundary must not register an available checkpoint"
        assert (
            next(
                step for step in report.steps if step.step_name == "second"
            ).status.value
            == "skipped"
        )

    anyio.run(exercise)


@pytest.mark.polars
@pytest.mark.pandas
def test_final_005_executor_deadline_retains_committed_receipt() -> None:
    """A late executor result cannot erase evidence of an actual publication."""
    from etlantic.connectors.models import CommitReceipt
    from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
    from etlantic.runtime.physical_protocol import (
        PhysicalArtifactHandle,
        PhysicalLogicalOutcome,
    )
    from tests.runtime.physical.test_qualification_0_53 import Chain, Row, setup

    async def exercise() -> None:
        request = RunRequest(timeout=TimeoutPolicy(run_seconds=2.0))
        runtime, _, plan = setup(Chain, ("local",), request)
        support = support_row_for(plan)
        assert support is not None
        committed: list[str] = []
        publication_id = "pub:sol-final-005-executor-deadline"

        class Executor:
            info = PhysicalExecutorInfo(
                "etlantic.physical.local/1",
                "etlantic",
                "0.52.1",
                capability_fingerprint=plan.inventory.targets[0].capability_fingerprint,
                evidence_refs=support.evidence_refs,
            )

            def analyze(self, plan: Any, unit: Any) -> PhysicalUnitSupport:
                return PhysicalUnitSupport(True, self.info.identity)

            async def execute(self, context: Any) -> PhysicalUnitResult:
                unit = context.unit
                if unit.kind.value == "publication":
                    await runtime.memory.write(
                        binding="out",
                        location=None,
                        data=[{"id": 1}],
                        contract_type=Row,
                        context={},
                    )
                    committed.append(publication_id)
                    time.sleep(
                        max(
                            0.0,
                            anyio.current_effective_deadline() - anyio.current_time(),
                        )
                        + 0.05
                    )
                    return PhysicalUnitResult(
                        unit.identity,
                        unit.target_identity,
                        "succeeded",
                        commit_receipt=CommitReceipt(
                            "committed", publication_id=publication_id
                        ),
                    )
                name = unit.logical_nodes[0]
                node = context.plan.logical_graph.node_map()[name]
                return PhysicalUnitResult(
                    unit.identity,
                    unit.target_identity,
                    "succeeded",
                    outputs=tuple(
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
                    ),
                    logical_outcomes=(PhysicalLogicalOutcome(name, "succeeded"),),
                )

            async def cancel(self, context: Any) -> None:
                pass

            async def cleanup(self, context: Any, result: Any) -> tuple[Any, ...]:
                return ()

        runtime.physical_executors = {"local": Executor()}  # type: ignore[attr-defined]
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert committed == [publication_id], "The actual effect must occur once"
        assert [row.id for row in runtime.memory.get("out")] == [1]
        assert report.status.value != "succeeded"
        assert any(d.code == "PMEXEC408" for d in report.diagnostics)
        receipts = report.metadata.get("etlantic.publication_receipts", [])
        unknown = report.metadata.get("etlantic.unknown_publications", [])
        assert any(
            record.get("publication_id") == publication_id
            for record in [*receipts, *unknown]
        ), "The failed run must retain the known receipt or its reconciliation ID"
        if any(record.get("publication_id") == publication_id for record in unknown):
            assert any(d.code == "PMADP524" for d in report.diagnostics)

    anyio.run(exercise)


def test_final_003_truthy_boundary_flag_cannot_authorize_noop_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = Sample.build_graph()
    graph = replace(
        graph,
        nodes=tuple(
            replace(
                node,
                metadata={
                    **dict(node.metadata),
                    "etlantic.materialization_required": True,
                },
            )
            if node.name == "raw"
            else node
            for node in graph.nodes
        ),
    )
    monkeypatch.setattr(Sample, "build_graph", classmethod(lambda cls: graph))

    async def exercise() -> None:
        request = RunRequest()
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 7}])
        effects: list[str] = []
        original_read = runtime.memory.read
        original_write = runtime.memory.write

        async def read(**kwargs: Any) -> Any:
            effects.append("read")
            return await original_read(**kwargs)

        async def write(**kwargs: Any) -> Any:
            effects.append("write")
            return await original_write(**kwargs)

        monkeypatch.setattr(runtime.memory, "read", read)
        monkeypatch.setattr(runtime.memory, "write", write)
        rejected = False
        try:
            plan = plan_pipeline(Sample, profile=adaptive_profile(), request=request)
            assert any(
                unit.kind == "materialization" for unit in plan.physical_dag.units
            )
            await LocalScheduler().execute(plan, request=request, runtime=runtime)
        except PipelineValidationError:
            rejected = True
        except PipelineExecutionError as exc:
            rejected = exc.stage == "admission"
        # The executable contract says truthy flags alone do not authorize a
        # checkpoint operation. No serializer/owner/ref is supplied here.
        assert rejected and effects == [], (rejected, effects)

    anyio.run(exercise)


def test_final_004_supported_source_only_selection_executes() -> None:
    async def exercise() -> None:
        request = RunRequest(selection=RunSelection.until("raw"))
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        plan = plan_pipeline(Sample, profile=adaptive_profile(), request=request)
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert [(step.step_name, step.status.value) for step in report.steps] == [
            ("raw", "succeeded")
        ]
        assert runtime.memory.get("out") == []

    anyio.run(exercise)


def test_final_004_profile_concurrency_precedes_request_concurrency() -> None:
    async def exercise() -> None:
        from etlantic.runtime.execute import arun_pipeline

        active = 0
        peak = 0
        runtime = PipelineRuntime()
        runtime.memory.seed("cross-rows", [{"id": 1}])

        async def middleware(context: Any, call_next: Any) -> Any:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await anyio.sleep(0.01)
                return await call_next()
            finally:
                active -= 1

        runtime.step_middleware.add(middleware)
        report = await arun_pipeline(
            Fanout,
            profile=adaptive_profile(concurrency=1),
            runtime=runtime,
            request=RunRequest(metadata={"concurrency": 3}),
        )
        assert report.status.value == "succeeded", report.diagnostics
        assert peak == 1, "Captured Profile concurrency takes precedence over request"

    anyio.run(exercise)


def test_final_007_cancel_and_cleanup_finish_under_run_timeout() -> None:
    async def exercise() -> None:
        request = RunRequest(timeout=TimeoutPolicy(run_seconds=0.05))
        plan = plan_pipeline(Sample, profile=adaptive_profile(), request=request)
        support = support_row_for(plan)
        assert support is not None
        runtime = PipelineRuntime()
        calls: list[str] = []

        class Executor:
            info = PhysicalExecutorInfo(
                "etlantic.physical.local/1",
                "etlantic",
                "0.52.1",
                capability_fingerprint=plan.inventory.targets[0].capability_fingerprint,
                evidence_refs=support.evidence_refs,
            )

            def analyze(self, plan: Any, unit: Any) -> PhysicalUnitSupport:
                return PhysicalUnitSupport(True, self.info.identity)

            async def execute(self, context: Any) -> PhysicalUnitResult:
                calls.append("started")
                await anyio.sleep_forever()

            async def cancel(self, context: Any) -> None:
                await anyio.sleep(0)
                calls.append("cancelled")

            async def cleanup(self, context: Any, result: Any) -> tuple[Any, ...]:
                await anyio.sleep(0)
                calls.append("cleaned")
                return ()

        runtime.physical_executors = {"local": Executor()}  # type: ignore[attr-defined]
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert "started" in calls
        assert "cancelled" in calls and "cleaned" in calls, (calls, report.diagnostics)

    anyio.run(exercise)


def test_final_005_timeout_after_commit_retains_unknown_obligation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exercise() -> None:
        request = RunRequest(timeout=TimeoutPolicy(run_seconds=0.1))
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        original = runtime.memory.write
        writes: list[str] = []

        async def commit_then_wait(**kwargs: Any) -> Any:
            writes.append(kwargs["binding"])
            await original(**kwargs)
            await anyio.sleep_forever()

        monkeypatch.setattr(runtime.memory, "write", commit_then_wait)
        plan = plan_pipeline(Sample, profile=adaptive_profile(), request=request)
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert writes == ["out"] and runtime.memory.get("out")
        assert any(d.code == "PMADP524" for d in report.diagnostics), report.diagnostics
        assert report.metadata.get("etlantic.unknown_publications"), report.metadata

    anyio.run(exercise)


def test_final_005_explicit_writer_timeout_preserves_legacy_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exercise() -> None:
        request = RunRequest()
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])

        async def fail_write(**kwargs: Any) -> Any:
            raise TimeoutError("synthetic explicit writer timeout")

        monkeypatch.setattr(runtime.memory, "write", fail_write)
        plan = plan_pipeline(Sample, profile=Profile(name="explicit"))
        assert plan.schema == "etlantic.plan/1"
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        assert not any(d.code.startswith("PMADP") for d in report.diagnostics), (
            report.diagnostics
        )
        assert (
            next(step for step in report.steps if step.step_name == "out").status.value
            == "failed"
        )

    anyio.run(exercise)


def test_final_008_nonwriting_gate_rejects_fabricated_skipped_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = Path(__file__).resolve().parents[2] / "scripts/check_adaptive_0_53.py"
    spec = importlib.util.spec_from_file_location("sol_053_campaign_invariant", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    revision = "sha256:" + "a" * 64
    command = ["uv", "run", "pytest", "-q", *module.TESTS]
    evidence = tmp_path / "qualification.json"
    evidence.write_text(
        json.dumps(
            {
                "schema": module.EVIDENCE_SCHEMA,
                "phase": "0.53",
                "source_revision": revision,
                "command": command,
                "returncode": 0,
                "stdout_sha256": "fabricated",
                "stderr_sha256": "fabricated",
            }
        )
    )
    before = evidence.read_bytes()
    monkeypatch.setattr(module, "OUT", tmp_path)
    monkeypatch.setattr(module, "source_revision", lambda: revision)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, "11 skipped", ""
        ),
    )
    monkeypatch.setattr(sys, "argv", [str(path)])
    assert module.main() != 0, "Skipped/fabricated proof cannot qualify required rows"
    assert evidence.read_bytes() == before


def test_final_009_unknown_receipt_cannot_serialize_native_row_payload() -> None:
    marker = "SOL_SYNTHETIC_RECEIPT_ROW_MARKER"

    class NativeReceipt:
        def to_dict(self) -> dict[str, Any]:
            return {"rows": [{"id": 1, "name": marker}]}

    try:
        wire = PhysicalUnitFailure(
            "Publication outcome unknown",
            unit_id="unit",
            target_identity="target",
            unknown_receipt=NativeReceipt(),
        ).to_dict()
    except (ValueError, TypeError):
        return
    assert marker not in json.dumps(wire), wire


@pytest.mark.parametrize(
    ("expires_at", "selection"),
    [
        (None, "checkpoint"),
        (0.0, "producer"),
        (float("nan"), None),
        (float("inf"), None),
    ],
    ids=["unexpired", "expired", "nan-retention", "infinite-retention"],
)
def test_final_003_checkpoint_retention_must_be_valid_before_reuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expires_at: float | None,
    selection: str | None,
) -> None:
    """Malformed retention cannot grant a checkpoint hit or sink publication."""
    from etlantic.plan.adaptive_model import AdaptivePipelinePlan
    from etlantic.runtime.physical_operations import OPERATION_SCHEMA

    graph = Sample.build_graph()
    graph = replace(
        graph,
        nodes=tuple(
            replace(
                node,
                metadata={
                    **dict(node.metadata),
                    "etlantic.reuse_artifact": {
                        "schema": OPERATION_SCHEMA,
                        "kind": "reuse",
                        "checkpoint": "raw",
                    },
                },
            )
            if node.name == "raw"
            else node
            for node in graph.nodes
        ),
    )
    monkeypatch.setattr(Sample, "build_graph", classmethod(lambda cls: graph))

    async def exercise() -> None:
        request = RunRequest()
        plan = plan_pipeline(Sample, profile=adaptive_profile(), request=request)
        assert isinstance(plan, AdaptivePipelinePlan)
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        records = [{"id": 99}]
        payload = json.dumps(records, sort_keys=True, separators=(",", ":"))
        workspace = tmp_path.resolve()
        checkpoint = {
            "metadata": {
                "schema": "etlantic.checkpoint/1",
                "digest": "sha256:" + hashlib.sha256(payload.encode()).hexdigest(),
                "producer_fingerprint": plan.fingerprint,
                "contract_id": plan.logical_graph.node_map()["raw"]
                .outputs[0]
                .contract_id,
                "security_domain": plan.security_domain,
                "created_at": 0.0,
                "expires_at": expires_at,
            },
            "records": records,
        }
        # Python's decoder accepts these nonfinite JSON constants; the runtime
        # must reject them as malformed checkpoint state rather than a hit.
        (workspace / "checkpoint-raw.json").write_text(
            json.dumps(checkpoint), encoding="utf-8"
        )
        report = await LocalScheduler().execute(
            plan, request=request, runtime=runtime, workspace=workspace
        )
        reuse = next(
            trace
            for trace in report.metadata["etlantic.physical_trace"]
            if trace["kind"] == "reuse"
        )
        if selection is None:
            assert reuse["status"] == "failed", reuse
            assert runtime.memory.get("out") == []
            assert report.status.value != "succeeded"
        else:
            assert reuse["selection"] == selection
            assert report.status.value == "succeeded", report.diagnostics
            assert [row.id for row in runtime.memory.get("out")] == [
                99 if selection == "checkpoint" else 1
            ]

    anyio.run(exercise)


@pytest.mark.polars
@pytest.mark.pandas
def test_final_007_native_member_deadline_fences_late_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slow work in the admitted native compiler cannot turn timeout into success."""
    import etlantic_polars.compiler as compiler_module
    from etlantic.runtime.request import CancellationPolicy
    from tests.runtime.physical.test_qualification_0_53 import Chain, setup

    original = compiler_module.apply_action
    calls: list[str] = []

    def slow_native_action(*args: Any, **kwargs: Any) -> Any:
        calls.append("native_started")
        # Inject latency at the real synchronous native operation boundary,
        # retaining its compiler, dataframe result and admitted provider.
        time.sleep(0.4)
        return original(*args, **kwargs)

    monkeypatch.setattr(compiler_module, "apply_action", slow_native_action)

    async def exercise() -> None:
        request = RunRequest(
            timeout=TimeoutPolicy(step_seconds=0.1),
            cancellation=CancellationPolicy(abandon_after_seconds=0.1),
        )
        runtime, _, plan = setup(Chain, ("polars",), request)
        runtime.memory.seed("rows", [{"id": 1}])
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        first = next(step for step in report.steps if step.step_name == "first")
        assert calls, "The admitted native execution path must be exercised"
        assert first.status.value in {"timed_out", "abandoned"}, first
        assert first.attempts == 1
        assert runtime.memory.get("out") == []
        assert report.status.value != "succeeded"
        assert (
            next(
                step for step in report.steps if step.step_name == "second"
            ).status.value
            == "skipped"
        )

    anyio.run(exercise)


@pytest.mark.polars
@pytest.mark.pandas
def test_final_007_native_run_timeout_drains_or_records_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A terminal run cannot silently leave its native work in flight."""
    import etlantic_polars.compiler as compiler_module
    from etlantic.runtime.request import CancellationPolicy
    from tests.runtime.physical.test_qualification_0_53 import Chain, setup

    original = compiler_module.apply_action
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def blocked_native_action(*args: Any, **kwargs: Any) -> Any:
        started.set()
        try:
            release.wait(timeout=2.0)
            return original(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(compiler_module, "apply_action", blocked_native_action)

    async def exercise() -> None:
        request = RunRequest(
            timeout=TimeoutPolicy(run_seconds=0.3),
            cancellation=CancellationPolicy(abandon_after_seconds=0.1),
        )
        runtime, _, plan = setup(Chain, ("polars",), request)
        runtime.memory.seed("rows", [{"id": 1}])
        try:
            report = await LocalScheduler().execute(
                plan, request=request, runtime=runtime
            )
            assert started.is_set(), "The real native operation must be entered"
            assert report.status.value != "succeeded"
            assert runtime.memory.get("out") == []
            if not finished.is_set():
                obligations = report.metadata.get("etlantic.cleanup_obligations")
                assert obligations, "In-flight native work requires an owner obligation"
                assert any(
                    item.get("code") == "PMADP523" and item.get("owner")
                    for item in obligations
                ), obligations
                assert any(d.code == "PMADP523" for d in report.diagnostics)
        finally:
            # Drain the injected operation even when the assertion fails, so
            # this review artifact does not leave a worker or patched call alive.
            release.set()
            if started.is_set():
                assert await anyio.to_thread.run_sync(finished.wait, 2.0)

    anyio.run(exercise)


@pytest.mark.polars
@pytest.mark.pandas
def test_final_007_explicit_async_compiler_retains_host_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit compiler may await an asynchronous resource from its host."""
    import etlantic_polars.compiler as compiler_module
    from etlantic.runtime.execute import arun_pipeline
    from tests.runtime.physical.test_qualification_0_53 import Chain

    original = compiler_module.PolarsTransformCompiler.execute

    async def exercise() -> None:
        loop = asyncio.get_running_loop()
        ready = loop.create_future()

        async def compiler_execute(self: Any, compiled: Any, **kwargs: Any) -> Any:
            if not ready.done():
                # Model a compiler's pre-existing asynchronous session/resource.
                # It is completed by the host while execute awaits it; the
                # original compiler and real dataframe result remain intact.
                loop.call_soon_threadsafe(loop.call_later, 0.1, ready.set_result, None)
            await ready
            return await original(self, compiled, **kwargs)

        monkeypatch.setattr(
            compiler_module.PolarsTransformCompiler, "execute", compiler_execute
        )
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        report = await arun_pipeline(
            Chain,
            profile=Profile(
                name="explicit-async-compiler",
                dataframe_engine="polars",
                portable_transform_policy="require",
            ),
            runtime=runtime,
        )
        await anyio.sleep(0.15)
        assert report.status.value == "succeeded", report.diagnostics
        assert [row.id for row in runtime.memory.get("out")] == [1]

    anyio.run(exercise)


@pytest.mark.polars
@pytest.mark.pandas
@pytest.mark.parametrize(
    ("unit_status", "failure_stage"),
    [
        pytest.param("failed", "transform", id="terminal-outcome"),
        pytest.param(
            "failed",
            'rows=[{"id":"SOL_PRIVATE_ROW_MARKER"}]',
            id="final-009-private-stage",
        ),
        pytest.param(
            "succeeded",
            'rows=[{"id":"SOL_PRIVATE_ROW_MARKER"}]',
            id="final-009-inconsistent-unit-private-stage",
        ),
    ],
)
def test_sol_011_failed_executor_branch_has_terminal_logical_report(
    unit_status: str,
    failure_stage: str,
) -> None:
    """Later independent success must not erase an executor's failed outcome."""
    from etlantic.connectors.models import CommitReceipt
    from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
    from etlantic.runtime.physical_protocol import (
        PhysicalArtifactHandle,
        PhysicalLogicalOutcome,
    )
    from tests.runtime.physical.test_qualification_0_53 import Fanout, Row, setup

    async def exercise() -> None:
        request = RunRequest(metadata={"concurrency": 2})
        runtime, _, plan = setup(Fanout, ("local",), request)
        support = support_row_for(plan)
        assert support is not None
        runtime.memory.seed("rows", [{"id": 1}])
        started: list[str] = []
        cleaned: list[str] = []
        publications: list[str] = []

        class Executor:
            info = PhysicalExecutorInfo(
                "etlantic.physical.local/1",
                "etlantic",
                "0.52.1",
                capability_fingerprint=plan.inventory.targets[0].capability_fingerprint,
                evidence_refs=support.evidence_refs,
            )

            def analyze(self, plan: Any, unit: Any) -> PhysicalUnitSupport:
                return PhysicalUnitSupport(True, self.info.identity)

            async def execute(self, context: Any) -> PhysicalUnitResult:
                unit = context.unit
                started.append(unit.identity)
                if unit.kind.value == "publication":
                    name = unit.metadata["etlantic.logical_node"]
                    assert name == "right_out"
                    await runtime.memory.write(
                        binding="right-out",
                        location=None,
                        data=[{"id": 1}],
                        contract_type=Row,
                        context={},
                    )
                    publications.append(name)
                    return PhysicalUnitResult(
                        unit.identity,
                        unit.target_identity,
                        "succeeded",
                        commit_receipt=CommitReceipt(
                            "committed", publication_id="pub:sol-011-independent"
                        ),
                    )
                name = unit.logical_nodes[0]
                if name == "left":
                    return PhysicalUnitResult(
                        unit.identity,
                        unit.target_identity,
                        unit_status,
                        logical_outcomes=(
                            PhysicalLogicalOutcome(
                                name,
                                "failed",
                                attempts=1,
                                failure_stage=failure_stage,
                                code="PMADP520",
                            ),
                        ),
                    )
                node = plan.logical_graph.node_map()[name]
                return PhysicalUnitResult(
                    unit.identity,
                    unit.target_identity,
                    "succeeded",
                    outputs=tuple(
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
                    ),
                    logical_outcomes=(PhysicalLogicalOutcome(name, "succeeded"),),
                )

            async def cancel(self, context: Any) -> None:
                pass

            async def cleanup(self, context: Any, result: Any) -> tuple[Any, ...]:
                cleaned.append(context.unit.identity)
                return ()

        runtime.physical_executors = {"local": Executor()}  # type: ignore[attr-defined]
        report = await LocalScheduler().execute(plan, request=request, runtime=runtime)
        steps = {step.step_name: step for step in report.steps}
        assert set(steps) == set(plan.logical_graph.node_names())
        assert report.status.value == "partial"
        assert publications == ["right_out"]
        assert [row.id for row in runtime.memory.get("right-out")] == [1]
        assert runtime.memory.get("left-out") == []
        assert steps["right_out"].status.value == "succeeded"
        assert steps["left_out"].status.value == "skipped"
        assert sorted(cleaned) == sorted(started)
        assert steps["left"].status.value == "failed", (
            "A failed executor branch must have a terminal logical report even "
            "when a later independent branch succeeds"
        )
        assert steps["left"].attempts == 1
        assert report.summary.failed == 1
        assert report.summary.succeeded == 4
        assert report.summary.skipped == 1
        expected_codes = (
            {"PMADP400", "PMADP520"} if unit_status == "succeeded" else {"PMADP520"}
        )
        assert any(d.code in expected_codes for d in report.diagnostics)
        if failure_stage == "transform":
            assert steps["left"].failure_stage == "transform"
        assert "SOL_PRIVATE_ROW_MARKER" not in json.dumps(report.to_dict()), (
            "Returned executor failure stages must remain metadata-only in "
            "the final logical report"
        )

    anyio.run(exercise)
