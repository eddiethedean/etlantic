"""Local runtime acceptance tests for Pipelantic 0.4."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipelantic import (
    Data,
    Input,
    Output,
    Pipeline,
    PipelineRuntime,
    RunIntent,
    RunRequest,
    RunSelection,
    RunStatus,
    SecretRef,
    SecretValue,
    Sink,
    Source,
    Transformation,
)
from pipelantic.registry import BindingDescriptor, PlanningContext
from pipelantic.secrets.env import EnvSecretProvider
from pipelantic.secrets.value import SecretSerializationError


class Row(Data):
    id: int
    name: str


class Normalize(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Normalize.implementation("local")
def normalize_local(rows: list[Row]) -> list[Row]:
    return [Row(id=r.id, name=r.name.strip().title()) for r in rows]


class Double(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Double.implementation("local")
def double_local(rows: list[Row]) -> list[Row]:
    return [Row(id=r.id * 2, name=r.name) for r in rows]


class Audit(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Audit.implementation("local")
def audit_local(rows: list[Row]) -> list[Row]:
    return list(rows)


class SimplePipeline(Pipeline):
    raw: Source[Row] = Source(binding="rows")
    normalized = Normalize.step(rows=raw)
    out: Sink[Row] = Sink(input=normalized.result, binding="out")


class ParallelPipeline(Pipeline):
    raw: Source[Row] = Source(binding="rows")
    normalized = Normalize.step(rows=raw)
    audited = Audit.step(rows=raw)
    doubled = Double.step(rows=normalized.result)
    out: Sink[Row] = Sink(input=doubled.result, binding="out")


def test_local_memory_pipeline_runs() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name=" alice "), Row(id=2, name="bob")])
    report = SimplePipeline.run(profile="development", runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED
    assert report.summary.succeeded >= 3
    out = runtime.memory.get("out")
    assert len(out) == 2
    assert out[0].name == "Alice"
    assert "secret" not in report.to_json().lower() or "SecretRef" in report.to_json()
    text = report.to_text()
    assert "succeeded" in text
    html = report.to_html()
    assert "<html>" in html


def test_json_csv_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "in.json"
    dst = tmp_path / "out.csv"
    src.write_text(
        json.dumps([{"id": 1, "name": "ada"}, {"id": 2, "name": "grace"}]),
        encoding="utf-8",
    )

    class FilePipeline(Pipeline):
        raw: Source[Row] = Source(binding="file_in")
        normalized = Normalize.step(rows=raw)
        out: Sink[Row] = Sink(input=normalized.result, binding="file_out")

    context = PlanningContext.create(profile="development")
    context.registry.register_binding(
        BindingDescriptor(
            binding="file_in", provider="json", location=str(src), kind="source"
        )
    )
    context.registry.register_binding(
        BindingDescriptor(
            binding="file_out", provider="csv", location=str(dst), kind="sink"
        )
    )
    runtime = PipelineRuntime()
    report = FilePipeline.run(profile="development", runtime=runtime, context=context)
    assert report.status is RunStatus.SUCCEEDED
    assert dst.is_file()
    lines = dst.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "id,name"
    assert "Ada" in lines[1]


def test_null_no_write() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="x")])
    report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(intent=RunIntent.VALIDATE),
    )
    assert report.status is RunStatus.SUCCEEDED
    assert runtime.memory.get("out") == []


def test_run_selection_until() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(selection=RunSelection.until("normalized")),
    )
    assert report.status is RunStatus.SUCCEEDED
    names = {s.step_name for s in report.steps}
    assert "normalized" in names
    assert "out" not in names or all(
        s.status.value != "succeeded" for s in report.steps if s.step_name == "out"
    )


def test_parallel_branches_succeed() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=3, name="z")])
    report = ParallelPipeline.run(profile="development", runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED
    out = runtime.memory.get("out")
    assert out[0].id == 6


def test_secret_value_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PASSWORD", "super-secret")
    provider = EnvSecretProvider()
    import anyio

    from pipelantic.secrets.provider import SecretResolutionContext

    async def _resolve() -> SecretValue:
        return await provider.resolve(
            SecretRef(provider="env", name="DB_PASSWORD", key="value"),
            SecretResolutionContext(run_id="r1", pipeline_id="p1"),
        )

    value = anyio.run(_resolve)
    assert value.get_secret_value() == "super-secret"
    assert "***" in repr(value)
    assert str(value) == "***"
    with pytest.raises(SecretSerializationError):
        value.to_dict()


def test_debug_session() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="sam")])
    with SimplePipeline.debug(profile="development", runtime=runtime) as session:
        report = session.run_until("normalized")
    assert report.status is RunStatus.SUCCEEDED


def test_schema_observations_on_report() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = SimplePipeline.run(profile="development", runtime=runtime)
    layers = {o.layer for o in report.schema_observations}
    assert "declared" in layers
    assert "current" in layers


def test_lifespan_cleanup() -> None:
    from contextlib import asynccontextmanager

    cleaned: list[str] = []

    @asynccontextmanager
    async def lifespan(runtime: PipelineRuntime):
        cleaned.append("start")
        yield
        cleaned.append("stop")

    runtime = PipelineRuntime(lifespan=lifespan)
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    SimplePipeline.run(profile="development", runtime=runtime)
    assert cleaned == ["start", "stop"]
