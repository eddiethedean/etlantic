"""Lifecycle acceptance recovers lost acknowledgements without losing inputs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from etlantic import Data, Extract, Load, Pipeline, Profile
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.control_plane import (
    AcceptReceipt,
    ControlPlaneContext,
    ControlPlaneError,
    DurableWorkStore,
    EnvironmentRef,
    ExecutionEnvelope,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemoryEventStore,
    MemoryInputResourceStore,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    SubmissionRecord,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.input_resources import InputResourceReference
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.managed_execution import ManagedExecutionAdapter
from etlantic.service import ManagedApplicationService


class Row(Data):
    id: int


class UploadPipeline(Pipeline):
    source: Extract[Row] = Extract(asset="upload")
    result: Load[Row] = Load(input=source, asset="output")


@dataclass
class Application:
    ctx: ControlPlaneContext
    service: ManagedApplicationService
    durable: DurableWorkStore
    submissions: MemorySubmissionStore
    events: MemoryEventStore
    inputs: MemoryInputResourceStore
    reference: InputResourceReference
    parent: AcceptReceipt
    target: Path


def _application(tmp_path: Path, store_kind: str) -> Application:
    durable: DurableWorkStore = MemoryDurableWorkStore()
    if store_kind == "sqlmodel":
        pytest.importorskip("etlantic_sqlmodel")
        from etlantic_sqlmodel.control_plane import (
            SQLModelDurableWorkStore,
            create_sqlite_engine,
        )
        from etlantic_sqlmodel.migrations import apply_migrations

        engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'durable.db'}")
        apply_migrations(engine)
        durable = cast(DurableWorkStore, SQLModelDurableWorkStore(engine))
    ctx = ControlPlaneContext(
        principal=Principal("alice"),
        tenant=TenantRef("tenant"),
        workspace=WorkspaceRef("tenant", "workspace"),
        environment=EnvironmentRef("development"),
        security_domain=SecurityDomain("default"),
    )
    authz = MemoryAuthorizer()
    for action in (
        "definition.write",
        "run.submit",
        "run.read",
        "input.read",
        "run.retry",
        "run.rerun",
        "run.replay",
        "run.resume",
        "run.repair",
        "run.backfill",
    ):
        authz.grant(ctx, action)
    inputs = MemoryInputResourceStore()
    content = b"id\n7\n"
    staged = inputs.stage(
        ctx,
        content,
        media_type="text/csv",
        format="csv",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    reference = inputs.finalize(
        ctx,
        staged.upload_id,
        expected_sha256=hashlib.sha256(content).hexdigest(),
        expected_byte_length=len(content),
    )
    target = tmp_path / "target.csv"

    def planning(_ctx: ControlPlaneContext, profile: Profile) -> PlanningContext:
        context = PlanningContext.create(profile=profile)
        context.registry.register_binding(
            BindingDescriptor(
                binding="upload",
                provider="local-files",
                kind="source",
                config={"input_resource": reference.to_dict()},
            )
        )
        context.registry.register_binding(
            BindingDescriptor(
                binding="output", provider="csv", kind="sink", location=str(target)
            )
        )
        return context

    submissions, events = MemorySubmissionStore(), MemoryEventStore()
    service = ManagedApplicationService(
        authorizer=authz,
        definitions=MemoryDefinitionRepository(),
        submissions=submissions,
        durable_work=durable,
        input_resources=inputs,
        events=events,
        planning_context_factory=planning,
        profile="development",
        report_root=tmp_path / "reports",
    )
    service.register_definition(
        ctx, "upload", pipeline_to_dict(definition_from_pipeline(UploadPipeline))
    )
    parent = service.submit_run(ctx, "upload", idempotency_key="parent")
    lease = durable.acquire_lease(
        ctx, parent.submission_id, owner_id="parent-worker", ttl_seconds=60
    )
    attempt = durable.start_attempt(
        ctx,
        parent.submission_id,
        owner_id="parent-worker",
        fencing_token=lease.fencing_token,
    )
    durable.compare_and_swap_checkpoint(
        ctx,
        "checkpoint:parent",
        expected_version=None,
        value_fingerprint="sha256:" + "a" * 64,
        attempt_id=attempt.attempt_id,
        fencing_token=lease.fencing_token,
    )
    durable.finish_attempt(
        ctx,
        attempt.attempt_id,
        owner_id="parent-worker",
        fencing_token=lease.fencing_token,
        status="failed",
    )
    durable.reconcile_terminal_outbox(ctx)
    return Application(
        ctx, service, durable, submissions, events, inputs, reference, parent, target
    )


def _command(app: Application, command: str, key: str) -> AcceptReceipt:
    run_id = app.parent.resource_id
    assert run_id is not None
    if command == "retry":
        return app.service.retry_run(app.ctx, run_id, idempotency_key=key)
    if command == "rerun":
        return app.service.rerun_run(app.ctx, run_id, idempotency_key=key)
    if command == "replay":
        return app.service.replay_run(app.ctx, run_id, idempotency_key=key)
    if command == "resume":
        return app.service.resume_run(
            app.ctx, run_id, idempotency_key=key, checkpoint_id="checkpoint:parent"
        )
    if command == "repair":
        return app.service.repair_run(
            app.ctx,
            run_id,
            idempotency_key=key,
            invalidated_partition_ids={"source": ["a"], "result": ["a"]},
        )
    return app.service.backfill_run(
        app.ctx,
        run_id,
        idempotency_key=key,
        partition_ids={"source": ["a"], "result": ["a"]},
    )


def _child_lease(app: Application, key: str, operation: str) -> str:
    payload = app.submissions.lookup_idempotency_payload(
        app.ctx, key, operation=operation
    )
    assert payload is not None
    envelope = ExecutionEnvelope.from_json(str(payload["execution_envelope"]))
    lease_id = (envelope.evidence_refs or {}).get("input_resource_lease_id")
    assert isinstance(lease_id, str)
    return lease_id


@pytest.mark.parametrize(
    "store_kind", ["memory", pytest.param("sqlmodel", marks=pytest.mark.sqlmodel)]
)
@pytest.mark.parametrize(
    "command", ["retry", "rerun", "replay", "resume", "repair", "backfill"]
)
@pytest.mark.parametrize(
    "failure",
    [
        "before",
        "after",
        "server_before",
        "server_after",
        "rejected",
        "rejected_after",
        "lookup_before",
        "lookup_after",
        "rejected_lookup",
    ],
)
def test_lifecycle_acceptance_reconciles_without_cancelling_committed_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    store_kind: str,
    command: str,
    failure: str,
) -> None:
    app = _application(tmp_path, store_kind)

    # Partition connector qualification has its own integration suite. These
    # cases isolate the shared acceptance boundary using a qualified-provider
    # response; all immutable input leases and durable writes remain real.
    def qualified_provider(
        _self: ManagedApplicationService, _snapshot: str, *, operation: str
    ) -> str | None:
        return None

    monkeypatch.setattr(
        ManagedApplicationService, "_partition_action_block_reason", qualified_provider
    )
    operation, key = f"run.{command}", f"child-{failure}"
    accept = app.durable.accept
    lookup = app.durable.get_submission_by_idempotency
    issued = False

    def fail_accept(*args: Any, **kwargs: Any) -> tuple[SubmissionRecord, bool]:
        nonlocal issued
        issued = True
        if failure in {"after", "server_after", "lookup_after", "rejected_after"}:
            accept(*args, **kwargs)
        if failure.startswith("rejected"):
            raise ControlPlaneError.conflict("durable admission rejected")
        if failure.startswith("server"):
            raise ControlPlaneError("provider unavailable", code="TEST503", status=503)
        raise RuntimeError("lost durable acknowledgement")

    def fail_lookup(*args: Any, **kwargs: Any) -> SubmissionRecord | None:
        if issued and failure in {"lookup_before", "lookup_after", "rejected_lookup"}:
            raise RuntimeError("reconciliation temporarily unavailable")
        return lookup(*args, **kwargs)

    monkeypatch.setattr(app.durable, "accept", fail_accept)
    monkeypatch.setattr(app.durable, "get_submission_by_idempotency", fail_lookup)
    committed = failure in {"after", "server_after", "lookup_after", "rejected_after"}
    recovered = failure in {"after", "server_after", "rejected_after"}
    if recovered:
        returned = _command(app, command, key)
    else:
        with pytest.raises(ControlPlaneError) as error:
            _command(app, command, key)
        assert error.value.status == (409 if failure == "rejected" else 503)
        if failure != "rejected":
            assert error.value.code == "PMCP503"
            assert error.value.extensions["acceptance_uncertain"] is True
            assert error.value.extensions["compensated"] is False
        returned = None
    receipt = app.submissions.lookup_idempotency(app.ctx, key, operation=operation)
    assert receipt is not None and receipt.resource_id is not None
    cp1 = app.submissions.get_run(app.ctx, receipt.resource_id)
    assert cp1["status"] == (
        "cancel_requested" if failure == "rejected" else "accepted"
    )
    child = lookup(app.ctx, idempotency_key=key, operation=operation)
    assert (child is not None) is committed
    assert len(app.durable.pending_outbox(app.ctx)) == int(committed)
    accepted_events = [
        event
        for event in app.events.list_after_cursor(app.ctx, None)
        if event.kind == f"{operation}.accepted"
    ]
    assert len(accepted_events) == int(recovered)
    lease_id = _child_lease(app, key, operation)
    if failure == "rejected":
        with pytest.raises(ControlPlaneError):
            app.inputs.read_leased(app.ctx, app.reference, lease_id=lease_id)
        return
    assert (
        app.inputs.read_leased(app.ctx, app.reference, lease_id=lease_id) == b"id\n7\n"
    )
    monkeypatch.setattr(app.durable, "get_submission_by_idempotency", lookup)
    if not committed:
        with pytest.raises(ControlPlaneError) as replay_error:
            _command(app, command, key)
        assert replay_error.value.status == (
            409 if failure == "rejected_lookup" else 503
        )
        assert (
            app.submissions.get_run(app.ctx, receipt.resource_id)["status"]
            == "accepted"
        )
        assert (
            app.inputs.read_leased(app.ctx, app.reference, lease_id=lease_id)
            == b"id\n7\n"
        )

        def commit_then_lose_ack(
            *args: Any, **kwargs: Any
        ) -> tuple[SubmissionRecord, bool]:
            accept(*args, **kwargs)
            raise RuntimeError(
                "lost acknowledgement while reconciling CP1-only receipt"
            )

        monkeypatch.setattr(app.durable, "accept", commit_then_lose_ack)
    else:
        monkeypatch.setattr(app.durable, "accept", accept)
    retry = _command(app, command, key)
    assert retry == receipt
    if returned is not None:
        assert returned == receipt
    assert len(app.durable.pending_outbox(app.ctx)) == 1
    assert _child_lease(app, key, operation) == lease_id
    # A reconciled receipt remains idempotent even if acceptance is unavailable
    # again; returning it requires the already committed durable child.
    monkeypatch.setattr(app.durable, "accept", fail_accept)
    assert _command(app, command, key) == receipt
    if command not in {"repair", "backfill"}:
        host = ExecutionHost(
            app.durable,
            owner_id="child-worker",
            runner=ManagedExecutionAdapter(
                report_root=tmp_path / "reports", input_resource_store=app.inputs
            ),
        )
        assert host.tick(app.ctx) == 1
        assert (
            app.service.get_run_status(app.ctx, receipt.resource_id)["status"]
            == "completed"
        )
        assert app.target.read_text().splitlines() == ["id", "7"]
        assert host.tick(app.ctx) == 0


@pytest.mark.parametrize(
    "field", ["submission_id", "run_id", "operation", "input_snapshot"]
)
def test_lifecycle_acceptance_rejects_conflicting_reconciliation_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    app = _application(tmp_path, "memory")
    accept, lookup = app.durable.accept, app.durable.get_submission_by_idempotency
    committed = False

    def lose_ack(*args: Any, **kwargs: Any) -> tuple[SubmissionRecord, bool]:
        nonlocal committed
        accept(*args, **kwargs)
        committed = True
        raise RuntimeError("lost durable acknowledgement")

    def conflicting_lookup(*args: Any, **kwargs: Any) -> SubmissionRecord | None:
        row = lookup(*args, **kwargs)
        if row is None or not committed:
            return row
        return replace(row, **{field: "mismatched-receipt"})

    monkeypatch.setattr(app.durable, "accept", lose_ack)
    monkeypatch.setattr(
        app.durable, "get_submission_by_idempotency", conflicting_lookup
    )
    with pytest.raises(
        ControlPlaneError, match="conflicts with the CP1 receipt"
    ) as error:
        _command(app, "rerun", "conflicting-child")
    assert error.value.status == 409
    receipt = app.submissions.lookup_idempotency(
        app.ctx, "conflicting-child", operation="run.rerun"
    )
    assert receipt is not None and receipt.resource_id is not None
    assert app.submissions.get_run(app.ctx, receipt.resource_id)["status"] == "accepted"
    assert len(app.durable.pending_outbox(app.ctx)) == 1
    lease_id = _child_lease(app, "conflicting-child", "run.rerun")
    assert (
        app.inputs.read_leased(app.ctx, app.reference, lease_id=lease_id) == b"id\n7\n"
    )
    assert not [
        event
        for event in app.events.list_after_cursor(app.ctx, None)
        if event.kind == "run.rerun.accepted"
    ]
    monkeypatch.setattr(app.durable, "accept", accept)
    monkeypatch.setattr(app.durable, "get_submission_by_idempotency", lookup)
    assert _command(app, "rerun", "conflicting-child") == receipt
