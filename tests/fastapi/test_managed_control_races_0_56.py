"""Race and legacy-record cases for the managed command service."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any, cast

import pytest

from etlantic import Data, Extract, Load, Pipeline
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_fingerprint, pipeline_to_dict
from etlantic.control_plane import (
    AcceptReceipt,
    ControlPlaneContext,
    EffectRecord,
    EnvironmentRef,
    ExecutionEnvelope,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemoryRegistryProvider,
    MemorySubmissionStore,
    Principal,
    RegistryDefinitionRepository,
    SecurityDomain,
    SubmissionStore,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.runtime.managed_errors import ExecutionRejected
from etlantic.runtime.managed_execution import ManagedExecutionAdapter
from etlantic.service import ManagedApplicationService


class _RerunRows(Data):
    id: int


class _RerunPipeline(Pipeline):
    raw: Extract[_RerunRows] = Extract(asset="rows")
    output: Load[_RerunRows] = Load(input=raw, asset="output")


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="managed-race-user"),
        tenant=TenantRef(tenant_id="managed-race-tenant"),
        workspace=WorkspaceRef(
            tenant_id="managed-race-tenant", workspace_id="managed-race-workspace"
        ),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="managed-race-default"),
    )


def _service(
    authorizer: MemoryAuthorizer,
    submissions: SubmissionStore,
    durable: MemoryDurableWorkStore,
    definitions: MemoryDefinitionRepository | None = None,
) -> ManagedApplicationService:
    return ManagedApplicationService(
        authorizer=authorizer,
        definitions=definitions or MemoryDefinitionRepository(),
        submissions=submissions,
        durable_work=durable,
    )


def _authorized_service(
    submissions: SubmissionStore | None = None,
) -> tuple[
    ControlPlaneContext,
    MemoryAuthorizer,
    MemorySubmissionStore,
    MemoryDurableWorkStore,
    ManagedApplicationService,
]:
    ctx = _context()
    authorizer = MemoryAuthorizer()
    for action in ("run.actions", "run.cancel", "run.retry", "run.submit"):
        authorizer.grant(ctx, action)
    cp1 = MemorySubmissionStore()
    durable = MemoryDurableWorkStore()
    service = _service(authorizer, submissions or cp1, durable)
    return ctx, authorizer, cp1, durable, service


def _accepted_run(
    ctx: ControlPlaneContext,
    submissions: MemorySubmissionStore,
    durable: MemoryDurableWorkStore,
    *,
    idempotency_key: str,
    input_snapshot: str | None = None,
) -> AcceptReceipt:
    accepted = submissions.accept(
        ctx,
        idempotency_key=idempotency_key,
        payload={"definition_id": "legacy-definition"},
        resource_type="run",
        resource_id=f"run-{idempotency_key}",
    )
    receipt = accepted.receipt
    durable.accept(
        ctx,
        idempotency_key=idempotency_key,
        operation="run.submit",
        plan_fingerprint="a" * 64,
        input_snapshot=input_snapshot,
        submission_id=receipt.submission_id,
    )
    return receipt


class _SubmissionStoreWithoutCancellation:
    def __init__(self, store: MemorySubmissionStore) -> None:
        self._store = store

    def __getattr__(self, name: str) -> Any:
        if name == "cancel_run":
            raise AttributeError(name)
        return getattr(self._store, name)


def test_action_discovery_reports_unsupported_cancel_provider() -> None:
    ctx, authorizer, cp1, durable, _service_value = _authorized_service()
    service = _service(
        authorizer,
        cast(SubmissionStore, _SubmissionStoreWithoutCancellation(cp1)),
        durable,
    )
    receipt = _accepted_run(
        ctx, cp1, durable, idempotency_key="provider-without-cancel"
    )
    assert receipt.resource_id is not None

    actions = service.get_run_actions(ctx, receipt.resource_id)

    assert actions["actions"][0] == {
        "name": "cancel",
        "allowed": False,
        "reason": "provider_unsupported",
    }
    with pytest.raises(ControlPlaneError) as error:
        service.cancel_run(ctx, receipt.resource_id)
    assert error.value.status == 501


def test_cancel_returns_durable_completion_after_action_discovery() -> None:
    ctx, _authorizer, cp1, durable, service = _authorized_service()
    receipt = _accepted_run(ctx, cp1, durable, idempotency_key="state-race")
    assert receipt.resource_id is not None

    before = service.get_run_actions(ctx, receipt.resource_id)
    assert before["actions"][0]["allowed"] is True

    lease = durable.acquire_lease(
        ctx, receipt.submission_id, owner_id="race-worker", ttl_seconds=30
    )
    attempt = durable.start_attempt(
        ctx,
        receipt.submission_id,
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

    cancelled = service.cancel_run(ctx, receipt.resource_id)

    assert cancelled["status"] == "completed"
    assert cp1.get_run(ctx, receipt.resource_id)["status"] == "accepted"


def test_cancel_rechecks_authorization_after_action_discovery() -> None:
    ctx, authorizer, cp1, durable, service = _authorized_service()
    receipt = _accepted_run(ctx, cp1, durable, idempotency_key="authz-race")
    assert receipt.resource_id is not None

    before = service.get_run_actions(ctx, receipt.resource_id)
    assert before["actions"][0]["allowed"] is True
    authorizer.forbidden_resources.add(
        (
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            "run.cancel",
            f"run:{receipt.resource_id}",
        )
    )

    with pytest.raises(ControlPlaneError) as error:
        service.cancel_run(ctx, receipt.resource_id)

    assert error.value.status == 403
    assert cp1.get_run(ctx, receipt.resource_id)["status"] == "accepted"
    assert durable.get_submission(ctx, receipt.submission_id).status == "accepted"


def test_legacy_acceptance_without_envelope_cannot_be_replanned_or_executed() -> None:
    ctx, _authorizer, cp1, durable, service = _authorized_service()
    receipt = _accepted_run(ctx, cp1, durable, idempotency_key="legacy-no-envelope")
    assert receipt.resource_id is not None
    lease = durable.acquire_lease(
        ctx, receipt.submission_id, owner_id="legacy-worker", ttl_seconds=30
    )
    attempt = durable.start_attempt(
        ctx,
        receipt.submission_id,
        owner_id=lease.owner_id,
        fencing_token=lease.fencing_token,
    )
    durable.finish_attempt(
        ctx,
        attempt.attempt_id,
        owner_id=lease.owner_id,
        fencing_token=lease.fencing_token,
        status="failed",
    )
    assert service.get_run_actions(ctx, receipt.resource_id)["actions"][1] == {
        "name": "retry",
        "allowed": False,
        "reason": "unverified_execution_envelope",
    }
    before = durable.pending_outbox(ctx)

    with pytest.raises(ControlPlaneError, match="verified execution envelope"):
        service.submit_run(
            ctx,
            "missing-definition-must-not-be-read",
            idempotency_key="legacy-no-envelope",
        )

    assert durable.pending_outbox(ctx) == before
    submission = durable.get_submission(ctx, receipt.submission_id)
    assert submission.input_snapshot is None
    assert submission.plan_fingerprint == "a" * 64
    with pytest.raises(ExecutionRejected, match="no verified execution envelope"):
        ManagedExecutionAdapter()(
            ctx,
            submission=submission,
            submission_id=receipt.submission_id,
            attempt_id="legacy-attempt",
            fencing_token=1,
        )


def test_rerun_accepts_new_command_from_immutable_parent_snapshot() -> None:
    ctx = _context()
    authorizer = MemoryAuthorizer()
    for action in ("definition.write", "run.submit", "run.rerun", "run.actions"):
        authorizer.grant(ctx, action)
    submissions = MemorySubmissionStore()
    durable = MemoryDurableWorkStore()
    definitions = MemoryDefinitionRepository()
    service = _service(authorizer, submissions, durable, definitions)
    definition = definition_from_pipeline(_RerunPipeline)
    service.register_definition(ctx, "rerunnable", pipeline_to_dict(definition))

    parent_receipt = service.submit_run(
        ctx, "rerunnable", idempotency_key="initial-rerun-parent"
    )
    assert parent_receipt.resource_id is not None
    parent_run_id = parent_receipt.resource_id
    assert service.get_run_actions(ctx, parent_run_id)["actions"][2] == {
        "name": "rerun",
        "allowed": False,
        "reason": "non_rerunnable_state",
    }
    parent = durable.get_submission(ctx, parent_receipt.submission_id)
    lease = durable.acquire_lease(
        ctx, parent.submission_id, owner_id="rerun-worker", ttl_seconds=30
    )
    attempt = durable.start_attempt(
        ctx,
        parent.submission_id,
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
    durable.record_effect(
        ctx,
        EffectRecord(
            effect_id=f"{parent.submission_id}:execution",
            submission_id=parent.submission_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            status="committed",
            recorded_at=parent.created_at,
        ),
    )
    assert service.get_run_actions(ctx, parent_run_id)["actions"][2] == {
        "name": "rerun",
        "allowed": True,
        "reason": None,
    }

    rerun = service.rerun_run(ctx, parent_run_id, idempotency_key="explicit-rerun")

    assert (
        service.rerun_run(
            ctx, parent_run_id, idempotency_key="explicit-rerun"
        ).to_dict()
        == rerun.to_dict()
    )
    assert rerun.submission_id != parent.submission_id
    child = durable.get_submission(ctx, rerun.submission_id)
    assert child.plan_fingerprint == parent.plan_fingerprint
    assert child.input_snapshot is not None
    envelope = ExecutionEnvelope.from_json(child.input_snapshot)
    assert envelope.evidence_refs is not None
    assert envelope.evidence_refs["command"] == "rerun"
    assert envelope.evidence_refs["parent_run_id"] == parent_run_id
    assert envelope.evidence_refs["parent_submission_id"] == parent.submission_id


def test_rerun_blocks_unknown_parent_effect() -> None:
    ctx = _context()
    authorizer = MemoryAuthorizer()
    for action in ("definition.write", "run.submit", "run.rerun", "run.actions"):
        authorizer.grant(ctx, action)
    submissions = MemorySubmissionStore()
    durable = MemoryDurableWorkStore()
    definitions = MemoryDefinitionRepository()
    service = _service(authorizer, submissions, durable, definitions)
    definition = definition_from_pipeline(_RerunPipeline)
    service.register_definition(ctx, "rerunnable", pipeline_to_dict(definition))
    parent_receipt = service.submit_run(
        ctx, "rerunnable", idempotency_key="unknown-effect-parent"
    )
    assert parent_receipt.resource_id is not None
    parent_run_id = parent_receipt.resource_id
    parent = durable.get_submission(ctx, parent_receipt.submission_id)
    lease = durable.acquire_lease(
        ctx, parent.submission_id, owner_id="uncertain-worker", ttl_seconds=30
    )
    attempt = durable.start_attempt(
        ctx,
        parent.submission_id,
        owner_id=lease.owner_id,
        fencing_token=lease.fencing_token,
    )
    durable.finish_attempt(
        ctx,
        attempt.attempt_id,
        owner_id=lease.owner_id,
        fencing_token=lease.fencing_token,
        status="failed",
    )
    durable.record_effect(
        ctx,
        EffectRecord(
            effect_id=f"{parent.submission_id}:execution",
            submission_id=parent.submission_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            status="unknown",
            recorded_at=parent.created_at,
        ),
    )
    assert service.get_run_actions(ctx, parent_run_id)["actions"][2] == {
        "name": "rerun",
        "allowed": False,
        "reason": "effect_requires_reconciliation",
    }
    pending_before = durable.pending_outbox(ctx)

    with pytest.raises(ControlPlaneError, match="effect is reconciled") as error:
        service.rerun_run(ctx, parent_run_id, idempotency_key="unsafe-rerun")

    assert error.value.extensions["reason"] == "effect_requires_reconciliation"
    assert durable.pending_outbox(ctx) == pending_before


def test_concurrent_definition_edits_use_repository_compare_and_swap() -> None:
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "definition.write")
    authorizer.grant(ctx, "definition.edit")
    durable = MemoryDurableWorkStore()
    submissions = MemorySubmissionStore()
    barrier = Barrier(2)

    class RacingDefinitions(MemoryDefinitionRepository):
        synchronize_reads = False

        def get(self, ctx: ControlPlaneContext, definition_id: str) -> Any:
            document = super().get(ctx, definition_id)
            if self.synchronize_reads:
                barrier.wait(timeout=10)
            return document

    definitions = RacingDefinitions()
    service = _service(authorizer, submissions, durable, definitions)
    definition = definition_from_pipeline(_RerunPipeline)
    service.register_definition(ctx, "race", pipeline_to_dict(definition))
    fingerprint = pipeline_fingerprint(definition)
    original_nodes = definitions.get(ctx, "race")["nodes"]
    definitions.synchronize_reads = True

    def edit(index: int) -> str:
        node = dict(original_nodes[index])
        node["asset"] = f"edited-{index}"
        try:
            service.edit_definition(
                ctx,
                "race",
                {
                    "op": "update_node",
                    "payload": {"name": node["name"], "node": node},
                },
                expected_fingerprint=fingerprint,
            )
        except ControlPlaneError as exc:
            return f"conflict:{exc.status}"
        return "accepted"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, (0, 1)))

    definitions.synchronize_reads = False
    assert sorted(results) == ["accepted", "conflict:409"]
    final_assets = {
        node["name"]: node.get("asset")
        for node in definitions.get(ctx, "race")["nodes"]
    }
    assert (
        sum(asset in {"edited-0", "edited-1"} for asset in final_assets.values()) == 1
    )


def test_revision_repository_compare_and_swap_rejects_stale_head() -> None:
    ctx = _context()
    definitions = RegistryDefinitionRepository(MemoryRegistryProvider())
    original = {"name": "pipe", "version": 1}
    definitions.put(ctx, "revision-race", original)
    barrier = Barrier(2)

    def edit(version: int) -> str:
        barrier.wait(timeout=10)
        try:
            definitions.compare_and_swap(
                ctx,
                "revision-race",
                original,
                {"name": "pipe", "version": version},
            )
        except ControlPlaneError as exc:
            return f"conflict:{exc.status}"
        return "accepted"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, (2, 3)))

    assert sorted(results) == ["accepted", "conflict:409"]
    assert definitions.get(ctx, "revision-race")["version"] in {2, 3}
