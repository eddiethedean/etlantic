# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportMissingImports=false, reportMissingParameterType=false, reportOptionalSubscript=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUnusedFunction=false, reportUnusedVariable=false
"""Shared headless and HTTP managed application contract tests."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier, Event, Thread
from typing import Any, cast

import anyio
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx2")

from fastapi.testclient import TestClient

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Parameter,
    Pipeline,
    Transformation,
)
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import (
    pipeline_fingerprint,
    pipeline_from_dict,
    pipeline_to_dict,
)
from etlantic.control_plane import (
    AliasRecord,
    AuthzDecision,
    ControlPlaneContext,
    DefinitionResolution,
    EnvironmentRef,
    ExecutionEnvelope,
    FakeScheduleClock,
    MemoryApprovalStore,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemoryEventStore,
    MemoryPolicyProvider,
    MemoryQuotaProvider,
    MemoryRegistryProvider,
    MemoryScheduleStore,
    MemorySubmissionStore,
    PolicyDecision,
    PolicyHook,
    Principal,
    RegistryDefinitionRepository,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.profile import Profile, resolve_profile
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime.action_execution_host import ActionExecutionHost
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.managed_execution import ManagedExecutionAdapter, managed_run_id
from etlantic.runtime.request import (
    MaterializationPolicy,
    RunRequest,
    TimeoutPolicy,
)
from etlantic.runtime.scheduler_service import SchedulerService
from etlantic.service import ManagedApplicationService
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_dependency_from_callable,
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


class LimitRows(Transformation):
    rows: Input[Row]
    limit: Parameter[int]
    result: Output[Row]


@LimitRows.implementation("local")
def _limit_rows(rows: list[Row], limit: int) -> list[Row]:
    return list(rows)[:limit]


class ParameterManagedPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    limited = LimitRows.step(rows=raw)
    output: Load[Row] = Load(input=limited.result, asset="output")


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _wired(
    tmp_path: Path,
    *,
    profile: Profile | str = "development",
) -> tuple[
    ControlPlaneContext,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemorySubmissionStore,
    MemoryDurableWorkStore,
    MemoryEventStore,
    ManagedApplicationService,
]:
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
        "run.events",
        "connector.catalog",
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
        profile=profile,
        report_root=tmp_path / "reports",
    )
    definition = definition_from_pipeline(ManagedPipeline)
    service.register_definition(ctx, "pipe", pipeline_to_dict(definition))
    return ctx, authz, definitions, submissions, durable, events, service


def _accepted_envelope(
    durable: MemoryDurableWorkStore,
    ctx: ControlPlaneContext,
    submission_id: str,
) -> ExecutionEnvelope:
    record = durable.get_submission(ctx, submission_id)
    assert record.input_snapshot is not None
    return ExecutionEnvelope.from_json(record.input_snapshot)


def test_managed_run_identity_is_scoped_to_principal_and_operation(
    tmp_path: Path,
) -> None:
    ctx, authz, _definitions, submissions, _durable, _events, service = _wired(tmp_path)
    other_principal = replace(ctx, principal=Principal(subject="bob"))
    authz.grant(other_principal, "run.submit")

    alice = service.submit_run(ctx, "pipe", idempotency_key="shared-key")
    bob = service.submit_run(other_principal, "pipe", idempotency_key="shared-key")

    assert alice.resource_id is not None
    assert bob.resource_id is not None
    assert alice.resource_id != bob.resource_id
    assert alice.submission_id != bob.submission_id
    assert (
        submissions.get_run(ctx, alice.resource_id)["submission_id"]
        == alice.submission_id
    )
    assert (
        submissions.get_run(other_principal, bob.resource_id)["submission_id"]
        == bob.submission_id
    )
    assert managed_run_id(ctx, "shared-key", operation="run.retry") != alice.resource_id
    assert managed_run_id(ctx, "run.retry/child") != managed_run_id(
        ctx, "child", operation="run.retry"
    )


@pytest.mark.parametrize("backend", ["memory", "sqlmodel"])
def test_managed_reports_preserve_submitter_identity_across_workers_and_readers(
    tmp_path: Path,
    backend: str,
) -> None:
    ctx, authz, _definitions, _submissions, _durable, _events, service = _wired(
        tmp_path
    )
    engine = None
    report_store_factory = None
    if backend == "sqlmodel":
        pytest.importorskip("etlantic_sqlmodel")
        from etlantic_sqlmodel.control_plane import (
            SQLModelDurableWorkStore,
            SQLModelSubmissionStore,
            create_control_plane_tables,
            create_durable_tables,
            create_run_report_tables,
            create_sqlite_engine,
        )
        from etlantic_sqlmodel.control_plane.report_stores import SqlModelRunReportStore

        engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'identity.db'}")
        create_control_plane_tables(engine)
        create_durable_tables(engine)
        create_run_report_tables(engine)
        service.submissions = SQLModelSubmissionStore(engine)
        service.durable_work = SQLModelDurableWorkStore(engine)

        def sqlmodel_reports(caller: ControlPlaneContext) -> Any:
            return SqlModelRunReportStore(engine, caller)

        report_store_factory = sqlmodel_reports
        service.report_store_factory = report_store_factory

    source = tmp_path / "source.json"
    source.write_text('[{"id": 7}]', encoding="utf-8")

    def planning_context(
        _ctx: ControlPlaneContext, profile: Profile
    ) -> PlanningContext:
        planning = PlanningContext.create(profile=profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="file-in", provider="json", location=str(source), kind="source"
            )
        )
        planning.registry.register_binding(
            BindingDescriptor(
                binding="file-out",
                provider="csv",
                location=str(tmp_path / "output.csv"),
                kind="sink",
            )
        )
        return planning

    service.planning_context_factory = planning_context
    service.register_definition(
        ctx,
        "identity-pipe",
        pipeline_to_dict(definition_from_pipeline(ManagedFilePipeline)),
    )
    bob = replace(ctx, principal=Principal("bob", issuer="submitters", kind="workload"))
    authz.grant(bob, "run.submit")
    authz.grant(bob, "run.report")
    receipts = [
        service.submit_run(
            caller,
            "identity-pipe",
            idempotency_key="shared-key",
            request=RunRequest(metadata={"submitter": caller.principal.subject}),
        )
        for caller in (ctx, bob)
    ]
    runner = ManagedExecutionAdapter(
        report_root=tmp_path / "reports", report_store_factory=report_store_factory
    )
    try:
        worker = replace(
            ctx, principal=Principal("worker", issuer="workers", kind="service")
        )
        assert ExecutionHost(service.durable_work, runner=runner).tick(worker) == 2
        recovery_worker = replace(worker, principal=Principal("recovery-worker"))
        for receipt in receipts:
            recovered = runner(
                recovery_worker,
                submission=service.durable_work.get_submission(
                    ctx, receipt.submission_id
                ),
                submission_id=receipt.submission_id,
                attempt_id="recovered-attempt",
                fencing_token=1,
                recovered_attempt=True,
            )
            assert recovered.run_id == receipt.resource_id
            assert (
                recovered.metadata["etlantic.control_plane.execution"]["submission_id"]
                == receipt.submission_id
            )
        for reader in (ctx, bob):
            for receipt in receipts:
                assert receipt.resource_id is not None
                report = service.get_run_report(reader, receipt.resource_id)
                assert report["status"] == "succeeded"
                assert report["run_id"] == receipt.resource_id
                assert (
                    report["metadata"]["etlantic.control_plane.execution"][
                        "submission_id"
                    ]
                    == receipt.submission_id
                )
        assert receipts[0].resource_id != receipts[1].resource_id
    finally:
        if engine is not None:
            engine.dispose()


def test_managed_schedule_trigger_uses_pinned_managed_admission(
    tmp_path: Path,
) -> None:
    ctx, authz, definitions, submissions, durable, events, service = _wired(tmp_path)
    authz.grant(ctx, "schedule.write")
    authz.grant(ctx, "schedule.read")
    schedules = MemoryScheduleStore()
    api: Any = cast(
        Any,
        ETLanticAPI(
            authorizer=authz,
            definitions=definitions,
            submissions=submissions,
            events=events,
            durable_work=durable,
            schedule_store=schedules,
            managed_service=service,
            profile="development",
            context_factory=membership_context_factory(
                {"alice": ("tenant-a", "ws-1", "development", "default")}
            ),
            principal_dependency=principal_from_header,
        ),
    )
    client = TestClient(create_app(api))
    headers = {"X-Principal": "alice"}
    created = client.post(
        "/v1/definitions/pipe/schedules",
        headers=headers,
        json={"kind": "interval", "interval_seconds": 60, "overlap": "queue"},
    )
    assert created.status_code == 201, created.text
    schedule = created.json()
    resolution = definitions.resolve_revision(ctx, "pipe", "current")
    assert schedule["definition_revision_id"] == resolution.revision_id
    unresolved_policy = client.post(
        "/v1/definitions/pipe/schedules",
        headers=headers,
        json={
            "kind": "interval",
            "interval_seconds": 60,
            "parameter_refs": {"partition": "unresolved-ref"},
        },
    )
    assert unresolved_policy.status_code == 501
    assert len(schedules.list_schedules(ctx)) == 1

    nominal = "2026-10-01T12:00:00Z"
    triggered = client.post(
        f"/v1/schedules/{schedule['schedule_id']}/trigger",
        headers=headers,
        json={"nominal_fire_time": nominal},
    )
    assert triggered.status_code == 200, triggered.text
    firing = triggered.json()
    assert firing["status"] == "accepted"
    assert firing["metadata"]["admission"] == "managed"
    assert firing["metadata"]["definition_revision_id"] == resolution.revision_id
    submission = durable.get_submission(ctx, firing["submission_id"])
    assert submission.operation == "run.submit"
    assert submission.revision_id == resolution.revision_id
    assert submission.input_snapshot is not None
    envelope = ExecutionEnvelope.from_json(submission.input_snapshot)
    assert envelope.revision_id == resolution.revision_id
    assert envelope.plan_fingerprint == firing["metadata"]["plan_fingerprint"]
    assert len(durable.pending_outbox(ctx)) == 1

    replay = client.post(
        f"/v1/schedules/{schedule['schedule_id']}/trigger",
        headers=headers,
        json={"nominal_fire_time": nominal},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["submission_id"] == firing["submission_id"]
    assert replay.json()["created"] is False
    assert len(durable.pending_outbox(ctx)) == 1

    external = service.submit_run(
        ctx,
        "pipe",
        idempotency_key="same-revision-external-trigger",
        revision_selector=resolution.revision_id,
    )
    external_submission = durable.get_submission(ctx, external.submission_id)
    assert external_submission.input_snapshot is not None
    external_envelope = ExecutionEnvelope.from_json(external_submission.input_snapshot)
    assert external_submission.plan_fingerprint == submission.plan_fingerprint
    assert external_envelope.effective_fingerprint == envelope.effective_fingerprint
    assert len(durable.pending_outbox(ctx)) == 2


def test_external_workload_trigger_matches_manual_and_scheduled_admission(
    tmp_path: Path,
) -> None:
    ctx, _initial_authz, definitions, submissions, durable, events, service = _wired(
        tmp_path
    )
    workload = Principal(
        subject="event-runner", issuer="trusted-event-bus", kind="workload"
    )

    class TriggerAuthorizer:
        def authorize(
            self, auth_ctx: ControlPlaneContext, action: str, resource: str
        ) -> AuthzDecision:
            del resource
            human_admin = (
                auth_ctx.principal.kind == "human"
                and auth_ctx.principal.subject == "alice"
            )
            external_submitter = (
                auth_ctx.principal == workload and action == "run.submit"
            )
            allowed = human_admin or external_submitter
            return AuthzDecision(
                allowed=allowed,
                reason="authenticated trigger policy",
                disclosure="not_found",
            )

    authorizer = TriggerAuthorizer()
    service.authorizer = authorizer
    revision, profile_name = service.pin_schedule_definition_revision(ctx, "pipe")
    request = RunRequest()
    manual = service.submit_run(
        ctx,
        "pipe",
        idempotency_key="equivalence-manual",
        request=request,
        revision_selector=revision,
    )

    schedules = MemoryScheduleStore()
    nominal_time = "2026-10-01T14:00:00Z"
    schedule = schedules.create(
        ctx,
        definition_id="pipe",
        definition_revision_id=revision,
        profile_name=profile_name,
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        next_fire_at=nominal_time,
    )
    scheduler = SchedulerService(
        schedules,
        durable=durable,
        clock=FakeScheduleClock(datetime(2026, 10, 1, 14, 0, tzinfo=UTC)),
        owner_id="schedule-trigger",
        run_submitter=service.submit_scheduled_run,
    )
    assert scheduler.tick(ctx) == 1
    firing = schedules.list_firings(ctx, schedule.schedule_id)[0]
    assert firing.submission_id is not None

    def resolve_external_identity(request_context: Any) -> Principal:
        token = request_context.headers.get("Authorization")
        if token == "Bearer trusted-event-token":
            return workload
        if token == "Bearer authenticated-but-unauthorized-token":
            return Principal(
                subject="untrusted-runner",
                issuer="untrusted-event-bus",
                kind="workload",
            )
        raise ControlPlaneError.unauthorized("External trigger authentication failed")

    membership = {
        "alice": ("tenant-a", "ws-1", "development", "default"),
        "event-runner": ("tenant-a", "ws-1", "development", "default"),
        "untrusted-runner": ("tenant-a", "ws-1", "development", "default"),
    }
    api: Any = cast(
        Any,
        ETLanticAPI(
            authorizer=authorizer,
            definitions=definitions,
            submissions=submissions,
            events=events,
            durable_work=durable,
            managed_service=service,
            profile="development",
            context_factory=membership_context_factory(membership),
            principal_dependency=principal_dependency_from_callable(
                resolve_external_identity
            ),
        ),
    )
    client: Any = cast(Any, TestClient(create_app(api, with_lifespan=False)))
    external_headers = {"Authorization": "Bearer trusted-event-token"}
    payload = {
        "request": request.to_dict(),
        "revision_selector": revision,
    }
    unauthenticated = client.post(
        "/v1/definitions/pipe/runs",
        headers={"Idempotency-Key": "equivalence-no-auth"},
        json={"payload": payload},
    )
    spoofed_header = client.post(
        "/v1/definitions/pipe/runs",
        headers={
            "Authorization": "Bearer invalid-token",
            "X-Principal": "alice",
            "Idempotency-Key": "equivalence-spoofed-principal",
        },
        json={"payload": payload},
    )
    unauthorized_workload = client.post(
        "/v1/definitions/pipe/runs",
        headers={
            "Authorization": "Bearer authenticated-but-unauthorized-token",
            "Idempotency-Key": "equivalence-denied-workload",
        },
        json={"payload": payload},
    )
    assert unauthenticated.status_code == 401
    assert spoofed_header.status_code == 401
    assert unauthorized_workload.status_code == 404
    assert len(durable.pending_outbox(ctx)) == 2

    external = client.post(
        "/v1/definitions/pipe/runs",
        headers={
            **external_headers,
            "X-Principal": "alice",
            "Idempotency-Key": "equivalence-external",
        },
        json={"payload": payload},
    )
    assert external.status_code == 202, external.text
    external_submission = durable.get_submission(
        ControlPlaneContext(
            principal=workload,
            tenant=ctx.tenant,
            workspace=ctx.workspace,
            environment=ctx.environment,
            security_domain=ctx.security_domain,
        ),
        external.json()["submission_id"],
    )
    manual_submission = durable.get_submission(ctx, manual.submission_id)
    scheduled_submission = durable.get_submission(ctx, firing.submission_id)
    assert external_submission.principal_subject == "event-runner"
    assert external_submission.principal_issuer == "trusted-event-bus"
    assert external_submission.principal_kind == "workload"
    assert external_submission.revision_id == revision

    envelopes = [
        ExecutionEnvelope.from_json(item.input_snapshot)
        for item in (manual_submission, scheduled_submission, external_submission)
        if item.input_snapshot is not None
    ]
    assert len(envelopes) == 3
    assert (
        len(
            {
                item.plan_fingerprint
                for item in (
                    manual_submission,
                    scheduled_submission,
                    external_submission,
                )
            }
        )
        == 1
    )
    assert len({item.effective_fingerprint for item in envelopes}) == 1
    assert {item.revision_id for item in envelopes} == {revision}
    assert len(durable.pending_outbox(ctx)) == 3


def test_schedule_occurrence_snapshots_latest_approved_workload_and_refs(
    tmp_path: Path,
) -> None:
    profile = Profile(
        "development",
        secret_providers={"vault": "vault"},
    )
    ctx, base_authz, _old_definitions, submissions, durable, events, service = _wired(
        tmp_path, profile=profile
    )
    registry = MemoryRegistryProvider()
    definitions = RegistryDefinitionRepository(registry)
    service.definitions = definitions
    first_document = pipeline_to_dict(
        definition_from_pipeline(ParameterManagedPipeline)
    )
    service.register_definition(ctx, "pipe", first_document)
    first_revision = definitions.resolve_revision(ctx, "pipe", "current")
    second_document = json.loads(json.dumps(first_document))
    first_node = dict(second_document["nodes"][0])
    first_metadata = dict(first_node.get("metadata") or {})
    first_metadata["plugin:managed-schedule-snapshot"] = "edited-after-creation"
    first_node["metadata"] = first_metadata
    second_document["nodes"][0] = first_node
    second_document["fingerprint"] = pipeline_fingerprint(
        pipeline_from_dict(second_document, verify=False)
    )
    service.register_definition(ctx, "pipe", second_document)
    second_revision = definitions.resolve_revision(ctx, "pipe", "current")
    registry.revisions.put_alias(
        ctx,
        AliasRecord(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            alias="latest-approved",
            logical_id="pipe",
            revision_id=first_revision.revision_id,
        ),
    )
    parameter_values = {"param://limits/row-limit@v1": 10}

    def resolve_parameters(
        _context: ControlPlaneContext, references: Mapping[str, str]
    ) -> Mapping[str, Mapping[str, Any]]:
        reference = references["limited.limit"]
        return {"limited": {"limit": parameter_values[reference]}}

    service.schedule_parameter_resolver = resolve_parameters
    workload = Principal(
        subject="nightly-scheduler", issuer="trusted-scheduler", kind="workload"
    )
    base_authz.grant(ctx, "schedule.write")
    base_authz.grant(ctx, "schedule.bind_workload")
    base_authz.grant(ctx, "schedule.read")

    class ScheduleIdentityAuthorizer:
        def authorize(
            self, auth_ctx: ControlPlaneContext, action: str, resource: str
        ) -> AuthzDecision:
            if auth_ctx.principal == workload:
                allowed = action == "run.submit"
                return AuthzDecision(
                    allowed=allowed,
                    reason="scheduler workload policy",
                    disclosure="not_found",
                )
            return base_authz.authorize(auth_ctx, action, resource)

    authorizer = ScheduleIdentityAuthorizer()
    service.authorizer = authorizer

    class LoseFirstFiringLinkAck(MemoryScheduleStore):
        lose_ack = True

        def link_firing_submission(self, *args: Any, **kwargs: Any) -> Any:
            if self.lose_ack:
                self.lose_ack = False
                raise OSError("simulated scheduler process loss")
            return super().link_firing_submission(*args, **kwargs)

    schedules = LoseFirstFiringLinkAck()
    api: Any = cast(
        Any,
        ETLanticAPI(
            authorizer=authorizer,
            definitions=definitions,
            submissions=submissions,
            events=events,
            durable_work=durable,
            schedule_store=schedules,
            managed_service=service,
            profile=profile,
            context_factory=membership_context_factory(
                {
                    "alice": ("tenant-a", "ws-1", "development", "default"),
                    workload.subject: (
                        "tenant-a",
                        "ws-1",
                        "development",
                        "default",
                    ),
                }
            ),
            principal_dependency=principal_from_header,
        ),
    )
    client = cast(Any, TestClient(create_app(api, with_lifespan=False)))
    created = client.post(
        "/v1/definitions/pipe/schedules",
        headers={"X-Principal": "alice"},
        json={
            "spec": {
                "kind": "interval",
                "interval_seconds": 60,
                "overlap": "queue",
            },
            "revision_selector": "latest-approved",
            "parameter_refs": {"limited.limit": "param://limits/row-limit@v1"},
            "secret_refs": {
                "warehouse": {
                    "provider": "vault",
                    "name": "prod/warehouse",
                    "key": "password",
                    "version": "v7",
                }
            },
            "workload_identity": workload.to_dict(),
        },
    )
    assert created.status_code == 201, created.text
    schedule_payload = created.json()
    assert schedule_payload["revision_policy"] == "latest-approved"
    assert schedule_payload["definition_revision_id"] is None
    assert schedule_payload["workload_identity"] == workload.to_dict()
    schedule_id = str(schedule_payload["schedule_id"])

    registry.revisions.put_alias(
        ctx,
        AliasRecord(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            alias="latest-approved",
            logical_id="pipe",
            revision_id=second_revision.revision_id,
        ),
    )
    due = datetime.fromisoformat(
        str(schedule_payload["next_fire_at"]).replace("Z", "+00:00")
    )
    workload_ctx = ControlPlaneContext(
        principal=workload,
        tenant=ctx.tenant,
        workspace=ctx.workspace,
        environment=ctx.environment,
        security_domain=ctx.security_domain,
    )
    with pytest.raises(OSError, match="scheduler process loss"):
        SchedulerService(
            schedules,
            durable=durable,
            clock=FakeScheduleClock(due),
            owner_id="nightly-scheduler",
            run_submitter=service.submit_scheduled_run,
        ).tick(workload_ctx)

    first_firing = schedules.list_firings(ctx, schedule_id)[0]
    assert first_firing.submission_id is None
    assert first_firing.metadata["selected_definition_revision_id"] == (
        second_revision.revision_id
    )
    assert first_firing.metadata["trigger_principal"] == workload.to_dict()
    assert first_firing.metadata["parameter_fingerprint"]
    assert first_firing.metadata["reference_fingerprint"]
    first_pending = durable.pending_outbox(ctx)
    assert len(first_pending) == 1
    first_submission = durable.get_submission(ctx, first_pending[0].submission_id)
    first_envelope = ExecutionEnvelope.from_json(
        cast(str, first_submission.input_snapshot)
    )
    assert first_submission.principal_subject == workload.subject
    assert first_submission.principal_issuer == workload.issuer
    assert first_submission.principal_kind == "workload"
    assert first_submission.revision_id == second_revision.revision_id
    assert first_envelope.run_request["parameter_overrides"] == {
        "limited": {"limit": 10}
    }
    assert schedules.get(ctx, schedule_id).secret_refs["warehouse"]["version"] == ("v7")

    # The approval alias may move after the occurrence was accepted. Recovery
    # must use the persisted selected revision and the immutable v1/v7 refs.
    registry.revisions.put_alias(
        ctx,
        AliasRecord(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            alias="latest-approved",
            logical_id="pipe",
            revision_id=first_revision.revision_id,
        ),
    )
    recovered_schedules = MemoryScheduleStore()
    recovered_schedules.load(schedules.dump())
    recovered_durable = MemoryDurableWorkStore()
    recovered_durable.load(durable.dump())
    recovered_service = ManagedApplicationService(
        authorizer=authorizer,
        definitions=definitions,
        submissions=submissions,
        durable_work=recovered_durable,
        events=events,
        profile=profile,
        report_root=tmp_path / "reports",
        schedule_parameter_resolver=resolve_parameters,
    )
    restarted = SchedulerService(
        recovered_schedules,
        durable=recovered_durable,
        clock=FakeScheduleClock(due),
        owner_id="nightly-scheduler",
        run_submitter=recovered_service.submit_scheduled_run,
    )
    assert restarted.tick(workload_ctx) == 0
    recovered_firings = recovered_schedules.list_firings(ctx, schedule_id)
    assert len(recovered_firings) == 1
    assert recovered_firings[0].submission_id is not None
    assert (
        recovered_schedules.get(ctx, schedule_id).secret_refs["warehouse"]["version"]
        == "v7"
    )
    recovered_submission = recovered_durable.get_submission(
        workload_ctx, recovered_firings[0].submission_id
    )
    assert recovered_submission.revision_id == second_revision.revision_id
    assert recovered_submission.principal_subject == workload.subject
    assert len(recovered_durable.pending_outbox(ctx)) == 1


def test_managed_scheduler_recovers_occurrence_after_link_ack_loss(
    tmp_path: Path,
) -> None:
    ctx, authz, definitions, submissions, durable, events, service = _wired(tmp_path)
    pinned_revision, profile_name = service.pin_schedule_definition_revision(
        ctx, "pipe"
    )

    class LoseFirstLinkAck(MemoryScheduleStore):
        lose_ack = True

        def link_firing_submission(self, *args: Any, **kwargs: Any) -> Any:
            if self.lose_ack:
                self.lose_ack = False
                raise OSError("simulated process loss before firing link")
            return super().link_firing_submission(*args, **kwargs)

    schedules = LoseFirstLinkAck()
    due = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    schedule = schedules.create(
        ctx,
        definition_id="pipe",
        definition_revision_id=pinned_revision,
        profile_name=profile_name,
        spec=ScheduleSpec(kind="interval", interval_seconds=60, overlap="queue"),
        next_fire_at="2026-10-01T12:00:00Z",
    )
    # A concurrent edit creates a new current revision after schedule creation;
    # the occurrence must retain and execute the pinned revision.
    service.register_definition(
        ctx,
        "pipe",
        pipeline_to_dict(definition_from_pipeline(ManagedFilePipeline)),
    )
    scheduler = SchedulerService(
        schedules,
        durable=durable,
        clock=FakeScheduleClock(due),
        owner_id="managed-schedule-worker",
        run_submitter=service.submit_scheduled_run,
    )
    with pytest.raises(OSError, match="process loss"):
        scheduler.tick(ctx)

    initial_firing = schedules.list_firings(ctx, schedule.schedule_id)[0]
    assert initial_firing.status == "accepted"
    assert initial_firing.submission_id is None
    assert len(durable.pending_outbox(ctx)) == 1

    recovered_schedules = MemoryScheduleStore()
    recovered_schedules.load(schedules.dump())
    recovered_durable = MemoryDurableWorkStore()
    recovered_durable.load(durable.dump())
    recovered_service = ManagedApplicationService(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        durable_work=recovered_durable,
        events=events,
        profile="development",
        report_root=tmp_path / "reports",
    )
    restarted = SchedulerService(
        recovered_schedules,
        durable=recovered_durable,
        clock=FakeScheduleClock(due),
        owner_id="managed-schedule-worker",
        run_submitter=recovered_service.submit_scheduled_run,
    )
    assert restarted.tick(ctx) == 0
    recovered_firings = recovered_schedules.list_firings(ctx, schedule.schedule_id)
    assert len(recovered_firings) == 1
    assert recovered_firings[0].submission_id is not None
    recovered_submission = recovered_durable.get_submission(
        ctx, recovered_firings[0].submission_id
    )
    assert recovered_submission.operation == "run.submit"
    assert recovered_submission.revision_id == pinned_revision
    assert recovered_submission.input_snapshot is not None
    assert len(recovered_durable.pending_outbox(ctx)) == 1


def test_static_validate_and_plan_do_not_read_sources_or_run_transforms(
    tmp_path: Path,
) -> None:
    ctx, _authz, _definitions, _submissions, _durable, _events, service = _wired(
        tmp_path
    )
    transform_calls = 0
    source_path = tmp_path / "not-read.json"
    target_path = tmp_path / "not-written.csv"

    class ProbeTransform(Transformation):
        rows: Input[Row]
        result: Output[Row]

    @ProbeTransform.implementation("local")
    def probe_transform(rows: list[Row]) -> list[Row]:
        nonlocal transform_calls
        transform_calls += 1
        return rows

    class ProbePipeline(Pipeline):
        source: Extract[Row] = Extract(asset="probe-in")
        transformed = ProbeTransform.step(rows=source)
        output: Load[Row] = Load(input=transformed.result, asset="probe-out")

    def planning_context(
        _ctx: ControlPlaneContext, profile: Profile
    ) -> PlanningContext:
        planning = PlanningContext.create(profile=profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="probe-in",
                provider="json",
                location=str(source_path),
                kind="source",
            )
        )
        planning.registry.register_binding(
            BindingDescriptor(
                binding="probe-out",
                provider="csv",
                location=str(target_path),
                kind="sink",
            )
        )
        return planning

    service.planning_context_factory = planning_context
    service.register_definition(
        ctx,
        "planning-purity",
        pipeline_to_dict(definition_from_pipeline(ProbePipeline)),
    )

    validation = service.validate_definition(ctx, "planning-purity")
    planned = service.plan_definition(ctx, "planning-purity")

    assert validation["ok"] is True
    assert planned["plan"]["fingerprint"]
    assert transform_calls == 0
    assert not source_path.exists()
    assert not target_path.exists()


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


def test_managed_headless_and_http_command_semantics_match(tmp_path: Path) -> None:
    profile = Profile(
        name="managed-command-parity",
        security_mode="development",
        plugin_allowlist={"etlantic": None},
    )
    ctx, authz, definitions, submissions, durable, events, service = _wired(
        tmp_path, profile=profile
    )

    api = ETLanticAPI(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        events=events,
        durable_work=durable,
        managed_service=service,
        profile=profile,
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    ).enable_managed_execution()
    client = cast(Any, TestClient(create_app(api)))
    headers = {"X-Principal": "alice"}
    document = pipeline_to_dict(definition_from_pipeline(ManagedPipeline))

    headless_registered = service.register_definition(ctx, "parity-headless", document)
    http_registered = client.put(
        "/v1/definitions/parity-http",
        headers=headers,
        json={"document": document},
    )
    assert http_registered.status_code == 200
    assert {
        key: value
        for key, value in http_registered.json().items()
        if key != "definition_id"
    } == {
        key: value
        for key, value in headless_registered.items()
        if key != "definition_id"
    }

    headless_definition = service.get_definition(ctx, "parity-headless")
    http_definition = client.get("/v1/definitions/parity-headless", headers=headers)
    assert http_definition.status_code == 200
    assert http_definition.json() == {
        "definition_id": headless_definition["definition_id"],
        "document": headless_definition["document"],
    }

    first_node = dict(document["nodes"][0])
    first_node["metadata"] = {
        **dict(first_node.get("metadata") or {}),
        "plugin:parity": "first-edit",
    }
    first_edit = {
        "op": "update_node",
        "payload": {"name": first_node["name"], "node": first_node},
    }
    headless_edit = service.edit_definition(
        ctx,
        "parity-headless",
        first_edit,
        expected_fingerprint=headless_registered["fingerprint"],
    )
    http_edit = client.post(
        "/v1/definitions/parity-http/edit",
        headers=headers,
        json={
            "expected_fingerprint": http_registered.json()["fingerprint"],
            "command": first_edit,
        },
    )
    assert http_edit.status_code == 200
    assert {
        key: value for key, value in http_edit.json().items() if key != "definition_id"
    } == {key: value for key, value in headless_edit.items() if key != "definition_id"}

    headless_validation = service.validate_definition(ctx, "parity-headless")
    http_validation = client.post(
        "/v1/definitions/parity-http/validate", headers=headers
    )
    assert http_validation.status_code == 200
    assert {
        key: value
        for key, value in http_validation.json().items()
        if key != "definition_id"
    } == {
        key: value
        for key, value in headless_validation.items()
        if key != "definition_id"
    }

    headless_plan = service.plan_definition(ctx, "parity-headless")
    http_plan = client.post(
        "/v1/definitions/parity-http/plan",
        headers=headers,
        json={"request": RunRequest().to_dict()},
    )
    assert http_plan.status_code == 200
    assert http_plan.json()["plan"] == headless_plan["plan"]
    assert http_plan.json()["metadata"]["fingerprint"] == headless_plan["fingerprint"]

    service.register_definition(ctx, "parity-run", document)
    headless_receipt = service.submit_run(
        ctx, "parity-run", idempotency_key="parity-submit"
    )
    http_receipt = client.post(
        "/v1/definitions/parity-run/runs",
        headers={**headers, "Idempotency-Key": "parity-submit"},
        json={},
    )
    assert http_receipt.status_code == 202
    assert http_receipt.json()["resource_id"] == headless_receipt.resource_id
    assert http_receipt.json()["status"] == headless_receipt.status
    assert http_receipt.json()["submission_id"] == headless_receipt.submission_id
    assert http_receipt.json()["acceptance_id"] == headless_receipt.acceptance_id

    headless_status = service.get_run_status(ctx, str(headless_receipt.resource_id))
    http_status = client.get(
        f"/v1/runs/{headless_receipt.resource_id}", headers=headers
    )
    assert http_status.status_code == 200
    for field in (
        "status",
        "tenant_id",
        "workspace_id",
        "definition_id",
        "idempotency_key",
        "resource_type",
    ):
        assert http_status.json()[field] == headless_status[field]
    assert http_status.json()["run_id"]
    assert http_status.json()["submission_id"]
    assert http_status.json()["acceptance_id"]

    headless_actions = service.get_run_actions(ctx, str(headless_receipt.resource_id))
    http_actions = client.get(
        f"/v1/runs/{headless_receipt.resource_id}/actions", headers=headers
    )
    assert http_actions.status_code == 200
    assert http_actions.json() == headless_actions

    headless_events = service.list_run_events(ctx, str(headless_receipt.resource_id))
    http_events = client.get(
        f"/v1/runs/{headless_receipt.resource_id}/events/history", headers=headers
    )
    assert http_events.status_code == 200
    assert http_events.json() == headless_events

    for query, method in (
        ("report", service.get_run_report),
        ("lineage", service.get_run_lineage),
        ("artifacts", service.list_run_artifacts),
    ):
        with pytest.raises(ControlPlaneError) as headless_pending:
            method(ctx, str(headless_receipt.resource_id))
        http_pending = client.get(
            f"/v1/runs/{headless_receipt.resource_id}/{query}", headers=headers
        )
        assert http_pending.status_code == headless_pending.value.status
        assert http_pending.json()["code"] == headless_pending.value.code

    with pytest.raises(ControlPlaneError) as headless_missing:
        service.get_definition(ctx, "does-not-exist")
    http_missing = client.get("/v1/definitions/does-not-exist", headers=headers)
    assert http_missing.status_code == headless_missing.value.status
    assert http_missing.json()["code"] == headless_missing.value.code


def test_headless_run_event_pages_are_scoped_and_resumable(tmp_path: Path) -> None:
    ctx, authz, definitions, submissions, durable, events, service = _wired(tmp_path)
    receipt = service.submit_run(ctx, "pipe", idempotency_key="headless-events")
    run_id = receipt.resource_id
    assert run_id is not None
    events.append(ctx, kind="run.progress", payload={"run_id": "other-run"})
    events.append(ctx, kind="run.progress", payload={"run_id": run_id, "step": 1})
    events.append(ctx, kind="run.progress", payload={"run_id": run_id, "step": 2})

    first = service.list_run_events(ctx, run_id, limit=2)
    assert [item["kind"] for item in first["items"]] == ["run.accepted"]
    assert first["has_more"] is True
    api = ETLanticAPI(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        durable_work=durable,
        events=events,
        managed_service=service,
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    http = cast(Any, TestClient(create_app(api)))
    response = http.get(
        f"/v1/runs/{run_id}/events/history",
        params={"limit": 2},
        headers={"X-Principal": "alice"},
    )
    assert response.status_code == 200
    assert response.json() == first
    cursor = first["next_cursor"]
    assert isinstance(cursor, str)
    second = service.list_run_events(ctx, run_id, cursor=cursor, limit=2)
    assert [item["kind"] for item in second["items"]] == [
        "run.progress",
        "run.progress",
    ]
    assert second["has_more"] is False


def test_run_events_reports_and_artifacts_are_owner_isolated_across_adapters(
    tmp_path: Path,
) -> None:
    ctx, _authz, definitions, submissions, durable, events, service = _wired(tmp_path)
    owner = ControlPlaneContext(
        principal=ctx.principal,
        tenant=ctx.tenant,
        workspace=ctx.workspace,
        environment=ctx.environment,
        security_domain=ctx.security_domain,
        resource_owner_id="owner-a",
    )

    def scoped_context(
        subject: str,
        *,
        tenant_id: str = "tenant-a",
        workspace_id: str = "ws-1",
        environment: str = "development",
        domain: str = "default",
        resource_owner: str = "owner-a",
    ) -> ControlPlaneContext:
        return ControlPlaneContext(
            principal=Principal(subject, issuer="tests"),
            tenant=TenantRef(tenant_id),
            workspace=WorkspaceRef(tenant_id, workspace_id),
            environment=EnvironmentRef(environment),
            security_domain=SecurityDomain(domain),
            resource_owner_id=resource_owner,
        )

    foreign_contexts = [
        ("bob", scoped_context("bob", resource_owner="owner-b")),
        ("carol", scoped_context("carol", tenant_id="tenant-b")),
        ("dana", scoped_context("dana", workspace_id="ws-2")),
        ("erin", scoped_context("erin", environment="staging")),
        ("frank", scoped_context("frank", domain="restricted")),
    ]

    class OwnerScopedAuthorizer:
        def authorize(
            self,
            request_context: ControlPlaneContext,
            action: str,
            resource: str,
        ) -> AuthzDecision:
            _ = action, resource
            authorized_scope = (
                owner.tenant.tenant_id,
                owner.workspace.workspace_id,
                owner.environment.name,
                owner.security_domain.domain_id,
                owner.resource_owner_id,
            )
            requested_scope = (
                request_context.tenant.tenant_id,
                request_context.workspace.workspace_id,
                request_context.environment.name,
                request_context.security_domain.domain_id,
                request_context.resource_owner_id,
            )
            if requested_scope == authorized_scope:
                return AuthzDecision(allowed=True, reason="owner access")
            return AuthzDecision(
                allowed=False,
                reason="Resource not found",
                disclosure="not_found",
            )

    service.authorizer = OwnerScopedAuthorizer()
    report_store_calls: list[str] = []

    def report_store_must_not_be_opened(
        _request_context: ControlPlaneContext,
    ) -> Any:
        report_store_calls.append("opened")
        raise AssertionError("owner denial must happen before report lookup")

    service.report_store_factory = report_store_must_not_be_opened
    receipt = service.submit_run(owner, "pipe", idempotency_key="owner-run")
    assert receipt.resource_id is not None
    run_id = receipt.resource_id
    events.append(
        owner,
        kind="run.progress",
        payload={"run_id": run_id, "private_marker": "owner-a-event"},
    )

    api = ETLanticAPI(
        authorizer=service.authorizer,
        definitions=definitions,
        submissions=submissions,
        durable_work=durable,
        events=events,
        managed_service=service,
        context_factory=membership_context_factory(
            {
                "alice": ("tenant-a", "ws-1", "development", "default"),
                "bob": ("tenant-a", "ws-1", "development", "default"),
                "carol": ("tenant-b", "ws-1", "development", "default"),
                "dana": ("tenant-a", "ws-2", "development", "default"),
                "erin": ("tenant-a", "ws-1", "staging", "default"),
                "frank": ("tenant-a", "ws-1", "development", "restricted"),
            },
            resource_owners={
                "alice": "owner-a",
                "bob": "owner-b",
                "carol": "owner-a",
                "dana": "owner-a",
                "erin": "owner-a",
                "frank": "owner-a",
            },
        ),
        principal_dependency=principal_from_header,
    )
    client = cast(Any, TestClient(create_app(api)))

    owner_page = service.list_run_events(owner, run_id)
    owner_http = client.get(
        f"/v1/runs/{run_id}/events/history", headers={"X-Principal": "alice"}
    )
    assert owner_http.status_code == 200
    assert owner_http.json() == owner_page
    assert "owner-a-event" in owner_http.text

    for subject, foreign_context in foreign_contexts:
        headless_calls = [
            lambda context=foreign_context: service.get_run_status(context, run_id),
            lambda context=foreign_context: service.list_run_events(context, run_id),
            lambda context=foreign_context: service.get_run_report(context, run_id),
            lambda context=foreign_context: service.list_run_artifacts(context, run_id),
            lambda context=foreign_context: service.get_run_artifact_content(
                context, run_id, "private-artifact"
            ),
        ]
        http_requests = [
            ("GET", f"/v1/runs/{run_id}", {}),
            ("GET", f"/v1/runs/{run_id}/events/history", {}),
            ("GET", f"/v1/runs/{run_id}/report", {}),
            ("GET", f"/v1/runs/{run_id}/artifacts", {}),
            (
                "GET",
                f"/v1/runs/{run_id}/artifacts/content",
                {"params": {"artifact_id": "private-artifact"}},
            ),
        ]
        for headless_call, (method, path, options) in zip(
            headless_calls, http_requests, strict=True
        ):
            with pytest.raises(ControlPlaneError) as denied:
                headless_call()
            response = client.request(
                method,
                path,
                headers={"X-Principal": subject},
                **options,
            )
            assert (response.status_code, response.json()["code"]) == (
                denied.value.status,
                denied.value.code,
            )
            assert response.status_code == 404
            assert "owner-a-event" not in response.text
            assert "owner-a" not in response.text
    assert report_store_calls == []


def test_memory_definition_repository_current_tracks_reversion() -> None:
    definitions = MemoryDefinitionRepository()
    ctx = _ctx()
    original = {"version": "original"}
    changed = {"version": "changed"}
    definitions.put(ctx, "revision-order", original)
    original_revision = definitions.resolve_revision(ctx, "revision-order", "current")
    definitions.put(ctx, "revision-order", changed)
    changed_revision = definitions.resolve_revision(ctx, "revision-order", "current")

    definitions.put(ctx, "revision-order", original)
    current = definitions.resolve_revision(ctx, "revision-order", "current")

    assert current == original_revision
    assert changed_revision.revision_id != original_revision.revision_id
    assert (
        definitions.resolve_revision(
            ctx, "revision-order", changed_revision.revision_id
        )
        == changed_revision
    )


def test_submission_resolves_revision_once_and_binds_effective_policy(
    tmp_path: Path,
) -> None:
    ctx, _authz, _definitions, _submissions, durable, _events, service = _wired(
        tmp_path
    )
    registry = MemoryRegistryProvider()
    definitions = RegistryDefinitionRepository(registry)
    service.definitions = definitions
    original = definition_from_pipeline(ManagedPipeline)
    service.register_definition(ctx, "pipe", pipeline_to_dict(original))
    first_revision = definitions.resolve_revision(ctx, "pipe", "current")

    class RecordingPolicy(MemoryPolicyProvider):
        last_decision: Any = None

        def decide(
            self,
            ctx: ControlPlaneContext,
            *,
            hook: PolicyHook,
            plan_fingerprint: str | None = None,
            revision_id: str | None = None,
            resource: str | None = None,
            attributes: Mapping[str, Any] | None = None,
            bundle_id: str | None = None,
        ) -> PolicyDecision:
            decision = super().decide(
                ctx,
                hook=hook,
                plan_fingerprint=plan_fingerprint,
                revision_id=revision_id,
                resource=resource,
                attributes=attributes,
                bundle_id=bundle_id,
            )
            if hook == "pre_submit":
                self.last_decision = decision
            return decision

    policy = RecordingPolicy()
    service.policy = policy
    first_receipt = service.submit_run(
        ctx,
        "pipe",
        idempotency_key="revision-pinned",
        revision_selector=first_revision.revision_id,
    )
    first_envelope = _accepted_envelope(durable, ctx, first_receipt.submission_id)
    assert first_envelope.revision_id == first_revision.revision_id
    assert policy.last_decision.plan_fingerprint == first_envelope.effective_fingerprint
    assert policy.last_decision.revision_id == first_revision.revision_id

    changed_node = dict(pipeline_to_dict(original)["nodes"][0])
    changed_metadata = dict(changed_node.get("metadata") or {})
    changed_metadata["plugin:managed-revision-test"] = "second"
    changed_node["metadata"] = changed_metadata
    service.edit_definition(
        ctx,
        "pipe",
        {
            "op": "update_node",
            "payload": {"name": changed_node["name"], "node": changed_node},
        },
        expected_fingerprint=pipeline_fingerprint(original),
    )
    latest_revision = definitions.resolve_revision(ctx, "pipe", "current")
    registry.revisions.put_alias(
        ctx,
        AliasRecord(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            alias="latest-approved",
            logical_id="pipe",
            revision_id=latest_revision.revision_id,
        ),
    )

    approved_receipt = service.submit_run(
        ctx,
        "pipe",
        idempotency_key="revision-latest-approved",
        revision_selector="latest-approved",
    )
    approved_envelope = _accepted_envelope(durable, ctx, approved_receipt.submission_id)
    assert approved_envelope.revision_id == latest_revision.revision_id
    assert (
        approved_envelope.definition_fingerprint
        != first_envelope.definition_fingerprint
    )
    assert (
        policy.last_decision.plan_fingerprint == approved_envelope.effective_fingerprint
    )

    registry.revisions.put_alias(
        ctx,
        AliasRecord(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            alias="latest-approved",
            logical_id="pipe",
            revision_id=first_revision.revision_id,
        ),
    )
    retried = service.submit_run(
        ctx,
        "pipe",
        idempotency_key="revision-latest-approved",
        revision_selector="latest-approved",
    )
    assert retried.to_dict() == approved_receipt.to_dict()
    assert _accepted_envelope(durable, ctx, retried.submission_id).revision_id == (
        latest_revision.revision_id
    )


def test_approval_is_bound_to_resolved_effective_plan_and_revision(
    tmp_path: Path,
) -> None:
    ctx, _authz, _definitions, submissions, durable, _events, service = _wired(tmp_path)

    class CapturingPolicy(MemoryPolicyProvider):
        last_submit_decision: PolicyDecision | None = None

        def decide(
            self,
            ctx: ControlPlaneContext,
            *,
            hook: PolicyHook,
            plan_fingerprint: str | None = None,
            revision_id: str | None = None,
            resource: str | None = None,
            attributes: Mapping[str, Any] | None = None,
            bundle_id: str | None = None,
        ) -> PolicyDecision:
            decision = super().decide(
                ctx,
                hook=hook,
                plan_fingerprint=plan_fingerprint,
                revision_id=revision_id,
                resource=resource,
                attributes=attributes,
                bundle_id=bundle_id,
            )
            if hook == "pre_submit":
                self.last_submit_decision = decision
            return decision

    policy = CapturingPolicy()
    policy.set_rule("pre_submit", "require_approval")
    approvals = MemoryApprovalStore()
    service.policy = policy
    service.approvals = approvals

    with pytest.raises(ControlPlaneError, match="approval required"):
        service.submit_run(ctx, "pipe", idempotency_key="approval-required")
    decision = policy.last_submit_decision
    assert decision is not None
    assert decision.plan_fingerprint is not None
    assert decision.revision_id is not None

    approval = approvals.create(
        ctx,
        hook="pre_submit",
        plan_fingerprint=decision.plan_fingerprint,
        policy_fingerprint=decision.policy_fingerprint,
        revision_id=decision.revision_id,
    )
    reviewer = ControlPlaneContext(
        principal=Principal("reviewer", issuer="tests"),
        tenant=ctx.tenant,
        workspace=ctx.workspace,
        environment=ctx.environment,
        security_domain=ctx.security_domain,
    )
    approvals.decide(reviewer, approval_id=approval.approval_id, approve=True)

    accepted = service.submit_run(
        ctx, "pipe", idempotency_key="approval-bound-to-effective-plan"
    )
    envelope = _accepted_envelope(durable, ctx, accepted.submission_id)
    assert envelope.effective_fingerprint == decision.plan_fingerprint
    assert envelope.revision_id == decision.revision_id

    current_definition = pipeline_from_dict(
        service.get_definition(ctx, "pipe")["document"]
    )
    changed_node = dict(pipeline_to_dict(current_definition)["nodes"][0])
    changed_metadata = dict(changed_node.get("metadata") or {})
    changed_metadata["plugin:approval-binding-test"] = "new revision"
    changed_node["metadata"] = changed_metadata
    service.edit_definition(
        ctx,
        "pipe",
        {
            "op": "update_node",
            "payload": {"name": changed_node["name"], "node": changed_node},
        },
        expected_fingerprint=pipeline_fingerprint(current_definition),
    )

    with pytest.raises(ControlPlaneError, match="approval required and not satisfied"):
        service.submit_run(
            ctx,
            "pipe",
            idempotency_key="approval-cannot-cross-revision",
        )
    assert (
        submissions.lookup_idempotency(
            ctx,
            "approval-cannot-cross-revision",
            operation="run.submit",
        )
        is None
    )


def test_concurrent_same_intent_charges_workspace_quota_once(tmp_path: Path) -> None:
    ctx, _authz, definitions, _submissions, _durable, _events, service = _wired(
        tmp_path
    )
    quota = MemoryQuotaProvider()
    service.quotas = quota
    resolve_barrier = Barrier(2)
    resolve = definitions.resolve_revision

    def synchronized_resolution(
        ctx: ControlPlaneContext,
        definition_id: str,
        selector: str,
    ) -> DefinitionResolution:
        resolve_barrier.wait(timeout=10)
        return resolve(ctx, definition_id, selector)

    definitions.resolve_revision = synchronized_resolution

    def submit():
        return service.submit_run(
            ctx,
            "pipe",
            idempotency_key="concurrent-managed-submit",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(submit)
        second_future = pool.submit(submit)
        first = first_future.result()
        second = second_future.result()

    assert first.to_dict() == second.to_dict()
    assert quota.get_state(ctx).usage["concurrency"] == 1


def test_concurrent_changed_intent_conflicts_under_same_idempotency_key(
    tmp_path: Path,
) -> None:
    ctx, _authz, definitions, submissions, durable, _events, service = _wired(tmp_path)
    quota = MemoryQuotaProvider()
    service.quotas = quota
    resolve_barrier = Barrier(2)
    resolve = definitions.resolve_revision

    def synchronized_resolution(
        ctx: ControlPlaneContext,
        definition_id: str,
        selector: str,
    ) -> DefinitionResolution:
        resolve_barrier.wait(timeout=10)
        return resolve(ctx, definition_id, selector)

    definitions.resolve_revision = synchronized_resolution

    def submit(request: RunRequest | None = None):
        try:
            return service.submit_run(
                ctx,
                "pipe",
                idempotency_key="concurrent-changed-intent",
                request=request,
            )
        except ControlPlaneError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, (None, RunRequest(no_write=True))))

    receipts = [item for item in results if not isinstance(item, ControlPlaneError)]
    conflicts = [
        item
        for item in results
        if isinstance(item, ControlPlaneError) and item.status == 409
    ]
    assert len(receipts) == len(conflicts) == 1
    accepted = submissions.lookup_idempotency(
        ctx, "concurrent-changed-intent", operation="run.submit"
    )
    persisted = durable.get_submission_by_idempotency(
        ctx,
        idempotency_key="concurrent-changed-intent",
        operation="run.submit",
    )
    assert accepted is not None
    assert persisted is not None
    assert accepted.submission_id == persisted.submission_id
    assert quota.get_state(ctx).usage["concurrency"] == 1


def test_same_idempotency_key_has_principal_scoped_run_ids(
    tmp_path: Path,
) -> None:
    ctx, authz, _definitions, submissions, durable, _events, service = _wired(tmp_path)
    other_ctx = replace(ctx, principal=Principal("bob"))
    for action in ("definition.read", "run.submit"):
        authz.grant(other_ctx, action)

    alice = service.submit_run(ctx, "pipe", idempotency_key="shared-key")
    bob = service.submit_run(other_ctx, "pipe", idempotency_key="shared-key")

    assert alice.submission_id != bob.submission_id
    assert alice.resource_id != bob.resource_id
    assert alice.resource_id is not None
    assert bob.resource_id is not None
    assert submissions.get_run(ctx, alice.resource_id)["submission_id"] == (
        alice.submission_id
    )
    assert submissions.get_run(other_ctx, bob.resource_id)["submission_id"] == (
        bob.submission_id
    )
    assert durable.get_submission(ctx, alice.submission_id).run_id == alice.resource_id
    assert (
        durable.get_submission(other_ctx, bob.submission_id).run_id == bob.resource_id
    )


def test_submission_authorizes_resolved_resources_before_acceptance(
    tmp_path: Path,
) -> None:
    ctx, authz, definitions, submissions, durable, events, service = _wired(tmp_path)

    class ResourceDenyingAuthorizer(MemoryAuthorizer):
        def __init__(self) -> None:
            super().__init__(grants=set(authz.grants))
            self.resources: list[str] = []

        def authorize(self, ctx: ControlPlaneContext, action: str, resource: str):
            if resource.startswith("resource:"):
                self.resources.append(resource)
                if resource == "resource:file-in":
                    return AuthzDecision(
                        allowed=False,
                        reason="resource unavailable",
                        disclosure="not_found",
                    )
            return super().authorize(ctx, action, resource)

    scoped_authz = ResourceDenyingAuthorizer()
    service.authorizer = scoped_authz
    service.profile = Profile(
        name="development",
        assets={
            "file-in": "memory://source",
            "file-out": "memory://target",
        },
    )
    service.register_definition(
        ctx,
        "file-pipe",
        pipeline_to_dict(definition_from_pipeline(ManagedFilePipeline)),
    )

    with pytest.raises(ControlPlaneError) as denied:
        service.submit_run(ctx, "file-pipe", idempotency_key="resource-denied")

    assert denied.value.status == 404
    assert "resource:file-in" in scoped_authz.resources
    assert "resource:file-out" not in scoped_authz.resources
    assert (
        submissions.lookup_idempotency(ctx, "resource-denied", operation="run.submit")
        is None
    )
    assert (
        durable.get_submission_by_idempotency(
            ctx,
            idempotency_key="resource-denied",
            operation="run.submit",
        )
        is None
    )

    api = ETLanticAPI(
        authorizer=scoped_authz,
        definitions=definitions,
        submissions=submissions,
        durable_work=durable,
        events=events,
        managed_service=service,
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    client = TestClient(create_app(api, with_lifespan=False))
    denied_http = cast(Any, client).post(
        "/v1/definitions/file-pipe/runs",
        headers={
            "X-Principal": "alice",
            "Idempotency-Key": "resource-denied-http",
        },
        json={},
    )
    assert denied_http.status_code == 404
    assert "resource:file-in" in scoped_authz.resources
    assert "resource:file-out" not in scoped_authz.resources
    assert (
        submissions.lookup_idempotency(
            ctx, "resource-denied-http", operation="run.submit"
        )
        is None
    )
    assert (
        durable.get_submission_by_idempotency(
            ctx,
            idempotency_key="resource-denied-http",
            operation="run.submit",
        )
        is None
    )


def test_connector_catalog_is_shared_by_headless_and_http(tmp_path: Path) -> None:
    ctx, authz, definitions, submissions, durable, events, service = _wired(tmp_path)
    expected = service.get_connector_catalog(ctx)
    api = ETLanticAPI(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        events=events,
        durable_work=durable,
        managed_service=service,
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    client = TestClient(create_app(api, with_lifespan=False))

    response = client.get("/v1/connectors", headers={"X-Principal": "alice"})

    assert response.status_code == 200
    assert response.json() == expected
    assert expected["schema"] == "etlantic.connector_catalog/1"
    assert any(
        entry["name"] == "local-files" and entry["kind"] == "source"
        for entry in expected["connectors"]
    )


def test_connector_catalog_authorizes_before_plugin_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, _authz, _definitions, _submissions, _durable, _events, service = _wired(
        tmp_path
    )
    from etlantic.connectors import catalog as connector_catalog

    service.authorizer = MemoryAuthorizer()

    def unexpected_catalog(_profile: Profile) -> dict[str, Any]:
        raise AssertionError("must not discover")

    monkeypatch.setattr(
        connector_catalog,
        "connector_catalog_for_profile",
        unexpected_catalog,
    )

    with pytest.raises(ControlPlaneError) as exc_info:
        service.get_connector_catalog(ctx)

    assert exc_info.value.status == 404


def test_headless_and_http_share_run_actions_and_cancellation(tmp_path) -> None:
    ctx, authz, definitions, submissions, durable, events, service = _wired(tmp_path)
    headless = service.submit_run(ctx, "pipe", idempotency_key="cancel-headless")
    headless_actions = service.get_run_actions(ctx, headless.resource_id)
    assert headless_actions["actions"][:2] == [
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

    def planning_context(
        _ctx: ControlPlaneContext, profile: Profile
    ) -> PlanningContext:
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
    client: Any = cast(Any, TestClient(create_app(api)))
    response: Any = client.post(
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

    def planning_context(
        _ctx: ControlPlaneContext, profile: Profile
    ) -> PlanningContext:
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
    receipt = service.submit_run(
        ctx,
        "file-pipe",
        idempotency_key="file-transfer",
        request=RunRequest(
            metadata={
                "partitions": {
                    "raw": {
                        "subject_id": "raw",
                        "partition_keys": ["id"],
                        "minimum_count": 1,
                    }
                }
            }
        ),
    )
    accepted = _accepted_envelope(durable, ctx, receipt.submission_id)
    RunRequest.from_dict(accepted.effective_request)
    processed = ExecutionHost(
        durable,
        owner_id="worker-test",
        runner=ManagedExecutionAdapter(report_root=report_root),
    ).tick(ctx)

    assert processed == 1
    status = service.get_run_status(ctx, receipt.resource_id)
    assert status["status"] == "completed", status
    report = service.get_run_report(ctx, receipt.resource_id)
    lineage = service.get_run_lineage(ctx, receipt.resource_id)
    assert target.read_text(encoding="utf-8").splitlines() == ["id", "7"]
    assert report["run_id"] == receipt.resource_id
    assert report["status"] == "succeeded"
    assert lineage["submission_id"] == receipt.submission_id
    produced_partition_nodes = [
        node
        for node in lineage["nodes"]
        if node.get("kind") == "partition" and node.get("status") == "produced"
    ]
    assert len(produced_partition_nodes) == 1
    assert produced_partition_nodes[0]["partition_keys"] == ["id"]
    output_node_id = produced_partition_nodes[0]["output_node_id"]
    assert {
        "from": output_node_id,
        "to": produced_partition_nodes[0]["id"],
        "kind": "produced_partition",
    } in lineage["edges"]
    execution = report["metadata"]["etlantic.control_plane.execution"]
    assert lineage["attempt_id"] == execution["attempt_id"]
    attempt_node = next(
        node
        for node in lineage["nodes"]
        if node.get("kind") == "attempt"
        and node.get("attempt_id") == execution["attempt_id"]
    )
    assert attempt_node["role"] == "executed"
    assert {
        "from": receipt.resource_id,
        "to": attempt_node["id"],
        "kind": "has_attempt",
    } in lineage["edges"]
    for step in report["steps"]:
        step_node = next(
            node
            for node in lineage["nodes"]
            if node.get("kind") == "node" and node.get("step_id") == step["step_id"]
        )
        assert {
            "from": attempt_node["id"],
            "to": step_node["id"],
            "kind": "executed_node",
        } in lineage["edges"]
    assert (
        durable.get_effect(ctx, f"{receipt.submission_id}:execution").status
        == "committed"
    )


def test_durable_artifact_content_is_separately_authorized_and_downloadable(
    tmp_path: Path,
) -> None:
    source = tmp_path / "artifact-source.json"
    target = tmp_path / "artifact-target.csv"
    source.write_text('[{"id": 7}]', encoding="utf-8")
    ctx = _ctx()
    authorizer = MemoryAuthorizer()
    for action in (
        "definition.write",
        "definition.validate",
        "definition.plan",
        "run.submit",
        "run.read",
        "run.report",
        "run.artifacts",
    ):
        authorizer.grant(ctx, action)
    definitions = MemoryDefinitionRepository()
    submissions = MemorySubmissionStore()
    durable = MemoryDurableWorkStore()
    events = MemoryEventStore()
    report_root = tmp_path / "reports"
    artifact_root = tmp_path / "artifacts"

    def planning_context(
        _ctx: ControlPlaneContext, profile: Profile
    ) -> PlanningContext:
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
        authorizer=authorizer,
        definitions=definitions,
        submissions=submissions,
        durable_work=durable,
        events=events,
        profile="development",
        report_root=report_root,
        artifact_root=artifact_root,
        planning_context_factory=planning_context,
    )
    service.register_definition(
        ctx,
        "artifact-pipe",
        pipeline_to_dict(definition_from_pipeline(ManagedFilePipeline)),
    )
    receipt = service.submit_run(
        ctx,
        "artifact-pipe",
        idempotency_key="durable-artifact-content",
        request=RunRequest(materialization=MaterializationPolicy.DURABLE),
    )
    assert receipt.resource_id is not None
    assert (
        ExecutionHost(
            durable,
            owner_id="artifact-content-worker",
            runner=ManagedExecutionAdapter(
                report_root=report_root, artifact_root=artifact_root
            ),
        ).tick(ctx)
        == 1
    )
    listed = service.list_run_artifacts(ctx, receipt.resource_id)
    downloadable = next(
        item for item in listed if item["media_type"] == "application/json"
    )
    assert downloadable["content_available"] is True
    artifact_id = str(downloadable["artifact_id"])

    with pytest.raises(ControlPlaneError) as denied:
        service.get_run_artifact_content(ctx, receipt.resource_id, artifact_id)
    assert denied.value.status == 404

    api = ETLanticAPI(
        authorizer=authorizer,
        definitions=definitions,
        submissions=submissions,
        durable_work=durable,
        events=events,
        managed_service=service,
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    client: Any = TestClient(create_app(api))
    denied_http: Any = client.get(
        f"/v1/runs/{receipt.resource_id}/artifacts/content",
        params={"artifact_id": artifact_id},
        headers={"X-Principal": "alice"},
    )
    assert denied_http.status_code == 404

    authorizer.grant(ctx, "run.artifact.content")
    authorizer.forbidden_resources.add(
        (
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            "run.artifact.content",
            f"artifact:{artifact_id}",
        )
    )
    with pytest.raises(ControlPlaneError) as resource_denied:
        service.get_run_artifact_content(ctx, receipt.resource_id, artifact_id)
    assert resource_denied.value.status == 403
    authorizer.forbidden_resources.clear()

    content, media_type = service.get_run_artifact_content(
        ctx, receipt.resource_id, artifact_id
    )
    assert media_type == "application/json"
    assert json.loads(content) == [{"id": 7}]

    restarted_service = ManagedApplicationService(
        authorizer=authorizer,
        definitions=definitions,
        submissions=submissions,
        durable_work=durable,
        events=events,
        report_root=report_root,
        artifact_root=artifact_root,
    )
    restarted_content, _ = restarted_service.get_run_artifact_content(
        ctx, receipt.resource_id, artifact_id
    )
    assert restarted_content == content

    response: Any = client.get(
        f"/v1/runs/{receipt.resource_id}/artifacts/content",
        params={"artifact_id": artifact_id},
        headers={"X-Principal": "alice"},
    )
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("run_timeout", [None, 0.5], ids=["cancel", "timeout"])
def test_managed_worker_stops_real_runtime_without_writing_target(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    run_timeout: float | None,
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
    run_request = (
        RunRequest(timeout=TimeoutPolicy(run_seconds=run_timeout))
        if run_timeout is not None
        else None
    )
    command = "timeout-during-run" if run_timeout is not None else "cancel-during-run"
    receipt = service.submit_run(
        ctx, "cancel-pipe", idempotency_key=command, request=run_request
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
    heartbeat_seen = Event()
    original_heartbeat = durable.heartbeat

    def observe_heartbeat(*args, **kwargs):
        receipt = original_heartbeat(*args, **kwargs)
        heartbeat_seen.set()
        return receipt

    monkeypatch.setattr(durable, "heartbeat", observe_heartbeat)
    worker.start()
    assert started.wait(timeout=10)
    assert heartbeat_seen.wait(timeout=5), "worker did not renew its lease"
    if run_timeout is None:
        durable.cancel_submission(ctx, receipt.submission_id)
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert errors == []
    assert not target.exists()
    expected_durable_status = "failed" if run_timeout is not None else "cancelled"
    expected_report_status = "timed_out" if run_timeout is not None else "cancelled"
    assert durable.get_submission(ctx, receipt.submission_id).status == (
        expected_durable_status
    )
    report = service.get_run_report(ctx, receipt.resource_id)
    assert report["status"] == expected_report_status
    if run_timeout is not None:
        assert any(
            item.get("code") == "PMEXEC408" for item in report.get("diagnostics", [])
        )
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


def test_managed_resume_admits_checkpoint_linked_child_and_is_idempotent(
    tmp_path: Path,
) -> None:
    from etlantic.runtime.managed_errors import ExecutionRejected

    ctx, authz, definitions, submissions, durable, events, service = _wired(tmp_path)
    authz.grant(ctx, "run.resume")
    source = tmp_path / "resume-source.json"
    target = tmp_path / "resume-target.csv"
    source.write_text('[{"id": 42}]', encoding="utf-8")

    def planning_context(
        _ctx: ControlPlaneContext, profile: Profile
    ) -> PlanningContext:
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
        "resume-pipe",
        pipeline_to_dict(definition_from_pipeline(ManagedFilePipeline)),
    )
    parent = service.submit_run(ctx, "resume-pipe", idempotency_key="resume-parent")
    checkpoint_id = "checkpoint:resume-parent"

    def checkpoint_then_fail(
        worker_ctx: ControlPlaneContext,
        *,
        submission: Any,
        submission_id: str,
        attempt_id: str,
        fencing_token: int,
        **_kwargs: Any,
    ) -> None:
        assert submission.submission_id == submission_id
        durable.compare_and_swap_checkpoint(
            worker_ctx,
            checkpoint_id,
            expected_version=None,
            value_fingerprint="sha256:" + "a" * 64,
            attempt_id=attempt_id,
            fencing_token=fencing_token,
        )
        raise ExecutionRejected("simulated worker interruption after checkpoint")

    assert (
        ExecutionHost(
            durable, owner_id="resume-parent-worker", runner=checkpoint_then_fail
        ).tick(ctx)
        == 1
    )
    assert service.get_run_status(ctx, parent.resource_id)["status"] == "failed"
    assert service.get_run_actions(ctx, parent.resource_id)["actions"][-1] == {
        "name": "resume",
        "allowed": True,
        "reason": None,
    }

    resumed = service.resume_run(
        ctx,
        parent.resource_id,
        idempotency_key="resume-child",
        checkpoint_id=checkpoint_id,
    )
    assert (
        service.resume_run(
            ctx,
            parent.resource_id,
            idempotency_key="resume-child",
            checkpoint_id=checkpoint_id,
        ).to_dict()
        == resumed.to_dict()
    )
    child = durable.get_submission(ctx, resumed.submission_id)
    envelope = ExecutionEnvelope.from_json(child.input_snapshot)
    assert child.operation == "run.resume"
    assert envelope.run_request["intent"] == "resume"
    assert envelope.evidence_refs["command"] == "resume"
    assert envelope.evidence_refs["checkpoint_id"] == checkpoint_id
    assert envelope.evidence_refs["parent_run_id"] == parent.resource_id
    assert envelope.evidence_refs["parent_submission_id"] == parent.submission_id
    assert envelope.evidence_refs["artifact_parent_run_id"] == parent.resource_id
    assert len(durable.pending_outbox(ctx)) == 1

    api = ETLanticAPI(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        events=events,
        durable_work=durable,
        managed_service=service,
        profile="development",
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    client: Any = cast(Any, TestClient(create_app(api)))
    response: Any = client.post(
        f"/v1/runs/{parent.resource_id}/resume",
        headers={"X-Principal": "alice", "Idempotency-Key": "resume-child"},
        json={"checkpoint_id": checkpoint_id},
    )
    assert response.status_code == 202
    assert response.json()["submission_id"] == resumed.submission_id
    assert (
        ExecutionHost(
            durable,
            owner_id="resume-child-worker",
            runner=ManagedExecutionAdapter(report_root=tmp_path / "reports"),
        ).tick(ctx)
        == 1
    )
    assert service.get_run_status(ctx, resumed.resource_id)["status"] == "completed"
    assert target.read_text(encoding="utf-8").splitlines() == ["id", "42"]
    assert {
        "from": parent.resource_id,
        "to": resumed.resource_id,
        "kind": "resume",
    } in service.get_run_lineage(ctx, resumed.resource_id)["edges"]
    from etlantic.control_plane.durable_models import EffectRecord

    parent_record = durable.get_submission(ctx, parent.submission_id)
    durable.record_effect(
        ctx,
        EffectRecord(
            effect_id=f"{parent.submission_id}:execution",
            submission_id=parent.submission_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            status="unknown",
            recorded_at=parent_record.created_at,
        ),
    )
    assert service.get_run_actions(ctx, parent.resource_id)["actions"][-1] == {
        "name": "resume",
        "allowed": False,
        "reason": "effect_requires_reconciliation",
    }
    assert (
        service.resume_run(
            ctx,
            parent.resource_id,
            idempotency_key="resume-child",
            checkpoint_id=checkpoint_id,
        ).to_dict()
        == resumed.to_dict()
    )
    with pytest.raises(ControlPlaneError, match="effect is reconciled"):
        service.resume_run(
            ctx,
            parent.resource_id,
            idempotency_key="resume-unsafe",
            checkpoint_id=checkpoint_id,
        )


def test_managed_resume_rejects_unlinked_or_missing_checkpoint(tmp_path: Path) -> None:
    ctx, authz, _definitions, _submissions, durable, _events, service = _wired(tmp_path)
    authz.grant(ctx, "run.resume")
    parent = service.submit_run(ctx, "pipe", idempotency_key="resume-no-checkpoint")
    with pytest.raises(ControlPlaneError, match="failed or cancelled"):
        service.resume_run(
            ctx,
            parent.resource_id,
            idempotency_key="resume-too-early",
            checkpoint_id="checkpoint:missing",
        )
    assert durable.get_submission(ctx, parent.submission_id).status == "accepted"


def test_managed_accept_recovers_lost_cp1_ack_without_duplicate_receipt(
    tmp_path, monkeypatch
) -> None:
    ctx, _authz, _definitions, submissions, durable, _events, service = _wired(tmp_path)
    accept = submissions.accept
    calls = 0

    def accept_then_lose_ack(*args, **kwargs):
        nonlocal calls
        result = accept(*args, **kwargs)
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated lost CP1-accept acknowledgement")
        return result

    monkeypatch.setattr(submissions, "accept", accept_then_lose_ack)

    receipt = service.submit_run(ctx, "pipe", idempotency_key="cp1-lost-ack")

    recovered = submissions.lookup_idempotency(
        ctx, "cp1-lost-ack", operation="run.submit"
    )
    assert recovered is not None
    assert recovered.to_dict() == receipt.to_dict()
    assert calls == 1
    assert len(submissions.poll_accepted(ctx, limit=10)) == 1
    assert len(durable.pending_outbox(ctx)) == 1


def test_managed_accept_preserves_cp1_receipt_when_ack_lookup_is_unavailable(
    tmp_path, monkeypatch
) -> None:
    ctx, _authz, _definitions, submissions, durable, _events, service = _wired(tmp_path)
    accept = submissions.accept
    lookup_payload = submissions.lookup_idempotency_payload
    cp1_committed = False

    def accept_then_lose_ack(*args, **kwargs):
        nonlocal cp1_committed
        accept(*args, **kwargs)
        cp1_committed = True
        raise RuntimeError("simulated lost CP1-accept acknowledgement")

    def fail_payload_lookup(*args, **kwargs):
        if cp1_committed:
            raise RuntimeError("CP1 receipt details are temporarily unavailable")
        return lookup_payload(*args, **kwargs)

    monkeypatch.setattr(submissions, "accept", accept_then_lose_ack)
    monkeypatch.setattr(submissions, "lookup_idempotency_payload", fail_payload_lookup)

    with pytest.raises(ControlPlaneError, match="CP1 acceptance acknowledgement"):
        service.submit_run(ctx, "pipe", idempotency_key="cp1-reconcile-later")

    # Restore reads and retry the exact intent. Existing CP1 acceptance is
    # reconciled into one durable execution/outbox record.
    monkeypatch.setattr(submissions, "accept", accept)
    monkeypatch.setattr(submissions, "lookup_idempotency_payload", lookup_payload)
    recovered = service.submit_run(ctx, "pipe", idempotency_key="cp1-reconcile-later")
    assert (
        submissions.lookup_idempotency(
            ctx, "cp1-reconcile-later", operation="run.submit"
        )
        == recovered
    )
    assert len(submissions.poll_accepted(ctx, limit=10)) == 1
    assert len(durable.pending_outbox(ctx)) == 1


def test_managed_accept_cp1_rejection_creates_no_durable_command(
    tmp_path, monkeypatch
) -> None:
    ctx, _authz, _definitions, submissions, durable, _events, service = _wired(tmp_path)

    def reject_cp1_accept(*_args, **_kwargs):
        raise ControlPlaneError.conflict("CP1 rejected before commit")

    monkeypatch.setattr(submissions, "accept", reject_cp1_accept)

    with pytest.raises(ControlPlaneError, match="CP1 rejected before commit"):
        service.submit_run(ctx, "pipe", idempotency_key="cp1-rejected")

    assert (
        submissions.lookup_idempotency(ctx, "cp1-rejected", operation="run.submit")
        is None
    )
    assert (
        durable.get_submission_by_idempotency(
            ctx, idempotency_key="cp1-rejected", operation="run.submit"
        )
        is None
    )
    assert durable.pending_outbox(ctx) == []


def test_managed_accept_reconciles_commit_when_durable_ack_is_lost(
    tmp_path, monkeypatch
) -> None:
    ctx, _authz, _definitions, _submissions, durable, _events, service = _wired(
        tmp_path
    )
    accept = durable.accept

    def accept_then_lose_ack(*args, **kwargs):
        accept(*args, **kwargs)
        raise RuntimeError("simulated lost durable-accept acknowledgement")

    monkeypatch.setattr(durable, "accept", accept_then_lose_ack)

    receipt = service.submit_run(ctx, "pipe", idempotency_key="managed-lost-ack")

    recovered = durable.get_submission_by_idempotency(
        ctx, idempotency_key="managed-lost-ack", operation="run.submit"
    )
    assert recovered is not None
    assert recovered.submission_id == receipt.submission_id
    assert service.get_run_status(ctx, receipt.resource_id)["status"] == "accepted"
    assert len(durable.pending_outbox(ctx)) == 1
    host = ExecutionHost(
        durable,
        owner_id="lost-ack-recovery-worker",
        runner=ManagedExecutionAdapter(report_root=tmp_path / "reports"),
    )
    assert host.tick(ctx) == 1
    final_status = service.get_run_status(ctx, receipt.resource_id)
    attempts = durable.list_attempts(ctx, receipt.submission_id)
    assert final_status["status"] == "completed", (final_status, attempts)
    assert (
        service.submit_run(ctx, "pipe", idempotency_key="managed-lost-ack") == receipt
    )
    assert host.tick(ctx) == 0
    assert durable.pending_outbox(ctx) == []


def test_managed_accept_keeps_discoverable_receipt_when_reconciliation_is_unavailable(
    tmp_path, monkeypatch
) -> None:
    ctx, _authz, _definitions, submissions, durable, _events, service = _wired(tmp_path)
    accept = durable.accept
    lookup = durable.get_submission_by_idempotency
    committed = False

    def accept_then_lose_ack(*args, **kwargs):
        nonlocal committed
        accept(*args, **kwargs)
        committed = True
        raise RuntimeError("simulated lost durable-accept acknowledgement")

    def fail_reconciliation(*args, **kwargs):
        if committed:
            raise RuntimeError("durable reconciliation store is temporarily offline")
        return lookup(*args, **kwargs)

    monkeypatch.setattr(durable, "accept", accept_then_lose_ack)
    monkeypatch.setattr(durable, "get_submission_by_idempotency", fail_reconciliation)

    with pytest.raises(ControlPlaneError, match="acknowledgement is uncertain") as exc:
        service.submit_run(ctx, "pipe", idempotency_key="managed-reconcile-later")

    assert exc.value.extensions["acceptance_uncertain"] is True
    accepted = submissions.lookup_idempotency(
        ctx, "managed-reconcile-later", operation="run.submit"
    )
    assert accepted is not None
    assert service.get_run_status(ctx, accepted.resource_id)["status"] == "accepted"

    # The caller can retry the exact command after the execution store returns.
    monkeypatch.setattr(durable, "accept", accept)
    monkeypatch.setattr(durable, "get_submission_by_idempotency", lookup)
    recovered = service.submit_run(
        ctx, "pipe", idempotency_key="managed-reconcile-later"
    )
    assert recovered.to_dict() == accepted.to_dict()
    assert len(durable.pending_outbox(ctx)) == 1


def test_managed_accept_compensates_only_a_definite_durable_rejection(
    tmp_path, monkeypatch
) -> None:
    ctx, _authz, _definitions, _submissions, durable, _events, service = _wired(
        tmp_path
    )

    def reject_durable_accept(*_args, **_kwargs):
        raise ControlPlaneError.conflict("durable store rejected the command")

    monkeypatch.setattr(durable, "accept", reject_durable_accept)

    with pytest.raises(ControlPlaneError, match="durable store rejected"):
        service.submit_run(ctx, "pipe", idempotency_key="managed-definite-reject")

    receipt = service.submissions.lookup_idempotency(
        ctx, "managed-definite-reject", operation="run.submit"
    )
    assert receipt is not None
    assert service.get_run_status(ctx, receipt.resource_id)["status"] == (
        "cancel_requested"
    )
    assert (
        durable.get_submission_by_idempotency(
            ctx, idempotency_key="managed-definite-reject", operation="run.submit"
        )
        is None
    )
    assert durable.pending_outbox(ctx) == []


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


def test_managed_http_rejects_forged_plan_hash_and_unknown_revision(
    tmp_path: Path,
) -> None:
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
    client = cast(Any, TestClient(create_app(api)))
    headers = {"X-Principal": "alice", "Idempotency-Key": "forged-plan"}
    forged_plan = client.post(
        "/v1/definitions/pipe/runs",
        headers=headers,
        json={"payload": {"plan_fingerprint": "a" * 64}},
    )
    forged_revision = client.post(
        "/v1/definitions/pipe/runs",
        headers={**headers, "Idempotency-Key": "forged-revision"},
        json={"payload": {"revision_selector": "defrev-unknown"}},
    )

    assert forged_plan.status_code == 400
    assert forged_revision.status_code == 404
    assert durable.pending_outbox(ctx) == []


def test_managed_run_preparation_operations_query_cancel_and_execute(
    tmp_path: Path,
) -> None:
    ctx, authz, definitions, submissions, durable, events, service = _wired(tmp_path)
    api = ETLanticAPI(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        events=events,
        durable_work=durable,
        managed_service=service,
        profile="development",
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    )
    client = cast(Any, TestClient(create_app(api, with_lifespan=False)))
    headers = {"X-Principal": "alice", "Idempotency-Key": "prepare-cancel"}
    body = {"payload": {"request": RunRequest().to_dict()}}
    queued = client.post(
        "/v1/definitions/pipe/preparations", headers=headers, json=body
    )
    assert queued.status_code == 202, queued.text
    operation = queued.json()
    operation_id = operation["operation_id"]
    assert operation["status"] == "queued"
    assert operation["schema"] == "etlantic.control_plane.preparation_operation/1"
    assert (
        client.get(f"/v1/preparations/{operation_id}", headers=headers).json()
        == operation
    )

    repeated = client.post(
        "/v1/definitions/pipe/preparations", headers=headers, json=body
    )
    assert repeated.json()["operation_id"] == operation_id
    secret = client.post(
        "/v1/definitions/pipe/preparations",
        headers={**headers, "Idempotency-Key": "prepare-secret"},
        json={"payload": {"request": {"metadata": {"password": "never-store"}}}},
    )
    assert secret.status_code == 400
    assert "never-store" not in repr(durable.get_action_job(ctx, operation_id))

    cancelled = client.delete(f"/v1/preparations/{operation_id}", headers=headers)
    assert cancelled.status_code == 202, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert not durable.pending_outbox(ctx)

    run_headers = {"X-Principal": "alice", "Idempotency-Key": "prepare-run"}
    accepted = client.post(
        "/v1/definitions/pipe/preparations", headers=run_headers, json=body
    )
    assert accepted.status_code == 202, accepted.text
    run_operation_id = accepted.json()["operation_id"]

    async def execute(action_ctx: ControlPlaneContext, request: Mapping[str, Any]):
        return await asyncio.to_thread(
            service.execute_run_preparation,
            action_ctx,
            str(request["_operation_id"]),
            worker_id=str(request["_worker_id"]),
            fencing_token=int(request["_fencing_token"]),
            request=request,
            is_cancelled=request["_cancel_event"].is_set,
        )

    worker = ActionExecutionHost(
        durable,
        handlers={"run.prepare": execute},
        authorizer=authz,
        worker_id="preparation-worker",
        lease_seconds=10,
    )
    assert worker.tick(ctx) == 1
    completed = client.get(
        f"/v1/preparations/{run_operation_id}", headers=run_headers
    ).json()
    assert completed["status"] == "succeeded"
    assert completed["result"]["submission_id"]
    assert len(durable.pending_outbox(ctx)) == 1

    planning_started = Event()
    release_planning = Event()

    def blocked_planning_context(_context: ControlPlaneContext, _profile: Any) -> Any:
        planning_started.set()
        assert release_planning.wait(timeout=10)
        return None

    service.planning_context_factory = blocked_planning_context
    active = client.post(
        "/v1/definitions/pipe/preparations",
        headers={"X-Principal": "alice", "Idempotency-Key": "prepare-active-cancel"},
        json=body,
    )
    assert active.status_code == 202, active.text
    active_operation_id = active.json()["operation_id"]
    active_worker_results: list[int] = []
    active_worker = Thread(
        target=lambda: active_worker_results.append(worker.tick(ctx))
    )
    active_worker.start()
    assert planning_started.wait(timeout=10)
    cancellation = client.delete(
        f"/v1/preparations/{active_operation_id}", headers=run_headers
    )
    assert cancellation.status_code == 202, cancellation.text
    assert cancellation.json()["status"] == "cancel_requested"
    release_planning.set()
    active_worker.join(timeout=20)
    assert not active_worker.is_alive()
    assert active_worker_results == [1]
    terminal = client.get(
        f"/v1/preparations/{active_operation_id}", headers=run_headers
    )
    assert terminal.json()["status"] == "cancelled"
    assert len(durable.pending_outbox(ctx)) == 1
    assert (
        durable.get_submission_by_idempotency(
            ctx,
            idempotency_key=f"preparation-{active_operation_id}",
            operation="run.submit",
        )
        is None
    )


def test_managed_execution_uses_authority_persisted_at_acceptance(
    tmp_path: Path,
) -> None:
    from collections.abc import Awaitable, Callable
    from dataclasses import replace

    from etlantic.runtime.context import TrustedExecutionScope
    from etlantic.runtime.managed_errors import ExecutionRejected

    ctx, _authz, _definitions, _submissions, durable, _events, service = _wired(
        tmp_path
    )
    accepted_ctx = ControlPlaneContext(
        principal=Principal(
            subject="nightly-pipeline",
            issuer="trusted-scheduler",
            kind="workload",
        ),
        tenant=ctx.tenant,
        workspace=ctx.workspace,
        environment=EnvironmentRef("production"),
        security_domain=SecurityDomain("regulated"),
        resource_owner_id="data-owner",
    )
    receipt = service.submit_run(
        accepted_ctx, "pipe", idempotency_key="accepted-authority"
    )
    submission = durable.get_submission(accepted_ctx, receipt.submission_id)
    assert submission.environment == "production"
    assert submission.security_domain_id == "regulated"
    assert submission.resource_owner_id == "data-owner"

    runtime = PipelineRuntime()
    runtime.ensure_plugins_for_profile(resolve_profile("development"))
    observed_scopes: list[TrustedExecutionScope] = []

    async def capture_scope(
        _context: Any, call_next: Callable[[], Awaitable[Any]]
    ) -> Any:
        scope = runtime.trusted_execution_scope
        assert scope is not None
        observed_scopes.append(scope)
        return await call_next()

    runtime.add_run_middleware(capture_scope, name="capture-accepted-authority")
    worker_ctx = ControlPlaneContext(
        principal=Principal(
            subject="etl-worker",
            issuer="worker-service",
            kind="service",
        ),
        tenant=ctx.tenant,
        workspace=ctx.workspace,
        environment=EnvironmentRef("development"),
        security_domain=SecurityDomain("worker-default"),
        resource_owner_id="worker-owner",
    )
    runner = ManagedExecutionAdapter(
        runtime_factory=lambda: runtime,
        report_root=tmp_path / "reports",
    )
    host = ExecutionHost(
        durable,
        owner_id="managed-worker",
        runner=runner,
    )

    assert host.tick(worker_ctx) == 1
    assert len(observed_scopes) == 1
    scope = observed_scopes[0]
    assert scope.principal_id == "nightly-pipeline"
    assert scope.principal_kind == "workload"
    assert scope.principal_issuer == "trusted-scheduler"
    assert scope.tenant_id == "tenant-a"
    assert scope.workspace_id == "ws-1"
    assert scope.environment == "production"
    assert scope.security_domain_id == "regulated"
    assert scope.resource_owner_id == "data-owner"

    legacy_submission = replace(
        submission,
        environment=None,
        security_domain_id=None,
        resource_owner_id=None,
    )
    with pytest.raises(ExecutionRejected, match="durable execution authority"):
        runner(
            worker_ctx,
            submission=legacy_submission,
            submission_id=submission.submission_id,
            attempt_id="legacy-attempt",
            fencing_token=1,
        )


def test_result_publication_recovery_uses_accepted_scope(tmp_path: Path) -> None:
    from datetime import UTC, datetime
    from hashlib import sha256

    from etlantic.control_plane.durable_models import ResultPublicationRecord
    from etlantic.reports.model import PipelineRunReport
    from etlantic.runtime.request import RunIntent
    from etlantic.runtime.state import RunStatus

    ctx, _authz, _definitions, _submissions, durable, _events, _service = _wired(
        tmp_path
    )
    accepted_ctx = ControlPlaneContext(
        principal=Principal(
            "nightly-pipeline", issuer="trusted-scheduler", kind="workload"
        ),
        tenant=ctx.tenant,
        workspace=ctx.workspace,
        environment=EnvironmentRef("production"),
        security_domain=SecurityDomain("regulated"),
        resource_owner_id="data-owner",
    )
    worker_ctx = ControlPlaneContext(
        principal=Principal("etl-worker", issuer="worker-service", kind="service"),
        tenant=ctx.tenant,
        workspace=ctx.workspace,
        environment=EnvironmentRef("development"),
        security_domain=SecurityDomain("worker-default"),
        resource_owner_id="worker-owner",
    )
    submission, _created = durable.accept(
        accepted_ctx,
        idempotency_key="recovered-publication",
        operation="run.submit",
        plan_fingerprint="a" * 64,
    )
    outbox = durable.pending_outbox(worker_ctx)[0]
    durable.mark_published(worker_ctx, outbox.outbox_id)
    lease = durable.acquire_lease(
        worker_ctx, submission.submission_id, owner_id="crashed-worker", ttl_seconds=30
    )
    attempt = durable.start_attempt(
        worker_ctx,
        submission.submission_id,
        owner_id="crashed-worker",
        fencing_token=lease.fencing_token,
    )
    report = PipelineRunReport(
        pipeline_id="pipe",
        plan_id="plan",
        run_id="accepted-run-id",
        intent=RunIntent.STANDARD,
        profile="development",
        status=RunStatus.SUCCEEDED,
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        plan_fingerprint=submission.plan_fingerprint,
    )
    report_json = report.to_json(indent=None)
    publication = ResultPublicationRecord(
        submission_id=submission.submission_id,
        attempt_id=attempt.attempt_id,
        run_id=report.run_id,
        tenant_id=worker_ctx.tenant.tenant_id,
        workspace_id=worker_ctx.workspace.workspace_id,
        report_json=report_json,
        report_sha256=sha256(report_json.encode("utf-8")).hexdigest(),
        created_at=datetime.now(UTC).isoformat(),
    )
    durable.record_result_publication(
        worker_ctx,
        publication,
        owner_id="crashed-worker",
        fencing_token=lease.fencing_token,
    )
    durable.finish_attempt(
        worker_ctx,
        attempt.attempt_id,
        owner_id="crashed-worker",
        fencing_token=lease.fencing_token,
        status="completed",
    )

    stores: dict[str, dict[str, PipelineRunReport]] = {}
    observed_domains: list[str] = []

    class MemoryReportStore:
        def __init__(self, domain_id: str) -> None:
            self.domain_id = domain_id

        def put(self, value: PipelineRunReport) -> None:
            stores.setdefault(self.domain_id, {})[value.run_id] = value

    def report_store_factory(scope: ControlPlaneContext) -> MemoryReportStore:
        observed_domains.append(scope.security_domain.domain_id)
        return MemoryReportStore(scope.security_domain.domain_id)

    runner = ManagedExecutionAdapter(report_store_factory=report_store_factory)
    host = ExecutionHost(durable, owner_id="recovery-worker", runner=runner)

    assert host.tick(worker_ctx) == 0
    assert observed_domains == ["regulated"]
    assert stores["regulated"][report.run_id].status is RunStatus.SUCCEEDED
    assert not durable.pending_result_publications(worker_ctx)


def test_managed_execution_host_retains_accepted_scope_artifacts(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime, timedelta

    from etlantic.reports.model import ArtifactResult, PipelineRunReport
    from etlantic.runtime.artifacts import artifact_storage_path
    from etlantic.runtime.managed_execution import (
        ManagedExecutionAdapter,
        managed_artifact_workspace,
        managed_report_store,
    )
    from etlantic.runtime.request import RunIntent
    from etlantic.runtime.state import RunStatus

    ctx, _authz, _definitions, _submissions, durable, _events, _service = _wired(
        tmp_path
    )
    accepted_ctx = ControlPlaneContext(
        principal=Principal(
            "nightly-pipeline", issuer="trusted-scheduler", kind="workload"
        ),
        tenant=ctx.tenant,
        workspace=ctx.workspace,
        environment=EnvironmentRef("production"),
        security_domain=SecurityDomain("regulated"),
        resource_owner_id="data-owner",
    )
    worker_ctx = ControlPlaneContext(
        principal=Principal("etl-worker", issuer="worker-service", kind="service"),
        tenant=ctx.tenant,
        workspace=ctx.workspace,
        environment=EnvironmentRef("development"),
        security_domain=SecurityDomain("worker-default"),
        resource_owner_id="worker-owner",
    )
    submission, _created = durable.accept(
        accepted_ctx,
        idempotency_key="retention-scope",
        operation="run.submit",
        plan_fingerprint="b" * 64,
    )
    outbox = durable.pending_outbox(worker_ctx)[0]
    durable.mark_published(worker_ctx, outbox.outbox_id)

    artifact_root = tmp_path / "artifacts"
    report_root = tmp_path / "reports"
    run_id = "accepted-scope-run"
    artifact_identity = "result:private"
    artifact = artifact_storage_path(
        managed_artifact_workspace(accepted_ctx, run_id, artifact_root=artifact_root),
        artifact_identity,
    )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text('[{"id":1}]', encoding="utf-8")
    ended_at = datetime.now(UTC) - timedelta(days=2)
    report = PipelineRunReport(
        pipeline_id="pipe",
        plan_id="plan",
        run_id=run_id,
        intent=RunIntent.STANDARD,
        profile="development",
        status=RunStatus.SUCCEEDED,
        started_at=ended_at - timedelta(minutes=1),
        ended_at=ended_at,
        artifacts=(ArtifactResult(artifact_identity, "result", "durable"),),
        plan_fingerprint=submission.plan_fingerprint,
    )
    managed_report_store(accepted_ctx, report_root=report_root).put(report)

    observed_scopes: list[tuple[str, str, str, str | None]] = []

    def report_store_factory(scope: ControlPlaneContext):
        observed_scopes.append(
            (
                scope.principal.subject,
                scope.environment.name,
                scope.security_domain.domain_id,
                scope.resource_owner_id,
            )
        )
        return managed_report_store(scope, report_root=report_root)

    runner = ManagedExecutionAdapter(
        report_root=report_root,
        artifact_root=artifact_root,
        report_store_factory=report_store_factory,
        run_artifact_retention_seconds=1,
    )
    host = ExecutionHost(durable, owner_id="retention-worker", runner=runner)

    assert host.tick(worker_ctx) == 0
    assert set(observed_scopes) == {
        ("nightly-pipeline", "production", "regulated", "data-owner"),
        ("etl-worker", "development", "worker-default", "worker-owner"),
    }
    assert not artifact.exists()
    retained = managed_report_store(accepted_ctx, report_root=report_root).get(run_id)
    assert retained is not None
    assert retained.artifacts[0].status == "expired"
    assert retained.metadata["etlantic.control_plane.artifact_retention"] == "complete"


def test_managed_rerun_rechecks_admission_and_charges_quota_once(
    tmp_path: Path,
) -> None:
    ctx, authz, _definitions, submissions, durable, _events, service = _wired(tmp_path)
    authz.grant(ctx, "run.rerun")
    policy = MemoryPolicyProvider()
    policy.set_rule("pre_submit", "allow")
    quota = MemoryQuotaProvider()
    service.policy = policy
    service.quotas = quota

    shared_key = "shared-admission-key"
    original = service.submit_run(ctx, "pipe", idempotency_key=shared_key)
    assert original.resource_id is not None
    parent_lease = durable.acquire_lease(
        ctx,
        original.submission_id,
        owner_id="review-parent-worker",
        ttl_seconds=30,
    )
    parent_attempt = durable.start_attempt(
        ctx,
        original.submission_id,
        owner_id="review-parent-worker",
        fencing_token=parent_lease.fencing_token,
    )
    durable.finish_attempt(
        ctx,
        parent_attempt.attempt_id,
        owner_id="review-parent-worker",
        fencing_token=parent_lease.fencing_token,
        status="completed",
    )
    assert quota.get_state(ctx).usage["concurrency"] == 1

    policy.set_rule("pre_submit", "deny")
    with pytest.raises(ControlPlaneError, match="policy denied"):
        service.rerun_run(ctx, original.resource_id, idempotency_key="rerun-denied")
    assert quota.get_state(ctx).usage["concurrency"] == 1
    assert (
        submissions.lookup_idempotency(ctx, "rerun-denied", operation="run.rerun")
        is None
    )

    policy.set_rule("pre_submit", "allow")
    rerun = service.rerun_run(ctx, original.resource_id, idempotency_key=shared_key)
    assert quota.get_state(ctx).usage["concurrency"] == 2
    accepted = durable.get_submission(ctx, rerun.submission_id)
    assert accepted.policy_fingerprint is not None

    policy.set_rule("pre_submit", "deny")
    assert (
        service.rerun_run(
            ctx, original.resource_id, idempotency_key=shared_key
        ).to_dict()
        == rerun.to_dict()
    )
    assert quota.get_state(ctx).usage["concurrency"] == 2


def test_managed_rerun_authorizes_plan_resources_before_acceptance(
    tmp_path: Path,
) -> None:
    ctx, authz, _definitions, submissions, durable, _events, service = _wired(tmp_path)
    authz.grant(ctx, "run.rerun")
    source = tmp_path / "rerun-source.json"
    target = tmp_path / "rerun-target.csv"
    source.write_text('[{"id": 42}]', encoding="utf-8")

    def planning_context(
        _ctx: ControlPlaneContext, profile: Profile
    ) -> PlanningContext:
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
    service.register_definition(
        ctx,
        "rerun-file-pipe",
        pipeline_to_dict(definition_from_pipeline(ManagedFilePipeline)),
    )
    original = service.submit_run(
        ctx, "rerun-file-pipe", idempotency_key="rerun-resource-parent"
    )
    assert original.resource_id is not None
    parent_lease = durable.acquire_lease(
        ctx,
        original.submission_id,
        owner_id="review-parent-worker",
        ttl_seconds=30,
    )
    parent_attempt = durable.start_attempt(
        ctx,
        original.submission_id,
        owner_id="review-parent-worker",
        fencing_token=parent_lease.fencing_token,
    )
    durable.finish_attempt(
        ctx,
        parent_attempt.attempt_id,
        owner_id="review-parent-worker",
        fencing_token=parent_lease.fencing_token,
        status="completed",
    )
    authz.forbidden_resources.add(
        (
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            "run.submit",
            "resource:file-in",
        )
    )

    with pytest.raises(ControlPlaneError):
        service.rerun_run(
            ctx, original.resource_id, idempotency_key="rerun-resource-denied"
        )
    assert (
        submissions.lookup_idempotency(
            ctx, "rerun-resource-denied", operation="run.rerun"
        )
        is None
    )
    assert (
        durable.get_submission_by_idempotency(
            ctx,
            idempotency_key="rerun-resource-denied",
            operation="run.rerun",
        )
        is None
    )
