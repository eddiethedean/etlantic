"""SQL deadlines abort mutations and preserve verified late commit receipts."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Any, cast

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine

from etlantic.control_plane import (
    ActionJobRecord,
    ControlPlaneContext,
    ControlPlaneError,
    DurableWorkStore,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.action_jobs import (
    ConnectorProvisionCleanupRequest,
    verify_provision_parent,
)
from etlantic.runtime import ActionExecutionHost
from etlantic.service import ManagedApplicationService
from etlantic_sql import action_handlers as sql_actions


@dataclass
class Actions:
    engine: Engine
    ctx: ControlPlaneContext
    store: DurableWorkStore
    service: ManagedApplicationService
    worker: ActionExecutionHost
    resource: str
    connection: str

    def provision(self, *, deadline: float = 5) -> ActionJobRecord:
        return self.store.accept_action_job(
            self.ctx,
            action="connector.provision",
            idempotency_key=f"provision-{uuid.uuid4().hex}",
            request={
                "provider": "postgresql",
                "connection_id": self.connection,
                "resource_id": self.resource,
                "columns": [{"name": "id", "logical_type": "integer"}],
            },
            deadline_at=(datetime.now(UTC) + timedelta(seconds=deadline)).isoformat(),
        )

    def cleanup(
        self, parent: ActionJobRecord, *, deadline: float = 5
    ) -> ActionJobRecord:
        return self.store.accept_action_job(
            self.ctx,
            action="connector.provision.cleanup",
            idempotency_key=f"cleanup-{uuid.uuid4().hex}",
            request={
                "provider": "postgresql",
                "connection_id": self.connection,
                "resource_id": self.resource,
                "provision_action_id": parent.action_id,
            },
            deadline_at=(datetime.now(UTC) + timedelta(seconds=deadline)).isoformat(),
        )


@pytest.fixture(params=["sqlite", "postgresql"])
def actions(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Actions]:
    backend = request.param
    url = os.environ.get("ETLANTIC_ACTION_POSTGRES_URL")
    if backend == "postgresql":
        if not url:
            pytest.skip("ETLANTIC_ACTION_POSTGRES_URL is not configured")
    else:
        url = f"sqlite:///{tmp_path / 'actions.db'}"
    engine = create_engine(url)
    ctx = ControlPlaneContext(
        principal=Principal("deadline-owner"),
        tenant=TenantRef("deadline-tenant"),
        workspace=WorkspaceRef("deadline-tenant", "deadline-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("deadline-domain"),
    )
    authorizer = MemoryAuthorizer()
    for action in (
        "connector.provision",
        "connector.provision.cleanup",
        "connector.test",
    ):
        authorizer.grant(ctx, action)
    store = MemoryDurableWorkStore()

    def resolve(_ctx: ControlPlaneContext, _connection: str) -> Engine:
        return engine

    async def quick(
        _ctx: ControlPlaneContext, _request: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return {"ok": True}

    handlers = sql_actions.create_action_handlers(resolve)
    handlers["connector.test"] = quick
    worker = ActionExecutionHost(store, handlers=handlers, authorizer=authorizer)
    suffix = uuid.uuid4().hex[:16]
    application = Actions(
        engine,
        ctx,
        store,
        ManagedApplicationService(
            authorizer=authorizer,
            definitions=MemoryDefinitionRepository(),
            submissions=MemorySubmissionStore(),
            durable_work=store,
        ),
        worker,
        f"deadline_{suffix}",
        f"saved-{suffix}",
    )
    try:
        yield application
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS "{application.resource}"'))
            if inspect(connection).has_table("etlantic_connector_action_effects"):
                connection.execute(
                    text(
                        "DELETE FROM etlantic_connector_action_effects WHERE connection_id = :connection"
                    ),
                    {"connection": application.connection},
                )
        engine.dispose()


def _settle(monkeypatch: pytest.MonkeyPatch) -> Event:
    finished = Event()
    execute = cast(
        Callable[..., dict[str, Any]], getattr(sql_actions, "_execute", None)
    )

    def observed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return execute(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(sql_actions, "_execute", observed)
    return finished


@pytest.mark.parametrize("kind", ["provision", "cleanup"])
@pytest.mark.parametrize("autocommit", [False, True])
def test_deadline_rolls_back_a_mutation_after_a_blocked_driver_hook(
    actions: Actions, monkeypatch: pytest.MonkeyPatch, kind: str, autocommit: bool
) -> None:
    if autocommit:
        actions.engine.update_execution_options(isolation_level="AUTOCOMMIT")
    parent = actions.provision()
    if kind == "cleanup":
        assert actions.worker.tick(actions.ctx, limit=1) == 1
    else:
        # Keep the short deadline independent of fixture construction time.
        parent = actions.store.get_action_job(actions.ctx, parent.action_id)
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        actions.cleanup(parent)
        assert actions.worker.tick(actions.ctx, limit=1) == 1
    started, release = Event(), Event()
    settled = _settle(monkeypatch)

    def block(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _params: Any,
        _context: Any,
        _many: bool,
    ) -> None:
        operation = "DROP TABLE" if kind == "cleanup" else "CREATE TABLE"
        if operation in statement and actions.resource in statement:
            started.set()
            assert release.wait(3)

    event.listen(actions.engine, "before_cursor_execute", block)
    job = (
        actions.cleanup(parent, deadline=0.4)
        if kind == "cleanup"
        else actions.provision(deadline=0.4)
    )
    try:
        start = monotonic()
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        assert monotonic() - start < 1.5
        assert started.is_set() and not settled.is_set()
        timed_out = actions.store.get_action_job(actions.ctx, job.action_id)
        assert timed_out.status == "timed_out" and timed_out.result_json is None
    finally:
        release.set()
        assert settled.wait(3)
        event.remove(actions.engine, "before_cursor_execute", block)
    assert inspect(actions.engine).has_table(actions.resource) is (kind == "cleanup")
    if kind == "cleanup":
        # A rolled-back cleanup can still compensate the original owned effect.
        retry = actions.cleanup(parent)
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        assert (
            actions.store.get_action_job(actions.ctx, retry.action_id).status
            == "succeeded"
        )
        assert not inspect(actions.engine).has_table(actions.resource)


@pytest.mark.parametrize("kind", ["provision", "cleanup"])
@pytest.mark.parametrize("acknowledgement", ["delayed", "lost"])
@pytest.mark.parametrize(
    "store_kind", ["memory", pytest.param("sqlmodel", marks=pytest.mark.sqlmodel)]
)
def test_committed_effect_remains_verifiable_after_timeout_and_next_job(
    actions: Actions,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    kind: str,
    acknowledgement: str,
    store_kind: str,
) -> None:
    reopen: Callable[[], DurableWorkStore] | None = None
    if store_kind == "sqlmodel":
        pytest.importorskip("sqlmodel")

        from etlantic_sqlmodel.control_plane import (
            SQLModelDurableWorkStore,
            create_sqlite_engine,
        )
        from etlantic_sqlmodel.migrations import apply_migrations

        engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'durable.db'}")
        apply_migrations(engine)
        actions.store = cast(DurableWorkStore, SQLModelDurableWorkStore(engine))
        actions.service.durable_work = actions.store
        actions.worker.durable = actions.store

        def reopen_store() -> DurableWorkStore:
            return cast(DurableWorkStore, SQLModelDurableWorkStore(engine))

        reopen = reopen_store
    parent = actions.provision()
    if kind == "cleanup":
        assert actions.worker.tick(actions.ctx, limit=1) == 1
    else:
        # The target action must be the only queued mutation in this case.
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        actions.cleanup(parent)
        assert actions.worker.tick(actions.ctx, limit=1) == 1
    committed, release, retained = Event(), Event(), Event()
    finish = actions.store.finish_action_job

    def observed_finish(*args: Any, **kwargs: Any) -> ActionJobRecord:
        row = finish(*args, **kwargs)
        if row.status == "timed_out" and row.result_json is not None:
            retained.set()
        return row

    monkeypatch.setattr(actions.store, "finish_action_job", observed_finish)
    commit = actions.engine.dialect.do_commit
    execute = cast(
        Callable[..., dict[str, Any]], getattr(sql_actions, "_execute", None)
    )
    if acknowledgement == "delayed":
        execute = cast(
            Callable[..., dict[str, Any]], getattr(sql_actions, "_execute", None)
        )

        def delay_ack(*args: Any, **kwargs: Any) -> dict[str, Any]:
            result = execute(*args, **kwargs)
            committed.set()
            assert release.wait(3)
            return result

        monkeypatch.setattr(sql_actions, "_execute", delay_ack)
    else:
        commit = actions.engine.dialect.do_commit

        def lose_ack(connection: Any) -> None:
            commit(connection)
            committed.set()
            assert release.wait(3)
            raise RuntimeError("private database commit acknowledgement failure")

        monkeypatch.setattr(actions.engine.dialect, "do_commit", lose_ack)
    job = (
        actions.cleanup(parent, deadline=0.4)
        if kind == "cleanup"
        else actions.provision(deadline=0.4)
    )
    try:
        start = monotonic()
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        assert monotonic() - start < 1.5 and committed.is_set()
        assert (
            actions.store.get_action_job(actions.ctx, job.action_id).status
            == "timed_out"
        )
        quick = actions.store.accept_action_job(
            actions.ctx,
            action="connector.test",
            idempotency_key="next-job",
            request={"provider": "mock", "connection_id": "next"},
            deadline_at=(datetime.now(UTC) + timedelta(seconds=5)).isoformat(),
        )
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        assert (
            actions.store.get_action_job(actions.ctx, quick.action_id).status
            == "succeeded"
        )
    finally:
        release.set()
        if acknowledgement == "lost":
            monkeypatch.setattr(actions.engine.dialect, "do_commit", commit)
    assert retained.wait(3)
    receipt = actions.store.get_action_job(actions.ctx, job.action_id)
    assert receipt.status == "timed_out" and receipt.error_code == "deadline_exceeded"
    assert receipt.to_dict()["result"]["action_id"] == job.action_id
    assert "private database" not in str(receipt.to_dict())
    # Persistence of the proof is independent of the provider handler lifetime.
    if reopen is not None:
        actions.store = reopen()
        actions.service.durable_work = actions.store
        actions.worker.durable = actions.store
        assert (
            actions.store.get_action_job(actions.ctx, job.action_id).result_json
            == receipt.result_json
        )
    if kind == "provision":
        cleanup_request = ConnectorProvisionCleanupRequest(
            "postgresql", actions.connection, actions.resource, job.action_id
        )
        verify_provision_parent(actions.ctx, cleanup_request, receipt)
        with pytest.raises(ControlPlaneError):
            verify_provision_parent(
                replace(actions.ctx, principal=Principal("another-owner")),
                cleanup_request,
                receipt,
            )
        accepted = actions.service.submit_connector_action(
            actions.ctx,
            "connector.provision.cleanup",
            cleanup_request.to_dict(),
            idempotency_key="authorized-late-cleanup",
        )
        if acknowledgement == "delayed":
            monkeypatch.setattr(sql_actions, "_execute", execute)
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        assert (
            actions.store.get_action_job(actions.ctx, str(accepted["action_id"])).status
            == "succeeded"
        )
    assert not inspect(actions.engine).has_table(actions.resource)


@pytest.mark.parametrize("kind", ["provision", "cleanup"])
def test_postgresql_cancels_an_in_flight_statement_at_the_deadline(
    actions: Actions, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    if actions.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL statement cancellation qualification")
    parent = actions.provision()
    assert actions.worker.tick(actions.ctx, limit=1) == 1
    if kind == "provision":
        actions.cleanup(parent)
        assert actions.worker.tick(actions.ctx, limit=1) == 1
    settled = _settle(monkeypatch)
    started = Event()

    def slow_query(
        _connection: Any,
        cursor: Any,
        statement: str,
        _params: Any,
        _context: Any,
        _many: bool,
    ) -> None:
        operation = "DROP TABLE" if kind == "cleanup" else "CREATE TABLE"
        if operation in statement and actions.resource in statement:
            started.set()
            cursor.execute("SELECT pg_sleep(5)")

    event.listen(actions.engine, "before_cursor_execute", slow_query)
    try:
        job = (
            actions.cleanup(parent, deadline=0.4)
            if kind == "cleanup"
            else actions.provision(deadline=0.4)
        )
        start = monotonic()
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        assert monotonic() - start < 1.5
        assert started.is_set() and settled.wait(3)
        receipt = actions.store.get_action_job(actions.ctx, job.action_id)
        assert receipt.status == "timed_out" and receipt.result_json is None
    finally:
        event.remove(actions.engine, "before_cursor_execute", slow_query)
    assert inspect(actions.engine).has_table(actions.resource) is (kind == "cleanup")


def test_unresponsive_driver_cancel_does_not_block_the_action_worker(
    actions: Actions, monkeypatch: pytest.MonkeyPatch
) -> None:
    started, release, cancel_started, cancel_release, settled = (
        Event() for _ in range(5)
    )
    execute = cast(
        Callable[..., dict[str, Any]], getattr(sql_actions, "_execute", None)
    )

    class StuckDriver:
        def cancel(self) -> None:
            cancel_started.set()
            assert cancel_release.wait(3)

    def blocked(
        engine: Engine,
        ctx: ControlPlaneContext,
        request: Mapping[str, Any],
        operation: Any,
        *,
        cleanup: bool,
    ) -> dict[str, Any]:
        with operation.driver_lock:
            operation.driver = StuckDriver()
        started.set()
        try:
            assert release.wait(3)
            operation.check()
            return execute(engine, ctx, request, operation, cleanup=cleanup)
        finally:
            with operation.driver_lock:
                operation.driver = None
            settled.set()

    monkeypatch.setattr(sql_actions, "_execute", blocked)
    job = actions.provision(deadline=0.4)
    try:
        start = monotonic()
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        assert monotonic() - start < 1.5
        assert started.is_set() and cancel_started.wait(1)
        assert (
            actions.store.get_action_job(actions.ctx, job.action_id).status
            == "timed_out"
        )
    finally:
        cancel_release.set()
        release.set()
        assert settled.wait(3)
    assert not inspect(actions.engine).has_table(actions.resource)


@pytest.mark.parametrize("kind", ["provision", "cleanup"])
def test_same_key_recovers_uncertain_commit_after_receipt_reconciliation_outage(
    actions: Actions, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    parent = actions.provision()
    assert actions.worker.tick(actions.ctx, limit=1) == 1
    if kind == "provision":
        actions.cleanup(parent)
        assert actions.worker.tick(actions.ctx, limit=1) == 1
    commit = actions.engine.dialect.do_commit
    reconcile = getattr(sql_actions, "_committed_effect", None)
    committed, release, failed_read = Event(), Event(), Event()

    def lost_ack(connection: Any) -> None:
        commit(connection)
        committed.set()
        assert release.wait(3)
        raise RuntimeError("lost commit acknowledgement")

    def read_outage(*args: Any, **kwargs: Any) -> bool:
        failed_read.set()
        raise RuntimeError("temporary receipt registry outage")

    monkeypatch.setattr(actions.engine.dialect, "do_commit", lost_ack)
    monkeypatch.setattr(sql_actions, "_committed_effect", read_outage)
    job = (
        actions.cleanup(parent, deadline=0.4)
        if kind == "cleanup"
        else actions.provision(deadline=0.4)
    )
    try:
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        assert committed.is_set()
    finally:
        release.set()
        assert failed_read.wait(3)
        monkeypatch.setattr(actions.engine.dialect, "do_commit", commit)
        monkeypatch.setattr(sql_actions, "_committed_effect", reconcile)
    assert actions.store.get_action_job(actions.ctx, job.action_id).result_json is None
    import json

    renewed = actions.store.accept_action_job(
        actions.ctx,
        action=job.action,
        idempotency_key=job.idempotency_key,
        request=json.loads(job.request_json),
        deadline_at=(datetime.now(UTC) + timedelta(seconds=5)).isoformat(),
    )
    assert renewed.action_id == job.action_id and renewed.status == "queued"
    assert actions.worker.tick(actions.ctx, limit=1) == 1
    recovered = actions.store.get_action_job(actions.ctx, job.action_id)
    assert (
        recovered.status == "succeeded" and recovered.fencing_token > job.fencing_token
    )
    assert recovered.to_dict()["result"]["action_id"] == job.action_id
    if kind == "provision":
        cleanup = actions.service.submit_connector_action(
            actions.ctx,
            "connector.provision.cleanup",
            {
                "provider": "postgresql",
                "connection_id": actions.connection,
                "resource_id": actions.resource,
                "provision_action_id": job.action_id,
            },
            idempotency_key="compensate-recovered-effect",
        )
        assert actions.worker.tick(actions.ctx, limit=1) == 1
        assert (
            actions.store.get_action_job(actions.ctx, str(cleanup["action_id"])).status
            == "succeeded"
        )
    assert not inspect(actions.engine).has_table(actions.resource)


def test_late_receipt_cannot_replace_a_newer_worker_fence() -> None:
    store = MemoryDurableWorkStore()
    ctx = ControlPlaneContext(
        principal=Principal("owner"),
        tenant=TenantRef("tenant"),
        workspace=WorkspaceRef("tenant", "workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("domain"),
    )
    now = datetime.now(UTC)
    request = {
        "provider": "mock",
        "connection_id": "saved",
        "resource_id": "target",
        "columns": [{"name": "id", "logical_type": "integer"}],
    }
    job = store.accept_action_job(
        ctx,
        action="connector.provision",
        idempotency_key="renew",
        request=request,
        deadline_at=(now + timedelta(seconds=1)).isoformat(),
    )
    first = store.claim_action_job(ctx, worker_id="first", lease_seconds=30, now=now)
    assert first is not None
    store.finish_action_job(
        ctx,
        job.action_id,
        worker_id="first",
        fencing_token=first.fencing_token,
        status="timed_out",
        now=now + timedelta(seconds=2),
    )
    renewed = store.accept_action_job(
        ctx,
        action=job.action,
        idempotency_key="renew",
        request=request,
        deadline_at=(now + timedelta(seconds=10)).isoformat(),
    )
    assert renewed.action_id == job.action_id
    second = store.claim_action_job(
        ctx, worker_id="second", lease_seconds=30, now=now + timedelta(seconds=3)
    )
    assert second is not None and second.fencing_token > first.fencing_token
    receipt = {"effect_id": "effect", "action_id": job.action_id}
    with pytest.raises(ControlPlaneError, match="stale"):
        store.finish_action_job(
            ctx,
            job.action_id,
            worker_id="first",
            fencing_token=first.fencing_token,
            status="succeeded",
            result=receipt,
            now=now + timedelta(seconds=4),
        )
    store.finish_action_job(
        ctx,
        job.action_id,
        worker_id="second",
        fencing_token=second.fencing_token,
        status="succeeded",
        result=receipt,
        now=now + timedelta(seconds=11),
    )
    saved = store.get_action_job(ctx, job.action_id)
    assert saved.status == "timed_out" and saved.to_dict()["result"] == receipt
    with pytest.raises(ControlPlaneError, match="stale"):
        store.finish_action_job(
            ctx,
            job.action_id,
            worker_id="first",
            fencing_token=first.fencing_token,
            status="succeeded",
            result=receipt,
            now=now + timedelta(seconds=12),
        )
    with pytest.raises(ControlPlaneError, match="conflicts"):
        store.finish_action_job(
            ctx,
            job.action_id,
            worker_id="second",
            fencing_token=second.fencing_token,
            status="succeeded",
            result={"effect_id": "other"},
            now=now + timedelta(seconds=12),
        )
