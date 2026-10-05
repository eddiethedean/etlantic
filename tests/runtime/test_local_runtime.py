"""Local runtime acceptance tests for ETLantic 0.4."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

import anyio
import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    SecretRef,
    Transformation,
)
from etlantic.authoring import definition_from_pipeline
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    ExecutionEnvelope,
    MemoryDurableWorkStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.plan.model import PipelinePlan
from etlantic.profile import Profile, resolve_profile
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime.context import StepContext
from etlantic.runtime.execute import arun_pipeline, run_pipeline
from etlantic.runtime.managed_execution import ManagedExecutionAdapter, managed_run_id
from etlantic.runtime.request import RetryPolicy, RunIntent, RunRequest
from etlantic.runtime.state import RunStatus
from etlantic.secrets import SecretValue
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


def test_profile_concurrency_caps_local_parallel_pipeline() -> None:
    async def exercise() -> None:
        active = 0
        peak = 0
        runtime = PipelineRuntime()
        runtime.memory.seed("rows", [Row(id=1, name="alice")])

        async def observe_concurrency(
            context: StepContext, call_next: Callable[[], Awaitable[Any]]
        ) -> Any:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await anyio.sleep(0.01)
                return await call_next()
            finally:
                active -= 1

        runtime.step_middleware.add(observe_concurrency)
        report = await arun_pipeline(
            ParallelPipeline,
            profile=Profile(name="single-concurrency", concurrency=1),
            runtime=runtime,
            request=RunRequest(metadata={"concurrency": 4}),
        )

        assert report.status is RunStatus.SUCCEEDED, report.diagnostics
        assert peak == 1

    anyio.run(exercise)


def test_verified_stored_plan_runs_without_replanning() -> None:
    plan_document = SimplePipeline.plan(profile="development")
    plan = PipelinePlan.from_dict(plan_document.to_dict(), verify=True)
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=3, name=" stored ")])

    report = run_pipeline(plan, profile="development", runtime=runtime)

    assert report.status is RunStatus.SUCCEEDED
    assert runtime.memory.get("out")[0].name == "Stored"


def test_execution_envelope_round_trips_verified_plan_and_request() -> None:
    definition = definition_from_pipeline(SimplePipeline)
    profile = Profile(
        name="qualified",
        retry_max_attempts=5,
        timeout_seconds=120,
    )
    plan_document = SimplePipeline.plan(profile=profile)
    plan = PipelinePlan.from_dict(plan_document.to_dict(), verify=True)
    request = RunRequest(
        retry=RetryPolicy(max_attempts=1),
        extensions={"plugin:example/trace": {"enabled": True}},
    )
    envelope = ExecutionEnvelope.create(
        definition_id=definition.pipeline_id,
        revision_selector="latest-approved",
        revision_id="rev-1",
        definition=definition,
        plan=plan,
        profile_name="qualified",
        request=request,
    )

    encoded = envelope.to_json()
    restored = ExecutionEnvelope.from_json(encoded)

    assert restored.to_json() == encoded
    assert restored.definition_fingerprint == definition.fingerprint or (
        restored.definition_fingerprint == envelope.definition_fingerprint
    )
    assert restored.plan_fingerprint == plan.fingerprint
    assert restored.revision_id == "rev-1"
    assert restored.effective_request == envelope.effective_request
    assert restored.setting_provenance == envelope.setting_provenance
    assert restored.setting_provenance["request.retry.max_attempts"] == "request"
    assert restored.effective_request["retry"]["max_attempts"] == 1
    assert restored.effective_request["timeout"]["run_seconds"] == 120
    assert restored.setting_provenance["request.timeout.run_seconds"] == (
        "profile:qualified"
    )
    assert RunRequest.from_dict(restored.run_request).extensions == request.extensions
    with pytest.raises(TypeError):
        cast(dict[str, object], restored.plan_document["metadata"])["changed"] = True

    legacy_document = envelope.to_dict()
    legacy_document["schema"] = "etlantic.execution_envelope/1"
    legacy_document.pop("effective_request")
    legacy_document["run_request"].pop("explicit_settings")
    legacy_document["run_request"].pop("extensions")
    legacy_document["setting_provenance"] = {"retry_max_attempts": "profile.default"}
    upgraded = ExecutionEnvelope.from_dict(legacy_document)
    assert upgraded.schema == "etlantic.execution_envelope/2"
    assert upgraded.effective_request["retry"]["max_attempts"] == 5
    assert upgraded.effective_request["timeout"]["run_seconds"] == 120


def test_execution_envelope_rejects_tampered_plan_and_secret_fields() -> None:
    definition = definition_from_pipeline(SimplePipeline)
    plan_document = SimplePipeline.plan(profile="development")
    plan = PipelinePlan.from_dict(plan_document.to_dict(), verify=True)
    envelope = ExecutionEnvelope.create(
        definition_id=definition.pipeline_id,
        revision_selector=definition.pipeline_id,
        revision_id=None,
        definition=definition,
        plan=plan,
        profile_name="development",
        request=RunRequest(),
    )
    tampered = envelope.to_dict()
    tampered["plan_document"]["profile_name"] = "production"
    with pytest.raises(ValueError, match="fingerprint"):
        ExecutionEnvelope.from_dict(tampered)

    secret = envelope.to_dict()
    secret["setting_provenance"]["password"] = "should-never-persist"
    with pytest.raises(ValueError, match="sensitive field"):
        ExecutionEnvelope.from_dict(secret)

    tampered_settings = envelope.to_dict()
    tampered_settings["effective_request"]["retry"]["max_attempts"] = 9
    with pytest.raises(ValueError, match="Effective request"):
        ExecutionEnvelope.from_dict(tampered_settings)

    tampered_provenance = envelope.to_dict()
    tampered_provenance["setting_provenance"]["request.retry.max_attempts"] = (
        "profile:development"
    )
    with pytest.raises(ValueError, match="Setting provenance"):
        ExecutionEnvelope.from_dict(tampered_provenance)


def test_packaged_worker_executes_accepted_envelope_and_recovers_report(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    target = tmp_path / "target.csv"
    source.write_text(json.dumps([{"id": 7, "name": "Ada"}]), encoding="utf-8")

    class FileTransferPipeline(Pipeline):
        raw: Extract[Row] = Extract(asset="file_in")
        out: Load[Row] = Load(input=raw, asset="file_out")

    planning = PlanningContext.create(profile="development")
    planning.registry.register_binding(
        BindingDescriptor(
            binding="file_in",
            provider="json",
            location=str(source),
            kind="source",
        )
    )
    planning.registry.register_binding(
        BindingDescriptor(
            binding="file_out",
            provider="csv",
            location=str(target),
            kind="sink",
        )
    )
    definition = definition_from_pipeline(FileTransferPipeline)
    plan_document = FileTransferPipeline.plan(profile="development", context=planning)
    plan = PipelinePlan.from_dict(plan_document.to_dict(), verify=True)
    envelope = ExecutionEnvelope.create(
        definition_id=definition.pipeline_id,
        revision_selector="rev-1",
        revision_id="rev-1",
        definition=definition,
        plan=plan,
        profile_name="development",
        request=RunRequest(),
    )

    ctx = ControlPlaneContext(
        principal=Principal("worker"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "workspace-a"),
        environment=EnvironmentRef("development"),
        security_domain=SecurityDomain("internal"),
    )
    durable = MemoryDurableWorkStore()
    submission, _created = durable.accept(
        ctx,
        idempotency_key="managed-run-1",
        operation="run.submit",
        plan_fingerprint=envelope.plan_fingerprint,
        revision_id="rev-1",
        input_snapshot=envelope.to_json(),
        run_id=managed_run_id(ctx, "managed-run-1"),
    )
    worker = ManagedExecutionAdapter(
        report_root=tmp_path / "reports", profile=resolve_profile("development")
    )

    report = worker(
        ctx,
        submission=submission,
        submission_id=submission.submission_id,
        attempt_id="attempt-1",
        fencing_token=1,
    )
    replayed = worker(
        ctx,
        submission=submission,
        submission_id=submission.submission_id,
        attempt_id="attempt-2",
        fencing_token=2,
        recovered_attempt=True,
    )

    assert report.status is RunStatus.SUCCEEDED
    assert report.run_id == replayed.run_id
    assert replayed.status is RunStatus.SUCCEEDED
    assert target.read_text(encoding="utf-8").splitlines() == [
        "id,name",
        "7,Ada",
    ]
    drifted_worker = ManagedExecutionAdapter(
        report_root=tmp_path / "reports",
        profile=resolve_profile("development").with_updates(security_mode="test"),
    )
    recovered_with_drift = drifted_worker(
        ctx,
        submission=submission,
        submission_id=submission.submission_id,
        attempt_id="attempt-drifted-profile",
        fencing_token=3,
        recovered_attempt=True,
    )
    assert recovered_with_drift.status is RunStatus.SUCCEEDED


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
