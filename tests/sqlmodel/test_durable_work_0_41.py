"""SQLModel CP3 durable work store, migrations, and conformance (0.41 / 041-P)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

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
from etlantic_sqlmodel.migrations import apply_migrations, current_version

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
    assert apply_migrations(engine) == "002_durable_cp3"
    assert current_version(engine) == "002_durable_cp3"


def test_sqlmodel_durable_conformance(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'c.db'}")
    apply_migrations(engine)
    run_durable_work_conformance_suite(SQLModelDurableWorkStore(engine))


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
