# pyright: reportMissingImports=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""SQLModel CP3 durable work store, migrations, and conformance (0.41 / 041-P)."""

from __future__ import annotations

import json
from pathlib import Path
from time import sleep
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")
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
from etlantic.testing import run_durable_work_conformance_suite
from etlantic_sqlmodel.control_plane import (
    SQLModelDurableWorkStore,
    create_sqlite_engine,
)
from etlantic_sqlmodel.control_plane.models import DurableSnapshotRow
from etlantic_sqlmodel.migrations import (
    apply_migrations,
    current_version,
    downgrade,
    upgrade,
)
from sqlmodel import Session

pytestmark = pytest.mark.sqlmodel


def _ctx(
    tenant: str = "tenant-a", workspace: str = "workspace-a"
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("worker-a", issuer="tests"),
        tenant=TenantRef(tenant),
        workspace=WorkspaceRef(tenant, workspace),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def test_migration_includes_durable_cp3(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'd.db'}")
    assert apply_migrations(engine) == "014_cp1_complete_principal_idempotency_0_56"
    assert current_version(engine) == "014_cp1_complete_principal_idempotency_0_56"


def test_scope_backfill_migration_restores_legacy_snapshot_submissions(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'legacy-snapshot.db'}")
    upgrade(engine, target="002_durable_cp3")
    submission: dict[str, object] = {
        "submission_id": "legacy-submission",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "principal_subject": "legacy-scheduler",
        "principal_issuer": "tests",
        "principal_kind": "workload",
        "operation": "run.submit",
        "idempotency_key": "legacy-idempotency",
        "created_at": "2026-01-01T00:00:00Z",
        "plan_fingerprint": "plan",
        "status": "completed",
        "metadata": {},
        "environment": "production",
        "security_domain_id": "regulated",
        "resource_owner_id": "owner-a",
    }
    with Session(engine) as session:
        session.add(
            DurableSnapshotRow(
                store_id="default",
                payload_json=json.dumps(
                    {
                        "submissions": {
                            '["tenant-a","workspace-a","legacy-submission"]': submission
                        }
                    }
                ),
                payload_version=1,
            )
        )
        session.commit()

    assert upgrade(engine) == "014_cp1_complete_principal_idempotency_0_56"
    assert (
        downgrade(engine, target="012_bounded_event_tombstone_retention_0_56")
        == "012_bounded_event_tombstone_retention_0_56"
    )
    assert upgrade(engine) == "014_cp1_complete_principal_idempotency_0_56"
    page = SQLModelDurableWorkStore(engine).list_execution_scopes(_ctx())

    assert page.next_cursor is None
    assert len(page.scopes) == 1
    assert page.scopes[0].principal == Principal(
        "legacy-scheduler", issuer="tests", kind="workload"
    )
    assert page.scopes[0].security_domain == SecurityDomain("regulated")
    assert page.scopes[0].resource_owner_id == "owner-a"


def test_sqlmodel_durable_conformance(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'c.db'}")
    apply_migrations(engine)
    run_durable_work_conformance_suite(SQLModelDurableWorkStore(engine))


def test_sqlmodel_snapshot_preserves_accepted_execution_authority(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'authority.db'}")
    apply_migrations(engine)
    store = SQLModelDurableWorkStore(engine)
    base = _ctx()
    accepted_ctx = ControlPlaneContext(
        principal=Principal(
            "nightly-pipeline", issuer="trusted-scheduler", kind="workload"
        ),
        tenant=base.tenant,
        workspace=base.workspace,
        environment=EnvironmentRef("production"),
        security_domain=SecurityDomain("regulated"),
        resource_owner_id="data-owner",
    )
    accepted, created = store.accept(
        accepted_ctx,
        idempotency_key="authority",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    assert created

    restarted = SQLModelDurableWorkStore(engine)
    restored = restarted.get_submission(accepted_ctx, accepted.submission_id)
    assert restored.principal_subject == "nightly-pipeline"
    assert restored.principal_issuer == "trusted-scheduler"
    assert restored.principal_kind == "workload"
    assert restored.environment == "production"
    assert restored.security_domain_id == "regulated"
    assert restored.resource_owner_id == "data-owner"
    scopes = restarted.list_execution_scopes(accepted_ctx).scopes
    assert len(scopes) == 1
    assert scopes[0].principal == accepted_ctx.principal
    assert scopes[0].environment == accepted_ctx.environment
    assert scopes[0].security_domain == accepted_ctx.security_domain
    assert scopes[0].resource_owner_id == accepted_ctx.resource_owner_id


def test_sqlmodel_execution_scope_pages_bypass_snapshot_load(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'scope-pages.db'}")
    apply_migrations(engine)
    store = SQLModelDurableWorkStore(engine)
    base = _ctx()
    for suffix in ("a", "b", "c"):
        accepted_ctx = ControlPlaneContext(
            principal=Principal(f"pipeline-{suffix}", issuer="scheduler"),
            tenant=base.tenant,
            workspace=base.workspace,
            environment=EnvironmentRef("production"),
            security_domain=SecurityDomain("regulated"),
        )
        store.accept(
            accepted_ctx,
            idempotency_key=f"scope-{suffix}",
            operation="run.submit",
            plan_fingerprint="plan",
            submission_id=f"submission-{suffix}",
        )

    statements: list[str] = []

    def record_statement(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", record_statement)
    first = store.list_execution_scopes(base, limit=2)
    second = store.list_execution_scopes(
        base,
        after_submission_id=first.next_cursor,
        through_submission_id=first.high_watermark,
        limit=2,
    )
    event.remove(engine, "before_cursor_execute", record_statement)

    assert [scope.principal.subject for scope in first.scopes] == [
        "pipeline-a",
        "pipeline-b",
    ]
    assert first.next_cursor == "submission-b"
    assert first.high_watermark == "submission-c"
    assert [scope.principal.subject for scope in second.scopes] == ["pipeline-c"]
    assert second.next_cursor is None
    assert all("cp_durable_snapshot" not in statement for statement in statements)


def test_outbox_crash_point_and_duplicate_publish(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'o.db'}")
    apply_migrations(engine)
    store = SQLModelDurableWorkStore(engine)
    submission, created = store.accept(
        _ctx(),
        idempotency_key="out",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    assert created
    pending = store.pending_outbox(_ctx())
    assert len(pending) == 1 and pending[0].published_at is None
    first = store.mark_published(_ctx(), pending[0].outbox_id)
    second = store.mark_published(_ctx(), pending[0].outbox_id)
    assert first.published_at and second.delivery_count == first.delivery_count
    assert not store.pending_outbox(_ctx())
    # second store instance sees committed state (survives "API restart")
    revived = SQLModelDurableWorkStore(engine)
    again, created_again = revived.accept(
        _ctx(),
        idempotency_key="out",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    assert not created_again and again.submission_id == submission.submission_id


def test_dual_host_lease_fencing(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'l.db'}")
    apply_migrations(engine)
    host1 = SQLModelDurableWorkStore(engine)
    host2 = SQLModelDurableWorkStore(engine)
    submission, _ = host1.accept(
        _ctx(),
        idempotency_key="lease",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    lease1 = host1.acquire_lease(
        _ctx(), submission.submission_id, owner_id="one", ttl_seconds=60
    )
    with pytest.raises(ControlPlaneError, match="leased"):
        host2.acquire_lease(
            _ctx(), submission.submission_id, owner_id="two", ttl_seconds=60
        )
    # expire lease via host1 release then host2 acquires with new token
    host1.release_lease(
        _ctx(),
        submission.submission_id,
        owner_id="one",
        fencing_token=lease1.fencing_token,
    )
    lease2 = host2.acquire_lease(
        _ctx(), submission.submission_id, owner_id="two", ttl_seconds=60
    )
    assert lease2.fencing_token > lease1.fencing_token
    with pytest.raises(ControlPlaneError, match="Stale"):
        host1.heartbeat(
            _ctx(),
            submission.submission_id,
            owner_id="one",
            fencing_token=lease1.fencing_token,
            ttl_seconds=30,
        )


def test_snapshot_version_conflict_under_concurrent_hosts(tmp_path: Path) -> None:
    from etlantic_sqlmodel.control_plane.models import DurableSnapshotRow
    from etlantic_sqlmodel.control_plane.session import session_scope
    from sqlmodel import select

    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'race.db'}")
    apply_migrations(engine)
    host1 = SQLModelDurableWorkStore(engine)
    host2 = SQLModelDurableWorkStore(engine)
    submission, _ = host1.accept(
        _ctx(),
        idempotency_key="race",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    with session_scope(engine) as session:
        row = session.exec(
            select(DurableSnapshotRow).where(DurableSnapshotRow.store_id == "default")
        ).first()
        assert row is not None
        stale_version = int(row.payload_version)

    host2.acquire_lease(
        _ctx(), submission.submission_id, owner_id="two", ttl_seconds=60
    )
    # host2 bumped version; writing with the pre-lease version must conflict
    with session_scope(engine) as session:
        mem, _ = host1._read(session, for_update=True)
        with pytest.raises(ControlPlaneError, match="version conflict"):
            host1._write(session, mem, expected_version=stale_version)


def test_read_only_durable_ops_do_not_bump_payload_version(tmp_path: Path) -> None:
    from etlantic_sqlmodel.control_plane.models import DurableSnapshotRow
    from etlantic_sqlmodel.control_plane.session import session_scope
    from sqlmodel import select

    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'ro.db'}")
    apply_migrations(engine)
    store = SQLModelDurableWorkStore(engine)
    submission, _ = store.accept(
        _ctx(),
        idempotency_key="ro",
        operation="run.submit",
        plan_fingerprint="plan",
    )

    def _version() -> int:
        with session_scope(engine) as session:
            row = session.exec(
                select(DurableSnapshotRow).where(
                    DurableSnapshotRow.store_id == "default"
                )
            ).first()
            assert row is not None
            return int(row.payload_version)

    before = _version()
    store.explain_transition(
        _ctx(), "cursor:x", expected_version=None, value_fingerprint="v1"
    )
    store.replay(_ctx(), submission.submission_id)
    store.plan_resume(_ctx(), submission.submission_id)
    store.plan_repair(_ctx(), submission.submission_id)
    store.plan_backfill(_ctx(), submission.submission_id, partition_ids=("p1",))
    assert _version() == before


def test_cancel_reconciliation_is_persisted_and_unknown_after_worker_death(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'cancel-recovery.db'}")
    apply_migrations(engine)
    store = SQLModelDurableWorkStore(engine)
    submission, _ = store.accept(
        _ctx(),
        idempotency_key="cancel-recovery",
        operation="run.submit",
        plan_fingerprint="plan",
    )
    lease = store.acquire_lease(
        _ctx(), submission.submission_id, owner_id="crashed-worker", ttl_seconds=1
    )
    attempt = store.start_attempt(
        _ctx(),
        submission.submission_id,
        owner_id="crashed-worker",
        fencing_token=lease.fencing_token,
    )
    assert store.cancel_submission(_ctx(), submission.submission_id).status == (
        "cancel_requested"
    )
    sleep(1.1)

    reopened = SQLModelDurableWorkStore(engine)
    recovered = reopened.reconcile_cancelled_submissions(_ctx(), limit=10)
    assert [item.submission_id for item in recovered] == [submission.submission_id]
    assert (
        reopened.get_submission(_ctx(), submission.submission_id).status == "cancelled"
    )
    assert reopened.list_attempts(_ctx(), submission.submission_id)[0].status == "lost"
    assert (
        reopened.get_effect(_ctx(), f"{submission.submission_id}:execution").status
        == "unknown"
    )
    assert reopened.pending_outbox(_ctx()) == []
    assert attempt.status == "running"
