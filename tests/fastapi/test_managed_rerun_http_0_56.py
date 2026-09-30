"""HTTP adapter coverage for the explicit managed rerun command."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from etlantic import Data, Extract, Load, Pipeline
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
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
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.managed_execution import ManagedExecutionAdapter
from etlantic.runtime.request import RunIntent, RunRequest
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)


class _HTTPRows(Data):
    id: int


class _HTTPRerunPipeline(Pipeline):
    raw: Extract[_HTTPRows] = Extract(asset="rows")
    output: Load[_HTTPRows] = Load(input=raw, asset="output")


def test_managed_http_rerun_and_replay_execute_accepted_child(tmp_path: Path) -> None:
    source = tmp_path / "replay-source.json"
    target = tmp_path / "replay-target.csv"
    source.write_text('[{"id": 31}]', encoding="utf-8")

    ctx = ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )
    authorizer = MemoryAuthorizer()
    for action in (
        "definition.write",
        "run.submit",
        "run.actions",
        "run.rerun",
        "run.replay",
    ):
        authorizer.grant(ctx, action)
    definitions = MemoryDefinitionRepository()
    submissions = MemorySubmissionStore()
    durable = MemoryDurableWorkStore()

    def planning_context(
        _ctx: ControlPlaneContext, profile: Any
    ) -> PlanningContext:
        planning = PlanningContext.create(profile=profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="rows",
                provider="json",
                location=str(source),
                kind="source",
            )
        )
        planning.registry.register_binding(
            BindingDescriptor(
                binding="output",
                provider="csv",
                location=str(target),
                kind="sink",
            )
        )
        return planning

    api = ETLanticAPI(
        authorizer=authorizer,
        definitions=definitions,
        submissions=submissions,
        events=MemoryEventStore(),
        durable_work=durable,
        profile="development",
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
        planning_context_factory=planning_context,
    ).enable_managed_execution()
    service = api.managed_service
    assert service is not None
    service.register_definition(
        ctx,
        "rerunnable",
        pipeline_to_dict(definition_from_pipeline(_HTTPRerunPipeline)),
    )
    parent = service.submit_run(
        ctx, "rerunnable", idempotency_key="http-rerun-parent"
    )
    assert parent.resource_id is not None
    accepted = durable.get_submission(ctx, parent.submission_id)
    lease = durable.acquire_lease(
        ctx, accepted.submission_id, owner_id="http-rerun-worker", ttl_seconds=30
    )
    attempt = durable.start_attempt(
        ctx,
        accepted.submission_id,
        owner_id=lease.owner_id,
        fencing_token=lease.fencing_token,
    )
    durable.finish_attempt(
        ctx,
        attempt.attempt_id,
        owner_id=lease.owner_id,
        fencing_token=lease.fencing_token,
        status="completed",
    )

    headers = {"X-Principal": "alice", "Idempotency-Key": "http-rerun-child"}
    replay_headers = {
        "X-Principal": "alice",
        "Idempotency-Key": "http-replay-child",
    }
    with TestClient(create_app(api)) as client:
        http_client = cast(Any, client)
        actions = service.get_run_actions(ctx, parent.resource_id)
        response = http_client.post(
            f"/v1/runs/{parent.resource_id}/rerun", headers=headers
        )
        repeat = http_client.post(
            f"/v1/runs/{parent.resource_id}/rerun", headers=headers
        )
        replay = http_client.post(
            f"/v1/runs/{parent.resource_id}/replay", headers=replay_headers
        )
        replay_repeat = http_client.post(
            f"/v1/runs/{parent.resource_id}/replay", headers=replay_headers
        )
        schema = http_client.get("/openapi.json")

    assert response.status_code == 202
    assert repeat.status_code == 202
    assert response.json()["submission_id"] == repeat.json()["submission_id"]
    assert actions["actions"][3] == {
        "name": "replay",
        "allowed": True,
        "reason": None,
    }
    assert replay.status_code == 202
    assert replay_repeat.status_code == 202
    assert replay.json()["submission_id"] == replay_repeat.json()["submission_id"]
    replay_record = durable.get_submission(ctx, replay.json()["submission_id"])
    assert replay_record.input_snapshot is not None
    replay_envelope = ExecutionEnvelope.from_json(replay_record.input_snapshot)
    assert RunRequest.from_dict(replay_envelope.run_request).intent is RunIntent.REPLAY
    assert replay_envelope.evidence_refs is not None
    assert replay_envelope.evidence_refs["parent_run_id"] == parent.resource_id
    assert "/v1/runs/{run_id}/rerun" in schema.json()["paths"]
    assert "/v1/runs/{run_id}/replay" in schema.json()["paths"]

    rerun_id = response.json()["submission_id"]
    replay_id = replay.json()["submission_id"]
    processed = ExecutionHost(
        durable,
        owner_id="managed-replay-worker",
        runner=ManagedExecutionAdapter(report_root=tmp_path / "reports"),
    ).tick(ctx)

    assert processed == 2
    assert durable.get_submission(ctx, rerun_id).status == "completed"
    assert durable.get_submission(ctx, replay_id).status == "completed"
    assert target.read_text(encoding="utf-8").splitlines() == ["id", "31"]
