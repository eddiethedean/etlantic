"""WP6: write-mode retry safety and adversarial I/O matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    RunRequest,
    RunStatus,
    Transformation,
)
from etlantic.reliability import RetrySafetyDeclaration
from etlantic.runtime.request import RetryPolicy
from etlantic.storage import JsonStorage


class Row(Data):
    id: int
    name: str = "x"


class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Identity.implementation("local")
def identity_local(rows: list[Row]) -> list[Row]:
    return list(rows)


class LocalPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")


def test_local_memory_safe_retry_succeeds() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    report = LocalPipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(
            retry=RetryPolicy(max_attempts=2, backoff_seconds=0),
            metadata={
                "retry_safety": {
                    "step": RetrySafetyDeclaration(subject_id="step", safe=True)
                }
            },
        ),
    )
    assert report.status is RunStatus.SUCCEEDED


def test_unsafe_retry_blocked_with_pmexec501() -> None:
    class Boom(Transformation):
        rows: Input[Row]
        result: Output[Row]

    calls = {"n": 0}

    @Boom.implementation("local")
    def boom_local(rows: list[Row]) -> list[Row]:
        calls["n"] += 1
        raise RuntimeError("boom")

    class BoomPipeline(Pipeline):
        raw: Extract[Row] = Extract(asset="rows")
        step = Boom.step(rows=raw)
        out: Load[Row] = Load(input=step.result, asset="out")

    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1)])
    report = BoomPipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(
            retry=RetryPolicy(max_attempts=3, backoff_seconds=0),
            metadata={
                "retry_safety": {
                    "step": RetrySafetyDeclaration(subject_id="step", safe=False)
                }
            },
        ),
    )
    assert report.status in {RunStatus.FAILED, RunStatus.PARTIAL}
    assert calls["n"] == 1
    assert any(d.code == "PMEXEC501" for d in report.diagnostics)


def test_json_storage_round_trip(tmp_path: Path) -> None:
    """File-backed JSON writes remain valid under SafeIoPolicy (local path)."""
    import anyio

    json_path = tmp_path / "out.json"
    store = JsonStorage()

    async def _run() -> None:
        await store.write(
            binding="out",
            location=str(json_path),
            data=[Row(id=1, name="a")],
            contract_type=Row,
            context={},
        )

    anyio.run(_run)
    assert json_path.exists()
    assert '"id": 1' in json_path.read_text(encoding="utf-8")


def test_corrupt_report_json_skipped_on_load(tmp_path: Path) -> None:
    from etlantic.reports.file_store import FileReportStore

    root = tmp_path / "reports"
    root.mkdir()
    (root / "bad.json").write_text("{not-json", encoding="utf-8")
    store = FileReportStore(root)
    assert store.list() == []


def test_incomplete_tmp_report_skipped_on_load(tmp_path: Path) -> None:
    from etlantic.reports.file_store import FileReportStore

    root = tmp_path / "reports"
    root.mkdir()
    (root / "orphan.json.tmp").write_text('{"incomplete": true', encoding="utf-8")
    store = FileReportStore(root)
    assert store.list() == []
