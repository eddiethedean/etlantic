"""Provider-backed create/compensate action qualification on SQLAlchemy."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
