# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportMissingImports=false, reportMissingParameterType=false, reportOptionalSubscript=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUnusedFunction=false, reportUnusedVariable=false
"""Shared headless and HTTP managed application contract tests."""

from __future__ import annotations

from threading import Event, Thread

import anyio
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_fingerprint, pipeline_to_dict
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    ExecutionEnvelope,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemoryEventStore,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.profile import resolve_profile
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.managed_execution import ManagedExecutionAdapter
from etlantic.runtime.request import RunRequest
from etlantic.service import ManagedApplicationService
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)


class Row(Data):
    id: int


class CopyRows(Transformation):
    rows: Input[Row]
    result: Output[Row]


@CopyRows.implementation("local")
def _copy_rows(rows: list[Row]) -> list[Row]:
    return list(rows)


class ManagedPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    copied = CopyRows.step(rows=raw)
    output: Load[Row] = Load(input=copied.result, asset="output")


class ManagedFilePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="file-in")
    output: Load[Row] = Load(input=raw, asset="file-out")


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _wired(tmp_path):
    ctx = _ctx()
    authz = MemoryAuthorizer()
    for action in (
        "definition.write",
        "definition.read",
        "definition.validate",
        "definition.plan",
        "definition.edit",
        "run.submit",
        "run.cancel",
        "run.retry",
        "run.actions",
        "run.read",
        "run.report",
        "run.artifacts",
        "run.lineage",
    ):
        authz.grant(ctx, action)
    definitions = MemoryDefinitionRepository()
    submissions = MemorySubmissionStore()
    durable = MemoryDurableWorkStore()
    events = MemoryEventStore()
    service = ManagedApplicationService(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        durable_work=durable,
        events=events,
        profile="development",
        report_root=tmp_path / "reports",
    )
    definition = definition_from_pipeline(ManagedPipeline)
    service.register_definition(ctx, "pipe", pipeline_to_dict(definition))
    return ctx, authz, definitions, submissions, durable, events, service


