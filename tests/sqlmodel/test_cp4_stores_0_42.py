# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""SQLModel CP4 governance stores + durable entity dual-write."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event, local
from typing import Any

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy import event

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel.control_plane.cp4_stores import (
    SQLModelAuditEvidenceStore,
    SQLModelPolicyProvider,
    SQLModelQuotaProvider,
    create_cp4_tables,
)
from etlantic_sqlmodel.control_plane.durable_stores import SQLModelDurableWorkStore
from etlantic_sqlmodel.control_plane.models import (
    Cp4GovernanceSnapshotRow,
    DurableOutboxEntityRow,
    DurableSubmissionEntityRow,
)
from etlantic_sqlmodel.control_plane.session import create_sqlite_engine, session_scope
from etlantic_sqlmodel.migrations import apply_migrations
from sqlmodel import select

pytestmark = pytest.mark.sqlmodel


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("alice", issuer="tests"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "ws-1"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def test_audit_list_does_not_bump_payload_version(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    apply_migrations(engine)
    create_cp4_tables(engine)
    store = SQLModelAuditEvidenceStore(engine)
    c = _ctx()
    store.append(c, action="policy.decide", resource="r1")

    def _version() -> int:
        with session_scope(engine) as session:
            row = session.exec(
                select(Cp4GovernanceSnapshotRow).where(
                    Cp4GovernanceSnapshotRow.store_id == "default",
                    Cp4GovernanceSnapshotRow.kind == "audit",
                )
            ).first()
            assert row is not None
            return int(row.payload_version)

    before = _version()
    listed = store.list(c)
    assert listed
    assert store.verify_chain(c)
    exported = store.export(c)
    assert exported.records
    assert _version() == before


def test_policy_sql_round_trip(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'policy.db'}")
    apply_migrations(engine)
    create_cp4_tables(engine)
    store = SQLModelPolicyProvider(engine)
    c = _ctx()
    store.set_rule("pre_submit", "deny", tenant="tenant-a", workspace="ws-1")
    decision = store.decide(c, hook="pre_submit", plan_fingerprint="p1")
    assert decision.effect == "deny"
    again = SQLModelPolicyProvider(engine)
    assert again.decide(c, hook="pre_submit", plan_fingerprint="p1").effect == "deny"


def test_quota_idempotency_survives_store_reopen(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'quota-idempotency.db'}")
    apply_migrations(engine)
    create_cp4_tables(engine)
    ctx = _ctx()
    first = SQLModelQuotaProvider(engine).admit(
        ctx,
        resource="concurrency",
        idempotency_key="scoped-submission-digest",
    )
    repeated = SQLModelQuotaProvider(engine).admit(
        ctx,
        resource="concurrency",
        idempotency_key="scoped-submission-digest",
    )

    assert first == repeated
    assert repeated.used == 1
    assert SQLModelQuotaProvider(engine).get_state(ctx).usage["concurrency"] == 1


def test_quota_snapshot_rejects_stale_compensation_after_new_claim(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'quota-claims-race.db'}")
    apply_migrations(engine)
    create_cp4_tables(engine)
    ctx = _ctx()
    first = SQLModelQuotaProvider(engine).admit(
        ctx, resource="concurrency", idempotency_key="shared", claim_id="rejecting"
    )
    release_key = f"{first.metadata['reservation_key']}:release"
    both_read = Barrier(2)
    compensator_ready = Event()
    claimant_committed = Event()
    thread_state = local()

    class CoordinatedQuota(SQLModelQuotaProvider):
        def _read(self, session: Any, *, for_update: bool) -> tuple[Any, int]:
            snapshot = super()._read(session, for_update=for_update)
            if for_update:
                both_read.wait(timeout=10)
            return snapshot

    def order_updates(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _many: bool,
    ) -> None:
        if (
            not statement.lstrip()
            .upper()
            .startswith("UPDATE CP_CP4_GOVERNANCE_SNAPSHOT")
        ):
            return
        role = getattr(thread_state, "role", None)
        if role == "rejecting":
            compensator_ready.set()
            assert claimant_committed.wait(timeout=10)
        elif role == "accepting":
            assert compensator_ready.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", order_updates)
    try:

        def register():
            thread_state.role = "accepting"
            decision = CoordinatedQuota(engine).admit(
                ctx,
                resource="concurrency",
                idempotency_key="shared",
                claim_id="accepting",
            )
            claimant_committed.set()
            return decision

        def compensate():
            thread_state.role = "rejecting"
            try:
                return CoordinatedQuota(engine).release(
                    ctx,
                    resource="concurrency",
                    idempotency_key=release_key,
                    claim_id="rejecting",
                )
            except ControlPlaneError as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as pool:
            claimant = pool.submit(register)
            rejected = pool.submit(compensate)
            assert claimant.result(timeout=20).effect == "allow"
            assert isinstance(rejected.result(timeout=20), ControlPlaneError)
    finally:
        event.remove(engine, "before_cursor_execute", order_updates)

    reopened = SQLModelQuotaProvider(engine)
    assert reopened.get_state(ctx).usage["concurrency"] == 1
    # The rejected transaction did not commit its abandonment. A retry now
    # removes only its own claim and leaves the accepted claimant charged.
    reopened.release(
        ctx,
        resource="concurrency",
        idempotency_key=release_key,
        claim_id="rejecting",
    )
    assert reopened.get_state(ctx).usage["concurrency"] == 1


def test_durable_accept_dual_writes_entity_rows(tmp_path: Path) -> None:
    """041-P1-01: denormalized entity mirrors exist after accept (snapshot canonical)."""
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'entity.db'}")
    apply_migrations(engine)
    store = SQLModelDurableWorkStore(engine)
    submission, created = store.accept(
        _ctx(),
        idempotency_key="dual-1",
        operation="run.submit",
        plan_fingerprint="plan-dual",
    )
    assert created
    with session_scope(engine) as session:
        subs = list(
            session.exec(
                select(DurableSubmissionEntityRow).where(
                    DurableSubmissionEntityRow.submission_id == submission.submission_id
                )
            ).all()
        )
        outs = list(session.exec(select(DurableOutboxEntityRow)).all())
        assert len(subs) == 1
        assert subs[0].tenant_id == "tenant-a"
        assert outs
        assert outs[0].payload_json
