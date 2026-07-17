"""Regression tests for 0.4.0 runtime bugfixes."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pytest

from etlantic import (
    Data,
    Inject,
    Input,
    Output,
    Pipeline,
    PipelineRuntime,
    RunRequest,
    RunSelection,
    RunStatus,
    SchemaDriftPolicy,
    SecretRef,
    Sink,
    Source,
    Transformation,
)
from etlantic.lifecycle.callbacks import FailureAction
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime.request import MaterializationPolicy
from etlantic.schema_drift import (
    SchemaObservation,
    normalize_schema_from_fields,
    normalize_schema_from_model,
)
from etlantic.schema_policy import DriftAction, evaluate_drift


class Row(Data):
    id: int
    name: str


class Normalize(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Normalize.implementation("local")
def normalize_local(rows: list[Row]) -> list[Row]:
    return [Row(id=r.id, name=r.name.strip().title()) for r in rows]


class NoImpl(Transformation):
    rows: Input[Row]
    result: Output[Row]


class SimplePipeline(Pipeline):
    raw: Source[Row] = Source(binding="rows")
    normalized = Normalize.step(rows=raw)
    out: Sink[Row] = Sink(input=normalized.result, binding="out")


class MissingImplPipeline(Pipeline):
    raw: Source[Row] = Source(binding="rows")
    step = NoImpl.step(rows=raw)
    out: Sink[Row] = Sink(input=step.result, binding="out")


def test_missing_implementation_fails_closed() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = MissingImplPipeline.run(profile="development", runtime=runtime)
    assert report.status in {RunStatus.FAILED, RunStatus.PARTIAL}
    assert any("No implementation" in (d.message or "") for d in report.diagnostics)


def test_durable_policy_controls_workspace_files(tmp_path: Path) -> None:
    none_dir = tmp_path / "none"
    durable_dir = tmp_path / "durable"

    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="ada")])
    report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        workspace=none_dir,
        request=RunRequest(materialization=MaterializationPolicy.NONE),
    )
    assert report.status is RunStatus.SUCCEEDED
    assert list(none_dir.glob("*.json")) == []

    runtime2 = PipelineRuntime()
    runtime2.memory.seed("rows", [Row(id=1, name="ada")])
    report2 = SimplePipeline.run(
        profile="development",
        runtime=runtime2,
        workspace=durable_dir,
        request=RunRequest(materialization=MaterializationPolicy.DURABLE),
    )
    assert report2.status is RunStatus.SUCCEEDED
    assert list(durable_dir.glob("*.json"))


def test_secret_reaches_storage_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPE_TOKEN", "top-secret")
    seen: dict[str, object] = {}

    class CapturingMemory:
        name = "memory"

        async def read(self, *, binding, location, contract_type, context):
            seen["secret"] = context.get("secret")
            return [Row(id=1, name="x")]

        async def write(self, *, binding, location, data, contract_type, context):
            return {"records": len(data) if isinstance(data, list) else 1}

    runtime = PipelineRuntime()
    runtime.storage["memory"] = CapturingMemory()  # type: ignore[assignment]
    context = PlanningContext.create(profile="development")
    context.registry.register_binding(
        BindingDescriptor(
            binding="rows",
            provider="memory",
            secret_ref=SecretRef(provider="env", name="PIPE_TOKEN", key="value"),
        )
    )
    report = SimplePipeline.run(profile="development", runtime=runtime, context=context)
    assert report.status is RunStatus.SUCCEEDED
    secret = seen["secret"]
    assert secret is not None
    assert secret.get_secret_value() == "top-secret"  # type: ignore[union-attr]
    assert "top-secret" not in report.to_json()


def test_missing_secret_fails_closed() -> None:
    runtime = PipelineRuntime()
    context = PlanningContext.create(profile="development")
    context.registry.register_binding(
        BindingDescriptor(
            binding="rows",
            provider="memory",
            secret_ref=SecretRef(
                provider="env", name="MISSING_SECRET_XYZ", key="value"
            ),
        )
    )
    report = SimplePipeline.run(profile="development", runtime=runtime, context=context)
    assert report.status in {RunStatus.FAILED, RunStatus.PARTIAL}
    assert any("Secret" in (d.message or "") for d in report.diagnostics)


def test_run_selection_until_excludes_sink() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(selection=RunSelection.until("normalized")),
    )
    assert report.status is RunStatus.SUCCEEDED
    names = {s.step_name for s in report.steps}
    assert "out" not in names
    assert "normalized" in names


def test_lineage_on_report() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = SimplePipeline.run(profile="development", runtime=runtime)
    assert report.lineage
    assert any("normalized" in edge["to"] for edge in report.lineage)


def test_resource_injection_and_cleanup() -> None:
    cleaned: list[str] = []

    class Counter(Transformation):
        rows: Input[Row]
        result: Output[Row]

    @Counter.implementation("local")
    def counter_local(
        rows: list[Row],
        db: Annotated[str, Inject("db")],
    ) -> list[Row]:
        assert db == "ok"
        return rows

    class InjectPipeline(Pipeline):
        raw: Source[Row] = Source(binding="rows")
        counted = Counter.step(rows=raw)
        out: Sink[Row] = Sink(input=counted.result, binding="out")

    async def provide_db(_ctx):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def cm():
            yield "ok"
            cleaned.append("done")

        return cm()

    runtime = PipelineRuntime()
    runtime.override_resource("db", provide_db)
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = InjectPipeline.run(profile="development", runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED
    assert cleaned == ["done"]


def test_continue_failure_action_skips() -> None:
    class Boom(Transformation):
        rows: Input[Row]
        result: Output[Row]

    @Boom.implementation("local")
    def boom_local(rows: list[Row]) -> list[Row]:
        raise RuntimeError("boom")

    class BoomPipeline(Pipeline):
        raw: Source[Row] = Source(binding="rows")
        step = Boom.step(rows=raw)
        out: Sink[Row] = Sink(input=step.result, binding="out")

    runtime = PipelineRuntime()
    runtime.callbacks.on_step_failed(lambda _ctx: FailureAction.CONTINUE)
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = BoomPipeline.run(profile="development", runtime=runtime)
    step = next(s for s in report.steps if s.step_name == "step")
    assert step.status.value == "skipped"


def test_schema_drift_policy_blocks_breaking_changes() -> None:
    declared = normalize_schema_from_model(Row)
    previous = SchemaObservation(subject_id="raw", schema=declared)
    current = SchemaObservation(
        subject_id="raw",
        schema=normalize_schema_from_fields(
            [
                {"name": "id", "logical_type": "integer"},
                {"name": "name", "logical_type": "string"},
                {"name": "extra", "logical_type": "string"},
            ],
            identity="observed:raw",
        ),
    )
    decision = evaluate_drift(
        subject_id="raw",
        declared=declared,
        previous=previous,
        current=current,
        policy=SchemaDriftPolicy(default_action=DriftAction.BLOCK),
        profile_name="development",
    )
    assert decision.action is DriftAction.BLOCK
    assert decision.change_count >= 1


def test_middleware_order_observable() -> None:
    order: list[str] = []

    async def mw_a(ctx, call_next):
        order.append("a-before")
        result = await call_next()
        order.append("a-after")
        return result

    async def mw_b(ctx, call_next):
        order.append("b-before")
        result = await call_next()
        order.append("b-after")
        return result

    runtime = PipelineRuntime()
    runtime.add_run_middleware(mw_a, name="a")
    runtime.add_run_middleware(mw_b, name="b")
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    SimplePipeline.run(profile="development", runtime=runtime)
    assert order == ["a-before", "b-before", "b-after", "a-after"]


def test_redact_message_in_report() -> None:
    from etlantic.runtime.logging import redact_message, redact_value

    assert "password=***" in redact_message("failed password=hunter2 for user")
    assert "hunter2" not in redact_message("token=hunter2")
    bearer = redact_message("Authorization: Bearer abc123token")
    assert "abc123token" not in bearer
    assert "Bearer ***" in bearer
    json_msg = redact_message('{"password": "hunter2", "user": "ada"}')
    assert "hunter2" not in json_msg
    assert '"password": "***"' in json_msg
    mongo = redact_message("mongodb://user:pass@host/db")
    assert "pass@" not in mongo
    assert "user:***@" in mongo
    redis = redact_message("redis://:s3cret@localhost:6379/0")
    assert "s3cret" not in redis
    https = redact_message("https://user:basicpass@api.example/v1")
    assert "basicpass" not in https
    assert "user:***@" in https
    assert redact_value({"error": "password=hunter2", "ok": 1}) == {
        "error": "password=***",
        "ok": 1,
    }
    assert redact_value({"passwd": "x", "pwd": "y", "aws_secret_access_key": "z"}) == {
        "passwd": "***",
        "pwd": "***",
        "aws_secret_access_key": "***",
    }
