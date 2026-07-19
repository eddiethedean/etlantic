"""Local runtime acceptance tests for ETLantic 0.4."""

from __future__ import annotations

import json
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
    RunIntent,
    RunRequest,
    RunStatus,
    SecretRef,
    SecretValue,
    Transformation,
)
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.secrets.env import EnvSecretProvider
from etlantic.secrets.value import SecretSerializationError


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
    raw: Extract[Row] = Extract(asset="rows")
    normalized = Normalize.step(rows=raw)
    out: Load[Row] = Load(input=normalized.result, asset="out")


class ParallelPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    normalized = Normalize.step(rows=raw)
    audited = Audit.step(rows=raw)
    doubled = Double.step(rows=normalized.result)
    out: Load[Row] = Load(input=doubled.result, asset="out")


def test_local_memory_pipeline_runs() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name=" alice "), Row(id=2, name="bob")])
    report = SimplePipeline.run(profile="development", runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED
    assert report.summary.succeeded >= 3
    out = runtime.memory.get("out")
    assert len(out) == 2
    assert out[0].name == "Alice"
    blob = report.to_json().lower()
    assert "password=" not in blob
    assert "super-secret" not in blob
    assert "top-secret" not in blob
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
        raw: Extract[Row] = Extract(asset="file_in")
        normalized = Normalize.step(rows=raw)
        out: Load[Row] = Load(input=normalized.result, asset="file_out")

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

    from etlantic.secrets.provider import SecretResolutionContext

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
