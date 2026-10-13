"""SQLModel persistence for canceled, uncertain Prefect dispatch recovery."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy import create_engine

from etlantic.control_plane import (
    ControlPlaneContext,
    DispatchRecord,
    EnvironmentRef,
    MemoryDurableWorkStore,
    OutboxRecord,
    Principal,
    SecurityDomain,
    SubmissionRecord,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel.control_plane import (
    SQLModelDurableWorkStore,
    create_durable_tables,
)
from sqlmodel import Session

pytestmark = pytest.mark.sqlmodel


def test_sqlmodel_recovers_canceled_uncertain_dispatch_before_route_drain() -> None:
    engine = create_engine("sqlite://")
    create_durable_tables(engine)
    store = SQLModelDurableWorkStore(engine, store_id="canceled-uncertain-058")
    ctx = ControlPlaneContext(
        principal=Principal(subject="cancel-operator", issuer="tests"),
        tenant=TenantRef("cancel-tenant"),
        workspace=WorkspaceRef("cancel-tenant", "cancel-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("internal"),
    )
    submission_id = "sub-canceled-uncertain"
    route = "prefect:" + "a" * 64
    timestamp = "2026-10-12T12:00:00Z"

    def seed(memory: MemoryDurableWorkStore) -> None:
        key = (*ctx.scope_key, submission_id)
        memory._submissions[key] = SubmissionRecord(
            submission_id=submission_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            principal_subject=ctx.principal.subject,
            principal_issuer=ctx.principal.issuer,
            operation="run.submit",
            idempotency_key="cancel-uncertain-key",
            created_at=timestamp,
            plan_fingerprint="b" * 64,
            status="accepted",
            execution_route=route,
        )
        memory._outbox[(*ctx.scope_key, "outbox-canceled-uncertain")] = OutboxRecord(
            outbox_id="outbox-canceled-uncertain",
            submission_id=submission_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            created_at=timestamp,
            payload_fingerprint="c" * 64,
        )
        memory._dispatches[key] = DispatchRecord(
            submission_id=submission_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            execution_route=route,
            binding_fingerprint=route.removeprefix("prefect:"),
            plan_fingerprint="b" * 64,
            envelope_sha256="e" * 64,
            generation=1,
            creation_key="etlantic-canceled-uncertain",
            created_at=timestamp,
            updated_at=timestamp,
            status="uncertain",
            last_error_code="prefect_create_uncertain",
        )

    with Session(engine) as session:
        store.apply_in_transaction(session, seed)
        session.commit()

    try:
        store.cancel_submission(ctx, submission_id)
        assert store.reconcile_cancelled_submissions(ctx, limit=10) == []
        assert store.get_submission(ctx, submission_id).status == "cancel_requested"
        assert [
            row.submission_id
            for row in store.pending_dispatches(ctx, execution_route=route)
        ] == [submission_id]

        claim = store.claim_dispatch(ctx, submission_id, owner_id="cancel-recovery")
        assert claim is not None
        store.link_dispatch(
            ctx,
            submission_id,
            owner_id="cancel-recovery",
            fencing_token=claim.lease_fencing_token,
            prefect_flow_run_id="prefect-run-found-by-idempotency-key",
        )
        assert [
            row.submission_id
            for row in store.reconcile_cancelled_submissions(ctx, limit=10)
        ] == [submission_id]
        assert store.get_submission(ctx, submission_id).status == "cancelled"
        assert store.execution_route_workload(ctx, route).drained
    finally:
        engine.dispose()
