"""Provider-backed create/compensate action qualification on SQLAlchemy."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.engine import Engine

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDurableWorkStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.action_jobs import parse_connector_action_request
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.runtime import ActionExecutionHost
from etlantic.secrets import SecretValue
from etlantic_sql import LivePostgresStorageConnector, create_action_handlers


def _context(owner: str = "sql-provision-owner") -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(owner),
        tenant=TenantRef("sql-provision-tenant"),
        workspace=WorkspaceRef("sql-provision-tenant", "sql-provision-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("sql-provision-domain"),
        resource_owner_id=owner,
    )


def _accept(
    store: MemoryDurableWorkStore,
    ctx: ControlPlaneContext,
    *,
    action: str,
    key: str,
    request: dict[str, Any],
) -> Any:
    return store.accept_action_job(
        ctx,
        action=action,
        idempotency_key=key,
        request=request,
        deadline_at=(datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
    )


def test_sql_provision_create_only_effect_retry_and_compensating_cleanup(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'provision.db'}")
    ctx = _context()
    resolver_calls: list[tuple[str, str]] = []

    def resolve_engine(action_ctx: ControlPlaneContext, connection_id: str) -> Any:
        resolver_calls.append((action_ctx.principal.subject, connection_id))
        return engine

    handlers = create_action_handlers(resolve_engine)
    # Registering the provider handlers is pure; ordinary setup creates no SQL
    # target or effect table before an authorized provision action is accepted.
    assert inspect(engine).get_table_names() == []
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.provision")
    authorizer.grant(ctx, "connector.provision.cleanup")
    store = MemoryDurableWorkStore()
    worker = ActionExecutionHost(
        store,
        handlers=handlers,
        authorizer=authorizer,
        worker_id="sql-provision-worker",
    )
    request: dict[str, Any] = {
        "provider": "postgresql",
        "connection_id": "saved-postgres",
        "resource_id": "orders",
        "target_kind": "table",
        "columns": [
            {
                "name": "id",
                "logical_type": "integer",
                "nullable": False,
                "primary_key": True,
            },
            {"name": "label", "logical_type": "string"},
        ],
    }
    provision = _accept(
        store,
        ctx,
        action="connector.provision",
        key="create-orders",
        request=request,
    )
    assert worker.tick(ctx, limit=1) == 1
    created = store.get_action_job(ctx, provision.action_id)
    assert created.status == "succeeded"
    receipt = created.to_dict()["result"]
    assert receipt["action_id"] == provision.action_id
    assert receipt["resource_id"] == "orders"
    assert receipt["created"] is True
    assert receipt["cleanup_supported"] is True
    assert inspect(engine).has_table("orders")
    assert [column["name"] for column in inspect(engine).get_columns("orders")] == [
        "id",
        "label",
    ]
    assert inspect(engine).get_pk_constraint("orders")["constrained_columns"] == ["id"]

    # A retry after the provider commit but before durable receipt publication
    # returns the same effect receipt from the transactional effect registry.
    retry_request: dict[str, Any] = {
        **request,
        "columns": [
            {**request["columns"][0]},
            {**request["columns"][1], "nullable": True, "primary_key": False},
        ],
        "action_id": provision.action_id,
        "mode": "create_only",
        "if_exists": "fail",
        "schema_fingerprint": receipt["schema_fingerprint"],
    }

    async def retry_provision() -> Any:
        return await handlers["connector.provision"](ctx, retry_request)

    assert anyio.run(retry_provision) == receipt

    conflict = _accept(
        store,
        ctx,
        action="connector.provision",
        key="do-not-replace-orders",
        request=request,
    )
    assert worker.tick(ctx, limit=1) == 1
    failed_conflict = store.get_action_job(ctx, conflict.action_id)
    assert failed_conflict.status == "failed"
    assert failed_conflict.error_code == "action_failed"
    assert inspect(engine).has_table("orders")

    cleanup = _accept(
        store,
        ctx,
        action="connector.provision.cleanup",
        key="cleanup-orders",
        request={
            "provider": "postgresql",
            "connection_id": "saved-postgres",
            "resource_id": "orders",
            "provision_action_id": provision.action_id,
        },
    )
    assert worker.tick(ctx, limit=1) == 1
    cleaned = store.get_action_job(ctx, cleanup.action_id)
    assert cleaned.status == "succeeded"
    assert cleaned.to_dict()["result"] == {
        "action_id": cleanup.action_id,
        "effect_id": receipt["effect_id"],
        "resource_id": "orders",
        "cleanup_of": provision.action_id,
        "removed": True,
    }
    assert not inspect(engine).has_table("orders")

    cleanup_retry_request = {
        "provider": "postgresql",
        "connection_id": "saved-postgres",
        "resource_id": "orders",
        "provision_action_id": provision.action_id,
        "action_id": cleanup.action_id,
        "effect_id": receipt["effect_id"],
        "schema_fingerprint": receipt["schema_fingerprint"],
        "target_kind": "table",
    }

    async def retry_cleanup() -> Any:
        return await handlers["connector.provision.cleanup"](ctx, cleanup_retry_request)

    assert anyio.run(retry_cleanup) == cleaned.to_dict()["result"]
    with engine.connect() as connection:
        state = connection.execute(
            text(
                "SELECT state FROM etlantic_connector_action_effects "
                "WHERE resource_id = 'orders'"
            )
        ).scalar_one()
    assert state == "removed"
    assert resolver_calls == [
        ("sql-provision-owner", "saved-postgres"),
        ("sql-provision-owner", "saved-postgres"),
        ("sql-provision-owner", "saved-postgres"),
        ("sql-provision-owner", "saved-postgres"),
        ("sql-provision-owner", "saved-postgres"),
    ]
    engine.dispose()


def test_sql_provision_schema_rejects_nullable_primary_key_before_provider_io() -> None:
    with pytest.raises(ControlPlaneError, match="cannot be nullable"):
        parse_connector_action_request(
            "connector.provision",
            {
                "provider": "postgresql",
                "connection_id": "saved-postgres",
                "resource_id": "orders",
                "columns": [
                    {
                        "name": "id",
                        "logical_type": "integer",
                        "nullable": True,
                        "primary_key": True,
                    }
                ],
            },
        )


def test_sql_read_only_actions_pass_remaining_deadline_to_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import etlantic_sql.action_handlers as action_handlers

    ctx = _context()
    resolved: list[tuple[ControlPlaneContext, str, float]] = []
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def resolve_engine(
        action_ctx: ControlPlaneContext,
        connection_id: str,
        *,
        timeout_seconds: float,
    ) -> Any:
        resolved.append((action_ctx, connection_id, timeout_seconds))
        return engine

    def fake_test_connection(
        _engine: Any, _operation: Any, _request: Any
    ) -> dict[str, str | bool]:
        return {
            "schema": "etlantic.connector_test/1",
            "ok": True,
            "provider": "postgresql",
        }

    monkeypatch.setattr(
        action_handlers, "_test_postgresql_connection", fake_test_connection
    )
    deadline_at = datetime.now(UTC) + timedelta(seconds=10)
    result = anyio.run(
        create_action_handlers(resolve_engine)["connector.test"],
        ctx,
        {
            "provider": "postgresql",
            "connection_id": "saved-postgres",
            "_deadline_at": deadline_at.isoformat(),
        },
    )

    assert result["ok"] is True
    assert len(resolved) == 1
    assert resolved[0][:2] == (ctx, "saved-postgres")
    assert 0 < resolved[0][2] <= 10


def test_sql_read_only_actions_reject_legacy_unbounded_resolver() -> None:
    ctx = _context()
    store = MemoryDurableWorkStore()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.test")
    resolver_calls: list[str] = []

    def resolve_engine(_ctx: ControlPlaneContext, connection_id: str) -> Any:
        resolver_calls.append(connection_id)
        raise AssertionError("unbounded resolver must not be called")

    worker = ActionExecutionHost(
        store,
        handlers=create_action_handlers(resolve_engine),
        authorizer=authorizer,
    )
    job = _accept(
        store,
        ctx,
        action="connector.test",
        key="unbounded-resolver",
        request={"provider": "postgresql", "connection_id": "saved"},
    )

    assert worker.tick(ctx, limit=1) == 1
    receipt = store.get_action_job(ctx, job.action_id).to_dict()
    assert receipt["status"] == "failed"
    assert receipt["error_code"] == "action_failed"
    assert resolver_calls == []


def test_postgresql_action_provision_effect_and_cleanup() -> None:
    database_url = os.environ.get("ETLANTIC_ACTION_POSTGRES_URL")
    if not database_url:
        pytest.skip("ETLANTIC_ACTION_POSTGRES_URL is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    ctx = _context()
    suffix = uuid.uuid4().hex[:16]
    resource_id = f"etlantic_ac056_{suffix}"
    connection_id = f"action-{suffix}"
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.provision")
    authorizer.grant(ctx, "connector.provision.cleanup")
    store = MemoryDurableWorkStore()

    def resolve_engine(_ctx: ControlPlaneContext, _connection_id: str) -> Engine:
        return engine

    worker = ActionExecutionHost(
        store,
        handlers=create_action_handlers(resolve_engine),
        authorizer=authorizer,
        worker_id=f"postgres-action-{suffix}",
    )
    provision = _accept(
        store,
        ctx,
        action="connector.provision",
        key=f"postgres-create-{suffix}",
        request={
            "provider": "postgresql",
            "connection_id": connection_id,
            "resource_id": resource_id,
            "columns": [
                {
                    "name": "id",
                    "logical_type": "integer",
                    "nullable": False,
                    "primary_key": True,
                },
                {"name": "payload", "logical_type": "json"},
            ],
        },
    )
    try:
        assert worker.tick(ctx, limit=1) == 1
        created = store.get_action_job(ctx, provision.action_id)
        assert created.status == "succeeded"
        receipt = created.to_dict()["result"]
        assert inspect(engine).has_table(resource_id)
        columns = inspect(engine).get_columns(resource_id)
        assert [column["name"] for column in columns] == ["id", "payload"]
        before_inspection = set(inspect(engine).get_table_names())
        storage = LivePostgresStorageConnector()
        runtime_context = {
            "secret": SecretValue(
                _value=database_url,
                provider="fixture",
                name="postgres-url",
                key="url",
                version="test",
            )
        }

        async def inspect_target() -> Any:
            return await storage.inspect_schema(
                binding={
                    "provider": "postgresql",
                    "config": {"schema": "public", "table": resource_id},
                },
                context=runtime_context,
            )

        inspected = anyio.run(inspect_target)
        assert [field["name"] for field in inspected.fields] == ["id", "payload"]
        assert set(inspect(engine).get_table_names()) == before_inspection

        cleanup = _accept(
            store,
            ctx,
            action="connector.provision.cleanup",
            key=f"postgres-cleanup-{suffix}",
            request={
                "provider": "postgresql",
                "connection_id": connection_id,
                "resource_id": resource_id,
                "provision_action_id": provision.action_id,
            },
        )
        assert worker.tick(ctx, limit=1) == 1
        cleaned = store.get_action_job(ctx, cleanup.action_id)
        assert cleaned.status == "succeeded"
        assert cleaned.to_dict()["result"]["effect_id"] == receipt["effect_id"]
        assert not inspect(engine).has_table(resource_id)
    finally:
        with engine.begin() as connection:
            if inspect(connection).has_table(resource_id):
                Table(resource_id, MetaData()).drop(connection, checkfirst=True)
            if inspect(connection).has_table("etlantic_connector_action_effects"):
                connection.execute(
                    text(
                        "DELETE FROM etlantic_connector_action_effects "
                        "WHERE connection_id = :connection_id AND resource_id = :resource_id"
                    ),
                    {"connection_id": connection_id, "resource_id": resource_id},
                )
        engine.dispose()


def test_postgresql_connection_test_and_bounded_schema_inspection() -> None:
    database_url = os.environ.get("ETLANTIC_ACTION_POSTGRES_URL")
    if not database_url:
        pytest.skip("ETLANTIC_ACTION_POSTGRES_URL is not configured")
    suffix = uuid.uuid4().hex[:12]
    schema_name = f"etlantic_action_{suffix}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    provider_engine: Engine | None = None
    try:
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema_name}"')
            connection.exec_driver_sql(
                f'CREATE TABLE "{schema_name}"."fixture" '
                "(id bigint PRIMARY KEY, payload text NOT NULL)"
            )
            connection.exec_driver_sql(
                f'INSERT INTO "{schema_name}"."fixture" VALUES (1, \'private-row-value\')'
            )
        resolved_engine = create_engine(
            database_url,
            connect_args={
                "connect_timeout": 5,
                "options": f"-csearch_path={schema_name}",
            },
            pool_pre_ping=True,
        )
        provider_engine = resolved_engine
        assert provider_engine is not None
        ctx = _context()
        authorizer = MemoryAuthorizer()
        authorizer.grant(ctx, "connector.test")
        authorizer.grant(ctx, "connector.schema.inspect")
        store = MemoryDurableWorkStore()
        resolver_calls: list[tuple[ControlPlaneContext, str]] = []

        def resolve_engine(
            action_ctx: ControlPlaneContext,
            connection_id: str,
            *,
            timeout_seconds: float,
        ) -> Engine:
            assert timeout_seconds > 0
            resolver_calls.append((action_ctx, connection_id))
            return resolved_engine

        handlers = create_action_handlers(resolve_engine)
        worker = ActionExecutionHost(store, handlers=handlers, authorizer=authorizer)
        before_tables = inspect(provider_engine).get_table_names()
        with provider_engine.connect() as connection:
            before_rows = connection.exec_driver_sql(
                'SELECT count(*) FROM "fixture"'
            ).scalar_one()

        tested = _accept(
            store,
            ctx,
            action="connector.test",
            key=f"postgres-connection-test-{suffix}",
            request={"provider": "postgresql", "connection_id": f"saved-{suffix}"},
        )
        assert worker.tick(ctx, limit=1) == 1
        test_receipt = store.get_action_job(ctx, tested.action_id).to_dict()
        assert test_receipt["status"] == "succeeded"
        assert test_receipt["result"] == {
            "schema": "etlantic.connector_test/1",
            "ok": True,
            "provider": "postgresql",
        }

        inspected = _accept(
            store,
            ctx,
            action="connector.schema.inspect",
            key=f"postgres-schema-inspection-{suffix}",
            request={
                "provider": "postgresql",
                "connection_id": f"saved-{suffix}",
                "max_fields": 1,
            },
        )
        assert worker.tick(ctx, limit=1) == 1
        inspection_receipt = store.get_action_job(ctx, inspected.action_id).to_dict()
        assert inspection_receipt["status"] == "succeeded"
        result = inspection_receipt["result"]
        assert result["provider"] == "postgresql"
        assert result["has_more"] is True
        assert len(result["fields"]) == 1
        assert result["fields"][0] == {
            "table": "fixture",
            "name": "id",
            "type": "bigint",
            "nullable": False,
            "primary_key": True,
        }
        assert "private-row-value" not in repr(result)
        assert inspect(provider_engine).get_table_names() == before_tables
        with provider_engine.connect() as connection:
            after_rows = connection.exec_driver_sql(
                'SELECT count(*) FROM "fixture"'
            ).scalar_one()
        assert after_rows == before_rows == 1
        assert resolver_calls == [
            (ctx, f"saved-{suffix}"),
            (ctx, f"saved-{suffix}"),
        ]
    finally:
        if provider_engine is not None:
            provider_engine.dispose()
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
        admin_engine.dispose()


@pytest.mark.parametrize("failure", ["revoked", "provider-outage"])
def test_sql_connection_test_hides_revoked_reference_and_provider_errors(
    failure: str,
) -> None:
    engine = create_engine("sqlite://")
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.test")
    store = MemoryDurableWorkStore()
    saved_connections: dict[str, Engine] = {"saved": engine}

    def resolve_engine(
        _ctx: ControlPlaneContext,
        connection_id: str,
        *,
        timeout_seconds: float,
    ) -> Engine:
        assert timeout_seconds > 0
        if failure == "provider-outage":
            raise RuntimeError("connection password must stay private")
        return saved_connections[connection_id]

    worker = ActionExecutionHost(
        store,
        handlers=create_action_handlers(resolve_engine),
        authorizer=authorizer,
    )
    job = _accept(
        store,
        ctx,
        action="connector.test",
        key=f"connection-{failure}",
        request={"provider": "postgresql", "connection_id": "saved"},
    )
    if failure == "revoked":
        saved_connections.pop("saved")
    try:
        assert worker.tick(ctx, limit=1) == 1
        receipt = store.get_action_job(ctx, job.action_id).to_dict()
        assert receipt["status"] == "failed"
        assert receipt["error_code"] == "action_failed"
        assert "password" not in repr(receipt)
    finally:
        engine.dispose()


def test_sql_connection_test_rechecks_connection_authorization_before_resolution() -> (
    None
):
    engine = create_engine("sqlite://")
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.test")
    authorizer.forbidden_resources.add(
        (
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            "connector.test",
            "connection:saved",
        )
    )
    resolver_calls: list[str] = []

    def resolve_engine(_ctx: ControlPlaneContext, connection_id: str) -> Engine:
        resolver_calls.append(connection_id)
        return engine

    store = MemoryDurableWorkStore()
    worker = ActionExecutionHost(
        store,
        handlers=create_action_handlers(resolve_engine),
        authorizer=authorizer,
    )
    job = _accept(
        store,
        ctx,
        action="connector.test",
        key="connection-authz-recheck",
        request={"provider": "postgresql", "connection_id": "saved"},
    )
    try:
        assert worker.tick(ctx, limit=1) == 1
        receipt = store.get_action_job(ctx, job.action_id).to_dict()
        assert receipt["status"] == "failed"
        assert receipt["error_code"] == "authorization_denied"
        assert resolver_calls == []
    finally:
        engine.dispose()