def test_headless_and_http_share_verified_acceptance(tmp_path) -> None:
    ctx, authz, definitions, submissions, durable, events, service = _wired(tmp_path)
    expected = service.submit_run(ctx, "pipe", idempotency_key="same-intent")

    api = ETLanticAPI(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        events=events,
        durable_work=durable,
        profile="development",
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    client = TestClient(create_app(api, managed_execution=True))
    definition_document = pipeline_to_dict(definition_from_pipeline(ManagedPipeline))
    registered = client.put(
        "/v1/definitions/pipe",
        headers={"X-Principal": "alice"},
        json={"document": definition_document},
    )
    assert registered.status_code == 200
    assert registered.json()["fingerprint"] == pipeline_fingerprint(
        definition_from_pipeline(ManagedPipeline)
    )
    expected_validation = service.validate_definition(ctx, "pipe")
    validated = client.post(
        "/v1/definitions/pipe/validate", headers={"X-Principal": "alice"}
    )
    assert validated.status_code == 200
    assert validated.json()["fingerprint"] == expected_validation["fingerprint"]
    expected_plan = service.plan_definition(ctx, "pipe")
    planned = client.post(
        "/v1/definitions/pipe/plan",
        headers={"X-Principal": "alice"},
        json={"request": RunRequest().to_dict()},
    )
    assert planned.status_code == 200
    assert planned.json()["metadata"]["fingerprint"] == expected_plan["fingerprint"]
    assert planned.json()["plan"] == expected_plan["plan"]

    response = client.post(
        "/v1/definitions/pipe/runs",
        headers={"X-Principal": "alice", "Idempotency-Key": "same-intent"},
        json={"payload": {"request": RunRequest().to_dict()}},
    )

    assert response.status_code == 202
    assert response.json()["acceptance_id"] == expected.acceptance_id
    accepted = durable.get_submission(ctx, expected.submission_id)
    envelope = ExecutionEnvelope.from_json(accepted.input_snapshot)
    assert accepted.plan_fingerprint == envelope.plan_fingerprint
    assert envelope.definition_fingerprint == pipeline_fingerprint(
        definition_from_pipeline(ManagedPipeline)
    )
    assert envelope.canonical_intent_fingerprint


def test_headless_and_http_share_run_actions_and_cancellation(tmp_path) -> None:
    ctx, authz, definitions, submissions, durable, events, service = _wired(tmp_path)
    headless = service.submit_run(ctx, "pipe", idempotency_key="cancel-headless")
    headless_actions = service.get_run_actions(ctx, headless.resource_id)
    assert headless_actions["actions"] == [
        {"name": "cancel", "allowed": True, "reason": None},
        {"name": "retry", "allowed": False, "reason": "non_retryable_state"},
    ]
    headless_cancelled = service.cancel_run(ctx, headless.resource_id)
    assert headless_cancelled["status"] == "cancel_requested"

    api = ETLanticAPI(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        events=events,
        durable_work=durable,
        profile="development",
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    ).enable_managed_execution()
    client = TestClient(create_app(api))
    http = service.submit_run(ctx, "pipe", idempotency_key="cancel-http")
    headers = {"X-Principal": "alice"}
    actions = client.get(f"/v1/runs/{http.resource_id}/actions", headers=headers)
    assert actions.status_code == 200
    assert actions.json()["actions"] == headless_actions["actions"]
    cancelled = client.post(f"/v1/runs/{http.resource_id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == headless_cancelled["status"]


def test_retry_reuses_accepted_plan_and_runs_through_http(tmp_path) -> None:
    from etlantic.control_plane.durable_models import EffectRecord
    from etlantic.runtime.managed_errors import ExecutionRejected

    source = tmp_path / "retry-source.json"
    target = tmp_path / "retry-target.csv"
    source.write_text('[{"id": 17}]', encoding="utf-8")
    ctx, authz, definitions, submissions, durable, events, service = _wired(
        tmp_path / "control"
    )

    def planning_context(_ctx, profile):
        planning = PlanningContext.create(profile=profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="file-in",
                provider="json",
                location=str(source),
                kind="source",
            )
        )
        planning.registry.register_binding(
            BindingDescriptor(
                binding="file-out",
                provider="csv",
                location=str(target),
                kind="sink",
            )
        )
        return planning

    service.planning_context_factory = planning_context
    service.report_root = tmp_path / "reports"
    service.register_definition(
        ctx,
        "file-pipe",
        pipeline_to_dict(definition_from_pipeline(ManagedFilePipeline)),
    )
    failed = service.submit_run(ctx, "file-pipe", idempotency_key="initial-run")
    refusing_host = ExecutionHost(
        durable,
        owner_id="reject-once",
        runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ExecutionRejected("transient worker startup rejection")
        ),
    )
    assert refusing_host.tick(ctx) == 1
    assert service.get_run_status(ctx, failed.resource_id)["status"] == "failed"
    assert service.get_run_actions(ctx, failed.resource_id)["actions"][1] == {
        "name": "retry",
        "allowed": True,
        "reason": None,
    }

    retry = service.retry_run(ctx, failed.resource_id, idempotency_key="retry-once")
    assert (
        service.retry_run(
            ctx, failed.resource_id, idempotency_key="retry-once"
        ).to_dict()
        == retry.to_dict()
    )
    retry_envelope = ExecutionEnvelope.from_json(
        durable.get_submission(ctx, retry.submission_id).input_snapshot
    )
    assert (
        retry_envelope.plan_fingerprint
        == durable.get_submission(ctx, failed.submission_id).plan_fingerprint
    )
    assert retry_envelope.evidence_refs["command"] == "retry"
    assert retry_envelope.evidence_refs["parent_submission_id"] == failed.submission_id

    api = ETLanticAPI(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        events=events,
        durable_work=durable,
        profile="development",
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    ).enable_managed_execution()
    client = TestClient(create_app(api))
    response = client.post(
        f"/v1/runs/{failed.resource_id}/retry",
        headers={"X-Principal": "alice", "Idempotency-Key": "retry-once"},
    )
    assert response.status_code == 202
    assert response.json()["submission_id"] == retry.submission_id
    parent = durable.get_submission(ctx, failed.submission_id)
    durable.record_effect(
        ctx,
        EffectRecord(
            effect_id=f"{failed.submission_id}:execution",
            submission_id=failed.submission_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            status="unknown",
            recorded_at=parent.created_at,
        ),
    )
    assert (
        service.retry_run(
            ctx, failed.resource_id, idempotency_key="retry-once"
        ).to_dict()
        == retry.to_dict()
    )
    assert service.get_run_actions(ctx, failed.resource_id)["actions"][1] == {
        "name": "retry",
        "allowed": False,
        "reason": "effect_requires_reconciliation",
    }
    with pytest.raises(ControlPlaneError, match="effect is reconciled"):
        service.retry_run(ctx, failed.resource_id, idempotency_key="unsafe-retry")

    assert (
        ExecutionHost(
            durable,
            owner_id="retry-worker",
            runner=ManagedExecutionAdapter(report_root=tmp_path / "reports"),
        ).tick(ctx)
        == 1
    )
    assert target.read_text(encoding="utf-8").splitlines() == ["id", "17"]
    assert service.get_run_status(ctx, retry.resource_id)["status"] == "completed"
    retry_lineage = service.get_run_lineage(ctx, retry.resource_id)
    assert retry_lineage["submission_id"] == retry.submission_id
    assert {
        "from": failed.resource_id,
        "to": retry.resource_id,
        "kind": "retry",
    } in retry_lineage["edges"]


