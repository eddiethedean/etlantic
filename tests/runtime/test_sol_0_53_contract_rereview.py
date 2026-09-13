"""Independent checks of unresolved phase 0.53 contract invariants.

These retain the original FINAL IDs and supplement the focused reproducers.
They intentionally fail only for in-scope release blockers.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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
