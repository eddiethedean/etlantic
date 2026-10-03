"""Explicit create-only SQL provisioning actions with compensating cleanup."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    inspect,
    select,
    update,
)
from sqlalchemy.engine import Connection, Engine

from etlantic.control_plane import ControlPlaneContext
from etlantic.runtime import ActionHandler

EngineResolver = Callable[[ControlPlaneContext, str], Engine]
_REGISTRY_NAME = "etlantic_connector_action_effects"
_SAFE_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}\Z")
_TYPES: dict[str, Any] = {
    "string": Text,
    "integer": Integer,
    "number": Float,
    "boolean": Boolean,
    "decimal": Numeric,
    "date": Date,
    "timestamp": lambda: DateTime(timezone=True),
    "json": JSON,
}


def _scope_id(ctx: ControlPlaneContext) -> str:
    identity = {
        "tenant": ctx.tenant.tenant_id,
        "workspace": ctx.workspace.workspace_id,
        "owner": ctx.resource_owner_id or ctx.principal.subject,
        "environment": ctx.environment.name,
        "security_domain": ctx.security_domain.domain_id,
        "principal_issuer": ctx.principal.issuer,
        "principal_kind": ctx.principal.kind,
        "principal_subject": ctx.principal.subject,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _registry(metadata: MetaData) -> Table:
    return Table(
        _REGISTRY_NAME,
        metadata,
        Column("connection_id", String(256), primary_key=True),
        Column("resource_id", String(63), primary_key=True),
        Column("scope_id", String(64), nullable=False),
        Column("provider", String(64), nullable=False),
        Column("provision_action_id", String(256), nullable=False),
        Column("effect_id", String(64), nullable=False),
        Column("schema_fingerprint", String(64), nullable=False),
        Column("state", String(16), nullable=False),
        Column("target_kind", String(16), nullable=False),
    )


def _target_table(request: Mapping[str, Any]) -> Table:
    resource_id = request.get("resource_id")
    if not isinstance(resource_id, str) or not _SAFE_IDENTIFIER.fullmatch(resource_id):
        raise ValueError("SQL provisioning resource_id must be a simple identifier")
    raw_columns = request.get("columns")
    if not isinstance(raw_columns, list) or not raw_columns:
        raise ValueError("SQL provisioning requires typed columns")
    raw_column_list = cast(list[Any], raw_columns)
    columns: list[Column[Any]] = []
    for raw_value in raw_column_list:
        if not isinstance(raw_value, Mapping):
            raise ValueError("SQL provisioning column declaration is invalid")
        raw = cast(Mapping[str, Any], raw_value)
        name = raw.get("name")
        logical_type = raw.get("logical_type")
        if not isinstance(name, str) or not _SAFE_IDENTIFIER.fullmatch(name):
            raise ValueError("SQL provisioning column name is invalid")
        type_factory = _TYPES.get(str(logical_type))
        if type_factory is None:
            raise ValueError("SQL provisioning column type is unsupported")
        nullable = raw.get("nullable", True)
        primary_key = raw.get("primary_key", False)
        if type(nullable) is not bool or type(primary_key) is not bool:
            raise ValueError("SQL provisioning column flags are invalid")
        columns.append(
            Column(
                name,
                type_factory(),
                nullable=nullable,
                primary_key=primary_key,
            )
        )
    return Table(resource_id, MetaData(), *columns)


def _receipt(
    *,
    action_id: str,
    effect_id: str,
    resource_id: str,
    schema_fingerprint: str,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "effect_id": effect_id,
        "resource_id": resource_id,
        "schema_fingerprint": schema_fingerprint,
        "created": True,
        "cleanup_supported": True,
    }


def _create_table_effect(
    connection: Connection,
    *,
    engine: Engine,
    ctx: ControlPlaneContext,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    if request.get("provider") != "postgresql":
        raise ValueError("SQL provisioning supports provider='postgresql'")
    if engine.dialect.name not in {"postgresql", "sqlite"}:
        raise ValueError("SQL provisioning dialect is unsupported")
    if request.get("target_kind") != "table":
        raise ValueError("SQL provisioning supports table targets only")
    action_id = request.get("action_id")
    connection_id = request.get("connection_id")
    resource_id = request.get("resource_id")
    fingerprint = request.get("schema_fingerprint")
    if not all(
        isinstance(value, str) and value for value in (action_id, connection_id)
    ):
        raise ValueError("SQL provisioning action identity is invalid")
    if not isinstance(resource_id, str) or not _SAFE_IDENTIFIER.fullmatch(resource_id):
        raise ValueError("SQL provisioning resource_id must be a simple identifier")
    if not isinstance(fingerprint, str) or not re.fullmatch(
        r"[0-9a-f]{64}", fingerprint
    ):
        raise ValueError("SQL provisioning schema fingerprint is invalid")

    registry = _registry(MetaData())
    if not inspect(connection).has_table(_REGISTRY_NAME):
        registry.create(connection, checkfirst=False)
    scope_id = _scope_id(ctx)
    existing = (
        connection.execute(
            select(registry).where(
                registry.c.connection_id == connection_id,
                registry.c.resource_id == resource_id,
            )
        )
        .mappings()
        .first()
    )
    target_exists = inspect(connection).has_table(resource_id)
    if existing is not None:
        row = dict(existing)
        if (
            row["scope_id"] == scope_id
            and row["provider"] == "postgresql"
            and row["provision_action_id"] == action_id
            and row["schema_fingerprint"] == fingerprint
            and row["state"] == "created"
            and target_exists
        ):
            return _receipt(
                action_id=str(action_id),
                effect_id=str(row["effect_id"]),
                resource_id=resource_id,
                schema_fingerprint=fingerprint,
            )
        if row["state"] != "removed" or row["scope_id"] != scope_id:
            raise ValueError("SQL target is already owned by another provision effect")
    elif target_exists:
        raise ValueError("SQL target already exists outside the provision registry")

    table = _target_table(request)
    table.create(connection, checkfirst=False)
    effect_material = "\0".join(
        (scope_id, str(connection_id), resource_id, str(action_id), fingerprint)
    )
    effect_id = hashlib.sha256(effect_material.encode("utf-8")).hexdigest()
    values = {
        "connection_id": connection_id,
        "resource_id": resource_id,
        "scope_id": scope_id,
        "provider": "postgresql",
        "provision_action_id": action_id,
        "effect_id": effect_id,
        "schema_fingerprint": fingerprint,
        "state": "created",
        "target_kind": "table",
    }
    if existing is None:
        connection.execute(registry.insert().values(**values))
    else:
        connection.execute(
            update(registry)
            .where(
                registry.c.connection_id == connection_id,
                registry.c.resource_id == resource_id,
            )
            .values(**values)
        )
    return _receipt(
        action_id=str(action_id),
        effect_id=effect_id,
        resource_id=resource_id,
        schema_fingerprint=fingerprint,
    )


def _remove_table_effect(
    connection: Connection,
    *,
    ctx: ControlPlaneContext,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    if request.get("provider") != "postgresql":
        raise ValueError("SQL cleanup supports provider='postgresql'")
    if request.get("target_kind") != "table":
        raise ValueError("SQL cleanup supports table targets only")
    action_id = request.get("action_id")
    connection_id = request.get("connection_id")
    resource_id = request.get("resource_id")
    provision_action_id = request.get("provision_action_id")
    effect_id = request.get("effect_id")
    fingerprint = request.get("schema_fingerprint")
    if (
        not isinstance(resource_id, str)
        or not _SAFE_IDENTIFIER.fullmatch(resource_id)
        or not all(
            isinstance(value, str) and value
            for value in (
                action_id,
                connection_id,
                provision_action_id,
                effect_id,
                fingerprint,
            )
        )
    ):
        raise ValueError("SQL cleanup effect identity is invalid")
    if not inspect(connection).has_table(_REGISTRY_NAME):
        raise ValueError("SQL provision effect is unavailable")
    registry = _registry(MetaData())
    existing = (
        connection.execute(
            select(registry).where(
                registry.c.connection_id == connection_id,
                registry.c.resource_id == resource_id,
            )
        )
        .mappings()
        .first()
    )
    if existing is None:
        raise ValueError("SQL provision effect is unavailable")
    row = dict(existing)
    if (
        row["scope_id"] != _scope_id(ctx)
        or row["provider"] != "postgresql"
        or row["provision_action_id"] != provision_action_id
        or row["effect_id"] != effect_id
        or row["schema_fingerprint"] != fingerprint
        or row["target_kind"] != "table"
    ):
        raise ValueError("SQL provision effect does not match the cleanup request")
    if row["state"] == "created":
        if inspect(connection).has_table(resource_id):
            target = Table(resource_id, MetaData(), autoload_with=connection)
            target.drop(connection, checkfirst=False)
        connection.execute(
            update(registry)
            .where(
                registry.c.connection_id == connection_id,
                registry.c.resource_id == resource_id,
                registry.c.state == "created",
            )
            .values(state="removed")
        )
    elif row["state"] != "removed":
        raise ValueError("SQL provision effect has an invalid state")
    return {
        "action_id": action_id,
        "effect_id": effect_id,
        "resource_id": resource_id,
        "cleanup_of": provision_action_id,
        "removed": True,
    }


def create_action_handlers(resolve_engine: EngineResolver) -> dict[str, ActionHandler]:
    """Build PostgreSQL create-only table provisioning and cleanup handlers.

    The callback receives trusted worker context and an opaque saved connection
    ID. It returns an application-owned SQLAlchemy engine whose credentials and
    lifecycle remain outside action requests and receipts.
    """

    # One abandoned operation must not create an unbounded executor backlog.
    slot = threading.BoundedSemaphore(1)

    async def invoke(
        ctx: ControlPlaneContext, request: Mapping[str, Any], *, cleanup: bool
    ) -> Mapping[str, Any]:
        operation = _ActionOperation(request)
        while not slot.acquire(blocking=False):
            operation.check()
            await asyncio.sleep(0.01)
        future: Future[Mapping[str, Any]] = Future()
        operation.future = future

        def run() -> None:
            try:
                operation.check()
                engine = resolve_engine(ctx, str(request["connection_id"]))
                operation.check()
                result = _execute(engine, ctx, request, operation, cleanup=cleanup)
            except BaseException as exc:
                slot.release()
                future.set_exception(exc)
            else:
                slot.release()
                future.set_result(result)
            operation.retain_if_cancelled()

        threading.Thread(target=run, name="etlantic-sql-action", daemon=True).start()
        wrapped = asyncio.wrap_future(future)

        def consume_result(completed: asyncio.Future[Mapping[str, Any]]) -> None:
            if not completed.cancelled():
                completed.exception()

        wrapped.add_done_callback(consume_result)
        try:
            return await asyncio.shield(wrapped)
        except asyncio.CancelledError:
            operation.cancel()
            raise

    async def provision(
        ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await invoke(ctx, request, cleanup=False)

    async def cleanup(
        ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await invoke(ctx, request, cleanup=True)

    return {
        "connector.provision": provision,
        "connector.provision.cleanup": cleanup,
    }


class _ActionOperation:
    def __init__(self, request: Mapping[str, Any]) -> None:
        value = request.get("_deadline_at")
        self.deadline = (
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if value is not None
            else None
        )
        if self.deadline is not None and self.deadline.tzinfo is None:
            raise ValueError("SQL action deadline must be timezone aware")
        callback = request.get("_retain_effect")
        self.retain = (
            cast(Callable[[Mapping[str, Any]], None], callback)
            if callable(callback)
            else None
        )
        self.cancelled = threading.Event()
        self.lock = threading.Lock()
        self.driver_lock = threading.Lock()
        self.driver: Any = None
        self.future: Future[Mapping[str, Any]] = Future()
        self.retained = False

    def check(self) -> None:
        if self.cancelled.is_set() or (
            self.deadline is not None and datetime.now(UTC) >= self.deadline
        ):
            raise TimeoutError("SQL action deadline exceeded")

    def cancel(self) -> None:
        self.cancelled.set()

        def interrupt() -> None:
            # Keep the connection out of the pool until cancellation completes;
            # a delayed cancel must never target its next borrower.
            with self.driver_lock:
                if self.driver is not None:
                    callback = getattr(self.driver, "cancel", None) or getattr(
                        self.driver, "interrupt", None
                    )
                    if callable(callback):
                        with suppress(Exception):
                            callback()

        threading.Thread(
            target=interrupt, name="etlantic-sql-cancel", daemon=True
        ).start()
        self.retain_if_cancelled()

    def retain_if_cancelled(self) -> None:
        with self.lock:
            if not self.cancelled.is_set() or not self.future.done() or self.retained:
                return
            self.retained = True
        try:
            result = self.future.result()
        except BaseException:
            return
        if self.retain is not None:
            # A stale worker cannot publish through a newer fencing token.
            with suppress(Exception):
                self.retain(result)


def _execute(
    engine: Engine,
    ctx: ControlPlaneContext,
    request: Mapping[str, Any],
    operation: _ActionOperation,
    *,
    cleanup: bool,
) -> dict[str, Any]:
    if engine.dialect.name not in {"postgresql", "sqlite"}:
        raise ValueError("SQL provisioning dialect is unsupported")
    operation.check()
    result: dict[str, Any] | None = None
    try:
        with engine.connect() as connection:
            with operation.driver_lock:
                operation.driver = connection.connection.driver_connection
            try:
                operation.check()
                if engine.dialect.name == "postgresql":
                    # An application-owned engine may use AUTOCOMMIT. Retain
                    # its database isolation level while requiring a real
                    # transaction for DDL and the effect registry.
                    connection.execution_options(
                        isolation_level=connection.get_isolation_level()
                    )
                    operation.check()
                with connection.begin():
                    if engine.dialect.name == "sqlite":
                        # SQLite's legacy transaction mode otherwise commits
                        # DDL independently of rollback and the registry.
                        connection.exec_driver_sql("BEGIN")
                    elif operation.deadline is not None:
                        milliseconds = max(
                            1,
                            int(
                                (operation.deadline - datetime.now(UTC)).total_seconds()
                                * 1000
                            ),
                        )
                        connection.exec_driver_sql(
                            f"SET LOCAL statement_timeout = {milliseconds}"
                        )
                        connection.exec_driver_sql(
                            f"SET LOCAL lock_timeout = {milliseconds}"
                        )
                    operation.check()
                    result = (
                        _remove_table_effect(connection, ctx=ctx, request=request)
                        if cleanup
                        else _create_table_effect(
                            connection, engine=engine, ctx=ctx, request=request
                        )
                    )
                    operation.check()
                # Return the receipt only after the actual transaction commit.
                return result
            finally:
                with operation.driver_lock:
                    operation.driver = None
    except Exception:
        # COMMIT acknowledgement loss is not proof of rollback. Verify the
        # effect with a fresh, bounded read before discarding its receipt.
        if result is not None and _committed_effect(
            engine, ctx, request, result, cleanup=cleanup
        ):
            return result
        raise


def _committed_effect(
    engine: Engine,
    ctx: ControlPlaneContext,
    request: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    cleanup: bool,
) -> bool:
    registry = _registry(MetaData())
    with engine.connect() as connection:
        if engine.dialect.name == "postgresql":
            connection.execution_options(
                isolation_level=connection.get_isolation_level()
            )
            connection.exec_driver_sql("SET LOCAL statement_timeout = 1000")
            connection.exec_driver_sql("SET LOCAL lock_timeout = 1000")
        if not inspect(connection).has_table(_REGISTRY_NAME):
            return False
        row = (
            connection.execute(
                select(registry).where(
                    registry.c.connection_id == request["connection_id"],
                    registry.c.resource_id == request["resource_id"],
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return False
        return (
            row["scope_id"] == _scope_id(ctx)
            and row["provider"] == "postgresql"
            and row["provision_action_id"]
            == request["provision_action_id" if cleanup else "action_id"]
            and row["effect_id"] == result["effect_id"]
            and row["schema_fingerprint"] == request["schema_fingerprint"]
            and row["target_kind"] == "table"
            and row["state"] == ("removed" if cleanup else "created")
            and inspect(connection).has_table(str(request["resource_id"]))
            is not cleanup
        )


__all__ = ["EngineResolver", "create_action_handlers"]
