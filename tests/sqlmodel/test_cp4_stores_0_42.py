"""SQLModel CP4 governance stores + durable entity dual-write."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_sqlmodel.control_plane.cp4_stores import (
    SQLModelAuditEvidenceStore,
    SQLModelPolicyProvider,
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
