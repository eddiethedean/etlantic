# pyright: reportMissingImports=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""SQLModel control-plane store restart and multi-worker tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

from sqlalchemy.exc import IntegrityError

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.runtime.managed_execution import managed_run_id
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


def test_sqlite_acceptance_keeps_same_key_isolated_by_principal(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'cp-principal-scope.db'}")
    create_control_plane_tables(engine)
    store = SQLModelSubmissionStore(engine)
    alice = _ctx()
    bob = replace(alice, principal=Principal(subject="bob"))

    alice_run_id = managed_run_id(alice, "shared-key")
    bob_run_id = managed_run_id(bob, "shared-key")
    alice_result = store.accept(
        alice,
        idempotency_key="shared-key",
        payload={"definition_id": "pipe", "owner": "alice"},
        resource_id=alice_run_id,
    )
    bob_result = store.accept(
        bob,
        idempotency_key="shared-key",
        payload={"definition_id": "pipe", "owner": "bob"},
        resource_id=bob_run_id,
    )

    assert alice_run_id != bob_run_id
    assert alice_result.receipt.submission_id != bob_result.receipt.submission_id
    assert (
        store.get_run(alice, alice_run_id)["submission_id"]
        == alice_result.receipt.submission_id
    )
    assert (
        store.get_run(bob, bob_run_id)["submission_id"]
        == bob_result.receipt.submission_id
    )


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


def test_sqlite_event_append_once_survives_restart_and_rejects_conflicts(
    tmp_path: Path,
) -> None:
    url = f"sqlite:///{tmp_path / 'cp-events-idempotent.db'}"
    engine = create_sqlite_engine(url)
    create_control_plane_tables(engine)
    ctx = _ctx()
    first = SqlModelEventStore(engine).append_once(
        ctx,
        event_key="sub-1:attempt-1:started",
        kind="run.started",
        payload={"run_id": "run-1", "attempt_id": "attempt-1"},
    )

    restarted = create_sqlite_engine(url)
    events = SqlModelEventStore(restarted)
    repeated = events.append_once(
        ctx,
        event_key="sub-1:attempt-1:started",
        kind="run.started",
        payload={"run_id": "run-1", "attempt_id": "attempt-1"},
    )
    assert repeated.event_id == first.event_id
    assert len(events.list_after_cursor(ctx, None)) == 1
    with pytest.raises(ControlPlaneError) as caught:
        events.append_once(
            ctx,
            event_key="sub-1:attempt-1:started",
            kind="run.started",
            payload={"run_id": "different"},
        )
    assert caught.value.status == 409


def test_sqlite_event_retention_preserves_tombstones_and_sequence_anchor(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'cp-events-retention.db'}")
    create_control_plane_tables(engine)
    ctx = _ctx()
    events = SqlModelEventStore(engine)
    expired = events.append_once(
        ctx,
        event_key="started:attempt-1",
        kind="run.started",
        payload={"run_id": "run-1"},
    )
    events.append(ctx, kind="run.progress", payload={"run_id": "run-1"})
    anchor = events.append(ctx, kind="run.completed", payload={"run_id": "run-1"})
    other_scope = events.append(_ctx(tenant="tenant-b"), kind="other.scope")

    assert events.prune_before_sequence(ctx, before_sequence=3) == 2
    with pytest.raises(ControlPlaneError) as cursor_error:
        events.list_after_cursor(ctx, expired.cursor)
    assert cursor_error.value.status == 410
    with pytest.raises(ControlPlaneError) as retry_error:
        events.append_once(
            ctx,
            event_key="started:attempt-1",
            kind="run.started",
            payload={"run_id": "run-1"},
        )
    assert retry_error.value.status == 410
    with pytest.raises(ControlPlaneError) as conflict:
        events.append_once(
            ctx,
            event_key="started:attempt-1",
            kind="run.started",
            payload={"run_id": "different"},
        )
    assert conflict.value.status == 409

    appended = events.append(ctx, kind="run.recovered")
    assert appended.sequence == anchor.sequence + 1 == 4
    assert [event.event_id for event in events.list_after_cursor(ctx, None)] == [
        anchor.event_id,
        appended.event_id,
    ]
    assert events.list_after_cursor(_ctx(tenant="tenant-b"), None) == [other_scope]


