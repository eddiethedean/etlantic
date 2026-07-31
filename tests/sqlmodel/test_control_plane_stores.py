"""SQLModel control-plane store restart and multi-worker tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
from etlantic_sqlmodel.control_plane import (
    SQLModelDefinitionRepository,
    SqlModelEventStore,
    SQLModelSubmissionStore,
    create_control_plane_tables,
    create_sqlite_engine,
)

pytestmark = pytest.mark.sqlmodel


def _ctx(tenant: str = "tenant-a", workspace: str = "ws-1") -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def test_sqlite_restart_preserves_accept(tmp_path: Path) -> None:
    db = tmp_path / "cp.db"
    url = f"sqlite:///{db}"
    engine = create_sqlite_engine(url)
    create_control_plane_tables(engine)
    store = SQLModelSubmissionStore(engine)
    ctx = _ctx()
    first = store.accept(
        ctx,
        idempotency_key="idem-restart",
        payload={"definition_id": "pipe"},
    )
    # Simulate restart: new engine + store against same file.
    engine2 = create_sqlite_engine(url)
    store2 = SQLModelSubmissionStore(engine2)
    found = store2.lookup_idempotency(ctx, "idem-restart")
    assert found is not None
    assert found.acceptance_id == first.receipt.acceptance_id
    assert found.submission_id == first.receipt.submission_id
    run = store2.get_run(ctx, first.receipt.resource_id or first.receipt.submission_id)
    assert run["status"] == "accepted"


def test_sqlite_event_store_restart(tmp_path: Path) -> None:
    db = tmp_path / "cp-events.db"
    url = f"sqlite:///{db}"
    engine = create_sqlite_engine(url)
    create_control_plane_tables(engine)
    events = SqlModelEventStore(engine)
    ctx = _ctx()
    first = events.append(
        ctx, kind="run.accepted", payload={"run_id": "run-1", "note": "ok"}
    )
    engine2 = create_sqlite_engine(url)
    events2 = SqlModelEventStore(engine2)
    listed = events2.list_after_cursor(ctx, None, limit=10)
    assert len(listed) == 1
    assert listed[0].event_id == first.event_id
    assert listed[0].payload == {"run_id": "run-1", "note": "ok"}
    assert listed[0].to_dict()["run_id"] == "run-1"


def test_sqlite_multi_worker_idempotent_submit(tmp_path: Path) -> None:
    db = tmp_path / "cp-mw.db"
    url = f"sqlite:///{db}"
    engine = create_sqlite_engine(url)
    create_control_plane_tables(engine)
    store_a = SQLModelSubmissionStore(engine)
    store_b = SQLModelSubmissionStore(engine)
    ctx = _ctx()

    def accept(store: SQLModelSubmissionStore):
        return store.accept(
            ctx,
            idempotency_key="idem-mw",
            payload={"definition_id": "pipe"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(accept, store_a)
        f2 = pool.submit(accept, store_b)
        r1, r2 = f1.result(), f2.result()

    assert r1.receipt.acceptance_id == r2.receipt.acceptance_id
    assert r1.receipt.submission_id == r2.receipt.submission_id
    assert r1.created or r2.created


def test_definition_repo_scoped(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'defs.db'}")
    create_control_plane_tables(engine)
    repo = SQLModelDefinitionRepository(engine)
    a = _ctx("tenant-a", "ws-1")
    b = _ctx("tenant-b", "ws-1")
    repo.put(a, "pipe", {"owner": "a"})
    repo.put(b, "pipe", {"owner": "b"})
    assert repo.get(a, "pipe")["owner"] == "a"
    assert repo.get(b, "pipe")["owner"] == "b"
    assert list(repo.list(a)) == ["pipe"]
    with pytest.raises(KeyError):
        repo.get(a, "missing")