def test_definition_edit_is_shared_with_http_adapter(tmp_path) -> None:
    ctx, _authz, _definitions, _submissions, _durable, _events, service = _wired(
        tmp_path / "headless"
    )
    definition = definition_from_pipeline(ManagedPipeline)
    document = pipeline_to_dict(definition)
    node = dict(document["nodes"][0])
    metadata = dict(node.get("metadata") or {})
    metadata["plugin:managed-test"] = "updated"
    node["metadata"] = metadata
    command = {
        "op": "update_node",
        "payload": {"name": node["name"], "node": node},
    }
    expected = service.edit_definition(
        ctx,
        "pipe",
        command,
        expected_fingerprint=pipeline_fingerprint(definition),
    )

    ctx_http, authz, definitions, submissions, durable, events, _http_service = _wired(
        tmp_path / "http"
    )
    api = ETLanticAPI(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        events=events,
        durable_work=durable,
        profile="development",
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    ).enable_managed_execution()
    response = TestClient(create_app(api)).post(
        "/v1/definitions/pipe/edit",
        headers={"X-Principal": "alice"},
        json={
            "expected_fingerprint": pipeline_fingerprint(definition),
            "command": command,
        },
    )

    assert response.status_code == 200
    assert response.json()["fingerprint"] == expected["fingerprint"]
    assert response.json()["document"] == expected["document"]
    assert ctx_http.scope_key == ctx.scope_key


def test_accepted_file_transfer_publishes_real_report_and_effect(tmp_path) -> None:
    source = tmp_path / "source.json"
    target = tmp_path / "target.csv"
    source.write_text('[{"id": 7}]', encoding="utf-8")
    ctx = _ctx()
    authz = MemoryAuthorizer()
    authz.grant(ctx, "definition.write")
    authz.grant(ctx, "run.submit")
    authz.grant(ctx, "run.read")
    authz.grant(ctx, "run.report")
    authz.grant(ctx, "run.artifacts")
    authz.grant(ctx, "run.lineage")
    definitions = MemoryDefinitionRepository()
    submissions = MemorySubmissionStore()
    durable = MemoryDurableWorkStore()
    report_root = tmp_path / "reports"

    def planning_context(_ctx, profile):
        planning = PlanningContext.create(profile=profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="file-in",
                provider="json",
                location=str(source),
                kind="source",
            )
        )
        planning.registry.register_binding(
            BindingDescriptor(
                binding="file-out",
                provider="csv",
                location=str(target),
                kind="sink",
            )
        )
        return planning

    service = ManagedApplicationService(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        durable_work=durable,
        profile="development",
        report_root=report_root,
        planning_context_factory=planning_context,
    )
    service.register_definition(
        ctx,
        "file-pipe",
        pipeline_to_dict(definition_from_pipeline(ManagedFilePipeline)),
    )
    receipt = service.submit_run(ctx, "file-pipe", idempotency_key="file-transfer")
    processed = ExecutionHost(
        durable,
        owner_id="worker-test",
        runner=ManagedExecutionAdapter(report_root=report_root),
    ).tick(ctx)

    assert processed == 1
    assert target.read_text(encoding="utf-8").splitlines() == ["id", "7"]
    status = service.get_run_status(ctx, receipt.resource_id)
    report = service.get_run_report(ctx, receipt.resource_id)
    lineage = service.get_run_lineage(ctx, receipt.resource_id)
    assert status["status"] == "completed"
    assert report["run_id"] == receipt.resource_id
    assert report["status"] == "succeeded"
    assert lineage["submission_id"] == receipt.submission_id
    assert (
        durable.get_effect(ctx, f"{receipt.submission_id}:execution").status
        == "committed"
    )


