"""Protected Sol regression contracts for phase 0.53 release blockers.

Keep original FINAL identifiers: these verify the same previously reported
root causes, rather than expanding the approved implementation boundary.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import anyio
import pytest

from etlantic import Extract, Load, Pipeline, __version__
from etlantic.exceptions import PipelineExecutionError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan import explain_plan, plan_from_json, plan_pipeline, plan_to_json
from etlantic.plan.adaptive_model import AdaptivePipelinePlan
from etlantic.registry import BindingDescriptor
from etlantic.runtime.adaptive_admission import admit_adaptive_plan
from etlantic.runtime.adaptive_support import support_row_for
from etlantic.runtime.physical_protocol import (
    PhysicalArtifactHandle,
    PhysicalExecutorInfo,
    PhysicalLogicalOutcome,
    PhysicalUnitFailure,
    PhysicalUnitResult,
    PhysicalUnitSupport,
)
from etlantic.runtime.request import (
    RetryPolicy,
    RunRequest,
    RunSelection,
    TimeoutPolicy,
)
from etlantic.runtime.scheduler import LocalScheduler
from etlantic.storage.memory import MemoryStorage
from tests.plan.test_adaptive_planner_0_52 import Sample, adaptive_profile
from tests.runtime.test_adaptive_execution_0_53 import (
    CrossPipeline,
    CrossRow,
    CrossStep,
)
from tests.runtime.test_adaptive_execution_0_53 import (
    test_adaptive_physical_execution_routes_portable_polars_to_pandas as run_cross_fixture,
)

ROOT = Path(__file__).resolve().parents[2]


class Fanout(Pipeline):
    raw: Extract[CrossRow] = Extract(asset="cross-rows")
    shared = CrossStep.step(source=raw)
    left = CrossStep.step(source=shared.result)
    right = CrossStep.step(source=shared.result)
    left_out: Load[CrossRow] = Load(input=left.result, asset="left-out")
    right_out: Load[CrossRow] = Load(input=right.result, asset="right-out")


class TwoSteps(Pipeline):
    raw: Extract[CrossRow] = Extract(asset="cross-rows")
    first = CrossStep.step(source=raw)
    second = CrossStep.step(source=first.result)
    out: Load[CrossRow] = Load(input=second.result, asset="cross-out")


def test_final_001_live_storage_replacement_rejects_before_effects() -> None:
    async def exercise() -> None:
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        request = RunRequest()
        plan = plan_pipeline(Sample, profile=adaptive_profile(), request=request)
        effects: list[str] = []

        class UnqualifiedWriter(MemoryStorage):
            async def read(self, **kwargs: Any) -> Any:
                effects.append("read")
                return await runtime.memory.read(**kwargs)

            async def write(self, **kwargs: Any) -> Any:
                effects.append("write")
                return await runtime.memory.write(**kwargs)

        runtime.register_storage("memory", UnqualifiedWriter())
        rejected = False
        try:
            await LocalScheduler().execute(plan, request=request, runtime=runtime)
        except PipelineExecutionError as exc:
            rejected = exc.code == "PMADP501" and exc.stage == "admission"
        assert rejected and effects == [], (rejected, effects)

    anyio.run(exercise)


def test_final_001_all_unit_support_analysis_precedes_session() -> None:
    request = RunRequest()
    plan = plan_pipeline(Sample, profile=adaptive_profile(), request=request)
    assert isinstance(plan, AdaptivePipelinePlan)
    support = support_row_for(plan)
    assert support is not None
    runtime = PipelineRuntime()
    calls: list[str] = []

    class RejectingExecutor:
        info = PhysicalExecutorInfo(
            "etlantic.physical.local/1",
            "etlantic",
            __version__,
            capability_fingerprint=plan.inventory.targets[0].capability_fingerprint,
            evidence_refs=support.evidence_refs,
        )

        def analyze(self, plan: Any, unit: Any) -> PhysicalUnitSupport:
            calls.append(unit.identity)
            return PhysicalUnitSupport(False, self.info.identity)

    runtime.physical_executors = {"local": RejectingExecutor()}  # type: ignore[attr-defined]
    with pytest.raises(PipelineExecutionError):
        admit_adaptive_plan(plan, request=request, runtime=runtime)
    assert calls, "Every unit must be analyzed during whole-DAG admission"


def test_final_001_metadata_append_mode_rejects_before_session() -> None:
    async def exercise() -> None:
        from etlantic.runtime.execute import arun_pipeline

        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        runtime.memory.seed("out", [{"id": 99}])
        runtime.registry.register_binding(
            BindingDescriptor("out", "memory", metadata={"write_mode": "append"})
        )
        effects: list[str] = []

        @asynccontextmanager
        async def lifespan(_: Any):
            effects.append("session")
            yield

        runtime.lifespan = lifespan
        rejected = False
        try:
            await arun_pipeline(
                Sample,
                profile=adaptive_profile(),
                runtime=runtime,
                request=RunRequest(),
            )
        except PipelineExecutionError as exc:
            rejected = exc.code in {"PMADP501", "PMADP522"}
        assert rejected and effects == [], (
            rejected,
            effects,
            runtime.memory.get("out"),
        )

    anyio.run(exercise)


def test_final_002_required_exact_fanout_has_qualified_row() -> None:
    plan = plan_pipeline(Fanout, profile=adaptive_profile(), request=RunRequest())
    assert isinstance(plan, AdaptivePipelinePlan)
    row = support_row_for(plan)
    assert row is not None and row.pattern == "fanout/1"


def test_final_003_real_handoff_occurs_inside_transfer_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    etlantic_pandas = pytest.importorskip("etlantic_pandas")

    plugin_type = type(etlantic_pandas.create_plugin())
    original = plugin_type.materialize_input
    original_emit = __import__(
        "etlantic.runtime.events", fromlist=["EventBus"]
    ).EventBus.emit
    active_kind: dict[str, str] = {}
    observations: list[str] = []

    def emit(bus: Any, event: Any) -> None:
        if event.kind == "physical_unit_started":
            active_kind[event.run_id] = "physical"
        elif event.kind == "step_started":
            active_kind[event.run_id] = "compute"
        original_emit(bus, event)

    def materialize(plugin: Any, value: Any, **kwargs: Any) -> Any:
        context = kwargs["context"]
        if context.interchange is not None:
            observations.append(active_kind.get(context.run_id, "none"))
        return original(plugin, value, **kwargs)

    monkeypatch.setattr("etlantic.runtime.events.EventBus.emit", emit)
    monkeypatch.setattr(plugin_type, "materialize_input", materialize)
    run_cross_fixture()
    assert observations == ["physical"], observations


def test_final_004_request_only_selection_controls_planning_scope() -> None:
    request = RunRequest(selection=RunSelection.until("raw"))
    plan = plan_pipeline(Sample, profile=adaptive_profile(), request=request)
    assert plan.logical_graph.node_names() == ("raw",)


def test_final_004_stored_portable_runs_without_live_pipeline_class() -> None:
    async def exercise() -> None:
        request = RunRequest()
        planned = plan_pipeline(
            CrossPipeline, profile=adaptive_profile(), request=request
        )
        restored = plan_from_json(plan_to_json(planned))
        runtime = PipelineRuntime()
        runtime.memory.seed("cross-rows", [{"id": 1}])
        report = await LocalScheduler().execute(
            restored, request=request, runtime=runtime, pipeline_cls=None
        )
        assert report.status.value == "succeeded", report.diagnostics
        assert [row.id for row in runtime.memory.get("cross-out")] == [1]

    anyio.run(exercise)


def test_final_004_none_request_uses_default_executable_lowering() -> None:
    plan = plan_pipeline(Sample, profile=adaptive_profile())
    assert explain_plan(plan)["planning_only"] is False
    assert plan.metadata["etlantic.runtime"]["request"] is not None


@pytest.mark.parametrize(
    "invalid_policy",
    [
        RunRequest(retry=RetryPolicy(max_attempts=True)),
        RunRequest(retry=RetryPolicy(max_attempts=cast(Any, 1.5))),
        RunRequest(timeout=TimeoutPolicy(step_seconds=True)),
    ],
)
def test_final_004_invalid_numeric_policy_rejects(invalid_policy: RunRequest) -> None:
    with pytest.raises(PipelineExecutionError) as error:
        admit_adaptive_plan(
            plan_pipeline(Sample, profile=adaptive_profile(), request=invalid_policy),
            request=invalid_policy,
        )
    assert error.value.code == "PMADP522"


def test_final_005_definite_publication_failure_is_logically_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exercise() -> None:
        request = RunRequest()
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])

        async def fail_write(**kwargs: Any) -> Any:
            raise OSError("synthetic publication failure")

        monkeypatch.setattr(runtime.memory, "write", fail_write)
        report = await LocalScheduler().execute(
            plan_pipeline(Sample, profile=adaptive_profile(), request=request),
            request=request,
            runtime=runtime,
        )
        statuses = {s.step_name: s.status.value for s in report.steps}
        assert statuses == {"raw": "succeeded", "out": "failed"}
        assert report.summary.succeeded == 1 and report.summary.failed == 1

    anyio.run(exercise)


def test_final_005_ack_loss_retains_unknown_publication_obligation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exercise() -> None:
        request = RunRequest()
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [{"id": 1}])
        original = runtime.memory.write
        writes: list[str] = []

        async def lose_ack(**kwargs: Any) -> Any:
            writes.append(kwargs["binding"])
            await original(**kwargs)
            raise TimeoutError("synthetic lost publication acknowledgement")

        monkeypatch.setattr(runtime.memory, "write", lose_ack)
        report = await LocalScheduler().execute(
            plan_pipeline(Sample, profile=adaptive_profile(), request=request),
            request=request,
            runtime=runtime,
        )
        assert writes == ["out"]
        assert runtime.memory.get("out"), (
            "The effect occurred before acknowledgement loss"
        )
        assert any(d.code == "PMADP524" for d in report.diagnostics), report.diagnostics
        assert any(
            s.step_name == "out" and s.status.value == "failed" for s in report.steps
        )
        assert "unknown" in json.dumps(report.to_dict()).lower(), (
            "Retain an explicit reconciliation obligation"
        )

    anyio.run(exercise)


def test_final_006_concurrent_default_runs_isolate_logical_artifacts() -> None:
    async def exercise() -> None:
        from etlantic.runtime.execute import arun_pipeline

        runtime = PipelineRuntime()
        runtime.memory.seed("a", [{"id": 1}])
        runtime.memory.seed("b", [{"id": 2}])
        source_barrier = anyio.Event()
        arrivals = 0

        async def barrier(context: Any, call_next: Any) -> Any:
            nonlocal arrivals
            result = await call_next()
            if context.step_name == "raw":
                arrivals += 1
                if arrivals == 2:
                    source_barrier.set()
                await source_barrier.wait()
            return result

        runtime.step_middleware.add(barrier)

        async def run(asset: str) -> None:
            report = await arun_pipeline(
                Sample,
                profile=adaptive_profile(),
                runtime=runtime,
                request=RunRequest(
                    asset_overrides={"raw": asset, "out": asset + "-out"}
                ),
            )
            assert report.status.value == "succeeded", report.diagnostics

        with anyio.fail_after(10):
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(run, "a")
                tasks.start_soon(run, "b")
        assert [row.id for row in runtime.memory.get("a-out")] == [1]
        assert [row.id for row in runtime.memory.get("b-out")] == [2]

    anyio.run(exercise)


def test_final_007_failed_dependency_blocks_transitive_downstream_start() -> None:
    async def exercise() -> None:
        from etlantic.runtime.execute import arun_pipeline

        runtime = PipelineRuntime()
        runtime.memory.seed("cross-rows", [{"id": 1}])
        started: list[str] = []

        async def middleware(context: Any, call_next: Any) -> Any:
            started.append(context.step_name)
            if context.step_name == "first":
                raise ValueError("synthetic middle failure")
            return await call_next()

        runtime.step_middleware.add(middleware)
        report = await arun_pipeline(
            TwoSteps,
            profile=adaptive_profile(),
            runtime=runtime,
            request=RunRequest(metadata={"concurrency": 1}),
        )
        assert started == ["raw", "first"], (started, report.steps)
        statuses = {step.step_name: step.status.value for step in report.steps}
        assert statuses == {
            "raw": "succeeded",
            "first": "failed",
            "second": "skipped",
            "out": "skipped",
        }

    anyio.run(exercise)


def test_final_008_nonwriting_gate_rejects_tampered_committed_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = ROOT / "scripts/check_adaptive_0_53.py"
    spec = importlib.util.spec_from_file_location("sol_adaptive_evidence", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    evidence = tmp_path / "qualification.json"
    evidence.write_text(
        '{"source_revision":"tampered","returncode":1}', encoding="utf-8"
    )
    before = evidence.read_bytes()
    monkeypatch.setattr(module, "OUT", tmp_path)
    monkeypatch.setattr(module, "source_revision", lambda: "sha256:" + "a" * 64)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, "11 passed", ""
        ),
    )
    monkeypatch.setattr(sys, "argv", [str(path)])
    assert module.main() != 0, (
        "A successful command must not authorize stale/tampered committed evidence"
    )
    assert evidence.read_bytes() == before


@pytest.mark.parametrize(
    "surface", ["metrics", "diagnostics", "failure", "artifact_ref"]
)
def test_final_009_protocol_never_serializes_rows_or_native_refs(surface: str) -> None:
    marker = "SOL_SYNTHETIC_ROW_MARKER"
    payload = {"rows": [{"id": 1, "name": marker}]}
    try:
        if surface == "metrics":
            wire = PhysicalLogicalOutcome("step", "failed", metrics=payload).to_dict()
        elif surface == "diagnostics":
            wire = PhysicalUnitResult(
                "unit", "target", "failed", diagnostics=(payload,)
            ).to_dict()
        elif surface == "failure":
            wire = PhysicalUnitFailure(
                f"Rejected row {payload}", unit_id="unit", target_identity="target"
            ).to_dict()
        else:

            class NativeRef:
                def to_dict(self) -> dict[str, Any]:
                    return payload

            wire = PhysicalArtifactHandle(NativeRef(), object()).to_dict()
    except (ValueError, TypeError):
        return  # Failing closed is also permitted for unsafe provider payloads.
    assert marker not in json.dumps(wire), wire