def test_sqlite_event_retention_policy_is_enforced_and_survives_restart(
    tmp_path: Path,
) -> None:
    url = f"sqlite:///{tmp_path / 'cp-events-policy.db'}"
    engine = create_sqlite_engine(url)
    create_control_plane_tables(engine)
    ctx = _ctx()
    unbounded = SqlModelEventStore(engine)
    expired = unbounded.append_once(
        ctx,
        event_key="start-policy-1",
        kind="run.started",
        payload={"run_id": "run-1"},
    )
    unbounded.append(ctx, kind="run.progress", payload={"run_id": "run-1"})
    anchor = unbounded.append(ctx, kind="run.completed", payload={"run_id": "run-1"})
    other_scope = unbounded.append(_ctx(tenant="tenant-b"), kind="other.scope")

    retained = SqlModelEventStore(engine, max_events_per_scope=2)
    assert [event.sequence for event in retained.list_after_cursor(ctx, None)] == [2, 3]
    with pytest.raises(ControlPlaneError) as cursor_error:
        retained.list_after_cursor(ctx, expired.cursor)
    assert cursor_error.value.status == 410
    with pytest.raises(ControlPlaneError) as retry_error:
        retained.append_once(
            ctx,
            event_key="start-policy-1",
            kind="run.started",
            payload={"run_id": "run-1"},
        )
    assert retry_error.value.status == 410

    next_event = retained.append(ctx, kind="run.recovered")
    assert next_event.sequence == anchor.sequence + 1 == 4
    assert [event.sequence for event in retained.list_after_cursor(ctx, None)] == [3, 4]
    assert retained.list_after_cursor(_ctx(tenant="tenant-b"), None) == [other_scope]
    engine.dispose()

    restarted_engine = create_sqlite_engine(url)
    restarted = SqlModelEventStore(restarted_engine, max_events_per_scope=2)
    assert [event.sequence for event in restarted.list_after_cursor(ctx, None)] == [
        3,
        4,
    ]
    with pytest.raises(ControlPlaneError) as restarted_retry:
        restarted.append_once(
            ctx,
            event_key="start-policy-1",
            kind="run.started",
            payload={"run_id": "run-1"},
        )
    assert restarted_retry.value.status == 410
    restarted_engine.dispose()


def test_sqlite_event_store_rejects_invalid_retention_policy(tmp_path: Path) -> None:
    engine = create_sqlite_engine(
        f"sqlite:///{tmp_path / 'cp-events-invalid-policy.db'}"
    )
    with pytest.raises(ValueError, match="positive integer"):
        SqlModelEventStore(engine, max_events_per_scope=0)
    engine.dispose()


def test_sqlite_event_sequence_conflict_is_bounded_and_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'cp-events.db'}")
    create_control_plane_tables(engine)
    events = SqlModelEventStore(engine)
    attempts = 0

    def collide(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise IntegrityError(
            "INSERT INTO cp_events",
            {},
            RuntimeError("duplicate uq_cp_event_scope_seq"),
        )

    monkeypatch.setattr(events, "_append_once", collide)
    with pytest.raises(ControlPlaneError) as caught:
        events.append(_ctx(), kind="run.accepted")

    assert attempts == 3
    assert caught.value.code == "PMCP409"
    assert caught.value.extensions == {
        "operation": "event.append",
        "retryable": True,
    }


def test_sqlite_event_append_does_not_retry_unrelated_integrity_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'cp-events.db'}")
    create_control_plane_tables(engine)
    events = SqlModelEventStore(engine)
    attempts = 0

    def fail(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise IntegrityError(
            "INSERT INTO cp_events",
            {},
            RuntimeError("not-null violation"),
        )

    monkeypatch.setattr(events, "_append_once", fail)
    with pytest.raises(IntegrityError):
        events.append(_ctx(), kind="run.accepted")

    assert attempts == 1


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
    repo.compare_and_swap(a, "pipe", {"owner": "a"}, {"owner": "a-edited"})
    with pytest.raises(ControlPlaneError) as stale:
        repo.compare_and_swap(a, "pipe", {"owner": "a"}, {"owner": "stale"})
    assert stale.value.status == 409
    assert repo.get(a, "pipe")["owner"] == "a-edited"
    with pytest.raises(ControlPlaneError):
        repo.get(a, "missing")