def test_managed_worker_cancels_real_runtime_and_does_not_write_target(
    tmp_path,
) -> None:
    source = tmp_path / "cancel-source.json"
    target = tmp_path / "cancel-target.csv"
    source.write_text('[{"id": 7}]', encoding="utf-8")
    ctx = _ctx()
    authz = MemoryAuthorizer()
    authz.grant(ctx, "definition.write")
    authz.grant(ctx, "definition.read")
    authz.grant(ctx, "definition.plan")
    authz.grant(ctx, "run.submit")
    authz.grant(ctx, "run.report")
    definitions = MemoryDefinitionRepository()
    submissions = MemorySubmissionStore()
    durable = MemoryDurableWorkStore()
    started = Event()

    def planning_context(_ctx, profile):
        planning = PlanningContext.create(profile=profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="file-in",
                provider="json",
                location=str(source),
                kind="source",
            )
        )
        planning.registry.register_binding(
            BindingDescriptor(
                binding="file-out",
                provider="csv",
                location=str(target),
                kind="sink",
            )
        )
        return planning

    report_root = tmp_path / "cancel-reports"
    service = ManagedApplicationService(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        durable_work=durable,
        profile="development",
        report_root=report_root,
        planning_context_factory=planning_context,
    )
    service.register_definition(
        ctx,
        "cancel-pipe",
        pipeline_to_dict(definition_from_pipeline(ManagedFilePipeline)),
    )
    receipt = service.submit_run(
        ctx, "cancel-pipe", idempotency_key="cancel-during-run"
    )

    runtime = PipelineRuntime()
    runtime.ensure_plugins_for_profile(resolve_profile("development"))

    async def pause_before_run(_context, call_next):
        started.set()
        await anyio.sleep(10)
        return await call_next()

    runtime.add_run_middleware(pause_before_run, name="test-cancellation-window")

    def runtime_factory() -> PipelineRuntime:
        return runtime

    host = ExecutionHost(
        durable,
        owner_id="cancel-integration-worker",
        ttl_seconds=1,
        runner=ManagedExecutionAdapter(
            runtime_factory=runtime_factory, report_root=report_root
        ),
    )
    errors: list[Exception] = []

    def run_worker() -> None:
        try:
            host.tick(ctx)
        except Exception as exc:
            errors.append(exc)

    worker = Thread(target=run_worker, daemon=True)
    worker.start()
    assert started.wait(timeout=10)
    durable.cancel_submission(ctx, receipt.submission_id)
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert errors == []
    assert not target.exists()
    assert durable.get_submission(ctx, receipt.submission_id).status == "cancelled"
    report = service.get_run_report(ctx, receipt.resource_id)
    assert report["status"] == "cancelled"
    assert durable.get_effect(ctx, f"{receipt.submission_id}:execution").status == (
        "unknown"
    )


def test_replay_uses_accepted_snapshot_and_changed_intent_conflicts(tmp_path) -> None:
    ctx, _authz, definitions, _submissions, durable, _events, service = _wired(tmp_path)
    accepted = service.submit_run(ctx, "pipe", idempotency_key="retry")
    original = durable.get_submission(ctx, accepted.submission_id)

    # The idempotent path returns the immutable admitted snapshot without
    # resolving the current mutable definition again.
    definitions.put(ctx, "pipe", {"not": "a canonical definition"})
    replayed = service.submit_run(ctx, "pipe", idempotency_key="retry")
    assert replayed.to_dict() == accepted.to_dict()
    assert durable.get_submission(ctx, accepted.submission_id) == original

    with pytest.raises(ControlPlaneError, match="different canonical intent"):
        service.submit_run(
            ctx,
            "pipe",
            idempotency_key="retry",
            request=RunRequest(no_write=True),
        )


def test_managed_http_rejects_non_string_revision_selector(tmp_path) -> None:
    ctx, authz, definitions, submissions, durable, events, _service = _wired(tmp_path)
    api = ETLanticAPI(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        events=events,
        durable_work=durable,
        profile="development",
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    ).enable_managed_execution()
    client = TestClient(create_app(api))
    response = client.post(
        "/v1/definitions/pipe/runs",
        headers={"X-Principal": "alice", "Idempotency-Key": "bad-selector"},
        json={"payload": {"revision_selector": ["current"]}},
    )

    assert response.status_code == 400
    assert durable.pending_outbox(ctx) == []
