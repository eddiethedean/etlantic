"""Live, bounded PostgreSQL connector implementations.

The connectors deliberately keep credentials out of connector configuration.
They accept a runtime ``SecretValue`` containing a PostgreSQL URL (or an
explicit worker ``ETLANTIC_SQL_URL`` setting), and never serialize it into a
plan, receipt, or connector error.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, cast

from etlantic.connectors.capabilities import (
    IDEMPOTENCY,
    PUBLICATION_ATOMIC,
    RECONCILIATION,
    SOURCE_BATCH_SNAPSHOT,
    SOURCE_PARTITIONED,
    SOURCE_SCHEMA_DISCOVERY,
    SOURCE_STATISTICS_BOUNDED,
    TRANSACTIONS,
    WRITE_APPEND,
    WRITE_MERGE,
    WRITE_OVERWRITE,
    WRITE_PARTITION_REPLACE,
)
from etlantic.connectors.errors import (
    ConnectorConfigError,
    ConnectorReadError,
    ConnectorWriteError,
)
from etlantic.connectors.maturity import ConnectorMaturity
from etlantic.connectors.models import (
    SINK_PROTOCOL,
    SOURCE_PROTOCOL,
    STORAGE_PROTOCOL,
    CleanupReceipt,
    CommitReceipt,
    ConnectorInfo,
    CursorProposal,
    LandingReadManifest,
    ReadBatch,
    ReconciliationResult,
    SchemaInspection,
    SinkPlan,
    SourcePlan,
    WriteSession,
    fingerprint_public_config,
)
from etlantic.secrets import SecretValue
from etlantic_sql.configuration_schemas import (
    SINK_CONFIG_SCHEMA,
    SOURCE_CONFIG_SCHEMA,
    STORAGE_CONFIG_SCHEMA,
)

PROVIDER = "postgresql"
PACKAGE_VERSION = "0.57.0"
_RESOURCE_IDENTITY_KEY = secrets.token_bytes(32)
DEFAULT_ROW_LIMIT = 10_000
MAX_ROW_LIMIT = 100_000
DEFAULT_BATCH_SIZE = 1_000
MAX_BATCH_SIZE = 10_000
DEFAULT_BYTE_LIMIT = 64 * 1024 * 1024
MAX_BYTE_LIMIT = 256 * 1024 * 1024
_MAX_BIND_PARAMETERS = 65_535
DEFAULT_EFFECT_TABLE = "etlantic_connector_effects"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 300

SOURCE_CAPS = frozenset(
    {
        SOURCE_BATCH_SNAPSHOT,
        SOURCE_SCHEMA_DISCOVERY,
        SOURCE_STATISTICS_BOUNDED,
        SOURCE_PARTITIONED,
    }
)
SINK_CAPS = frozenset(
    {
        WRITE_APPEND,
        WRITE_OVERWRITE,
        WRITE_MERGE,
        PUBLICATION_ATOMIC,
        TRANSACTIONS,
        RECONCILIATION,
        IDEMPOTENCY,
        WRITE_PARTITION_REPLACE,
    }
)

_IDENTIFIER = re.compile(r"^[^\x00.]+$")
_SOURCE_KEYS = {
    "schema",
    "table",
    "mode",
    "row_limit",
    "batch_size",
    "max_bytes",
    "timeout_seconds",
    "partition_column",
}
_SINK_KEYS = {
    "schema",
    "table",
    "mode",
    "key_columns",
    "effect_table",
    "timeout_seconds",
    "partition_column",
}
_STORAGE_KEYS = {"schema", "table", "timeout_seconds"}
_SENSITIVE_CONFIG_KEYS = {"url", "dsn", "database_url", "connection_string"}


def _config(binding: Mapping[str, Any], allowed: set[str]) -> dict[str, Any]:
    raw = binding.get("config")
    if raw is not None and not isinstance(raw, Mapping):
        raise ConnectorConfigError(
            "postgresql config must be an object",
            code="PMCONN844",
            provider=PROVIDER,
        )
    cfg: dict[str, Any] = dict(cast(Mapping[str, Any], raw) if raw is not None else {})
    forbidden = _SENSITIVE_CONFIG_KEYS.intersection(cfg)
    if forbidden:
        raise ConnectorConfigError(
            "PostgreSQL credentials must be supplied through a secret reference",
            code="PMCONN845",
            provider=PROVIDER,
        )
    unknown = set(cfg).difference(allowed)
    if unknown:
        raise ConnectorConfigError(
            f"unsupported postgresql options: {', '.join(sorted(unknown))}",
            code="PMCONN846",
            provider=PROVIDER,
        )
    return cfg


def _secret_ref_names(binding: Mapping[str, Any]) -> tuple[str, ...]:
    raw = binding.get("secret_refs")
    if not isinstance(raw, Mapping):
        return ()
    secret_refs = cast(Mapping[str, Any], raw)
    return tuple(sorted(str(key) for key in secret_refs))


def _table_parts(binding: Mapping[str, Any], cfg: Mapping[str, Any]) -> tuple[str, str]:
    table_value = cfg.get("table") or binding.get("location")
    schema_value = cfg.get("schema") or "public"
    if not isinstance(table_value, str) or not table_value:
        raise ConnectorConfigError(
            "postgresql binding requires table",
            code="PMCONN841",
            provider=PROVIDER,
        )
    if "." in table_value:
        if cfg.get("schema"):
            raise ConnectorConfigError(
                "specify the PostgreSQL schema separately from table",
                code="PMCONN847",
                provider=PROVIDER,
            )
        parts = table_value.split(".")
        if len(parts) != 2:
            raise ConnectorConfigError(
                "PostgreSQL table must be table or schema.table",
                code="PMCONN847",
                provider=PROVIDER,
            )
        schema_value, table_value = parts
    if (
        not isinstance(schema_value, str)
        or not _IDENTIFIER.fullmatch(schema_value)
        or not _IDENTIFIER.fullmatch(table_value)
    ):
        raise ConnectorConfigError(
            "PostgreSQL schema and table identifiers must be nonempty",
            code="PMCONN847",
            provider=PROVIDER,
        )
    return schema_value, table_value


def _runtime_url(context: Mapping[str, Any]) -> Any:
    """Resolve a DB URL only from a scoped runtime secret or worker env."""
    from sqlalchemy.engine import make_url

    secret = context.get("secret")
    if isinstance(secret, SecretValue):
        raw_url = secret.value
    elif secret is None:
        raw_url = os.environ.get("ETLANTIC_SQL_URL")
    else:
        # Do not allow connector callers to smuggle plaintext through context.
        raise ConnectorConfigError(
            "postgresql context secret must be a SecretValue",
            code="PMCONN848",
            provider=PROVIDER,
        )
    if not isinstance(raw_url, str) or not raw_url:
        raise ConnectorConfigError(
            "PostgreSQL requires a runtime secret reference or ETLANTIC_SQL_URL",
            code="PMCONN849",
            provider=PROVIDER,
        )
    try:
        url = make_url(raw_url)
    except Exception as exc:
        raise ConnectorConfigError(
            "invalid PostgreSQL connection URL",
            code="PMCONN850",
            provider=PROVIDER,
        ) from exc
    if not url.drivername.startswith("postgresql") or not url.host:
        raise ConnectorConfigError(
            "PostgreSQL connection URL must use a PostgreSQL driver and host",
            code="PMCONN851",
            provider=PROVIDER,
        )
    return url


def _engine(
    context: Mapping[str, Any], *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> Any:
    from sqlalchemy import create_engine

    return create_engine(
        _runtime_url(context),
        pool_pre_ping=True,
        hide_parameters=True,
        echo=False,
        future=True,
        connect_args={
            "connect_timeout": timeout_seconds,
            "options": f"-c statement_timeout={timeout_seconds * 1000}",
        },
    )


def _bounded_integer(
    value: Any,
    *,
    name: str,
    default: int,
    maximum: int,
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConnectorConfigError(
            f"{name} must be a positive integer",
            code="PMCONN852",
            provider=PROVIDER,
        )
    if value > maximum:
        raise ConnectorConfigError(
            f"{name} exceeds the configured maximum of {maximum}",
            code="PMCONN853",
            provider=PROVIDER,
        )
    return value


def _qualified(schema: str, table: str) -> str:
    return f"{schema}.{table}"


def _resource_identity_token(payload: Mapping[str, Any]) -> str:
    """Return a process-local opaque identity for overlap comparisons."""
    canonical = json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hmac.new(_RESOURCE_IDENTITY_KEY, canonical, hashlib.sha256).hexdigest()


async def _postgres_resource_identities(
    context: Mapping[str, Any],
    *,
    schema: str,
    table: str,
    timeout_seconds: int,
) -> tuple[str, ...]:
    """Resolve URL and server aliases before the run can publish a sink."""
    from anyio import to_thread
    from sqlalchemy import text

    url = _runtime_url(context)
    identities = {
        _resource_identity_token(
            {
                "kind": "url",
                "host": str(url.host or "").rstrip(".").lower(),
                "port": int(url.port or 5432),
                "database": str(url.database or ""),
                "schema": schema,
                "table": table,
            }
        )
    }

    def inspect_server() -> tuple[str | None, int | None, str]:
        engine = _engine(context, timeout_seconds=timeout_seconds)
        try:
            with engine.connect() as connection:
                row = connection.execute(
                    text(
                        "SELECT inet_server_addr()::text, inet_server_port(), "
                        "current_database()"
                    )
                ).one()
                address = str(row[0]) if row[0] is not None else None
                port = int(row[1]) if row[1] is not None else None
                database = str(row[2])
                return address, port, database
        finally:
            engine.dispose()

    try:
        address, port, database = await to_thread.run_sync(inspect_server)
    except Exception:
        raise ConnectorConfigError(
            "PostgreSQL resource overlap could not be verified",
            code="PMCONN880",
            provider=PROVIDER,
        ) from None
    if address is not None and port is not None:
        identities.add(
            _resource_identity_token(
                {
                    "kind": "server",
                    "address": address,
                    "port": port,
                    "database": database,
                    "schema": schema,
                    "table": table,
                }
            )
        )
    return tuple(sorted(identities))


def _json_bytes(row: Mapping[str, Any]) -> int:
    try:
        return len(
            json.dumps(
                dict(row),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            ).encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise ConnectorReadError(
            "PostgreSQL row cannot be represented by the bounded record format",
            code="PMCONN854",
            provider=PROVIDER,
        ) from exc


def _normalize_partition_ids(partition_ids: Sequence[str]) -> tuple[str, ...]:
    """Validate opaque partition identifiers at the provider boundary."""
    if (
        not isinstance(partition_ids, (list, tuple))
        or not partition_ids
        or len(partition_ids) > 1000
        or any(
            not isinstance(value, str) or not value.strip() or len(value) > 4096
            for value in partition_ids
        )
        or len(set(partition_ids)) != len(partition_ids)
    ):
        raise ConnectorConfigError(
            "PostgreSQL partition ids must be 1-1000 unique non-blank strings",
            code="PMCONN887",
            provider=PROVIDER,
        )
    return tuple(partition_ids)


@dataclass
class LivePostgresSourceConnector:
    """Bounded table snapshots read from a live PostgreSQL database."""

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=tuple(sorted(SOURCE_CAPS)),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"dialect": "postgresql", "backend": "live"},
            configuration_schema=deepcopy(SOURCE_CONFIG_SCHEMA),
        )

    async def resource_identities(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> tuple[str, ...]:
        cfg = _config(binding, _SOURCE_KEYS)
        schema, table = _table_parts(binding, cfg)
        timeout_seconds = _bounded_integer(
            cfg.get("timeout_seconds"),
            name="timeout_seconds",
            default=DEFAULT_TIMEOUT_SECONDS,
            maximum=MAX_TIMEOUT_SECONDS,
        )
        return await _postgres_resource_identities(
            context,
            schema=schema,
            table=table,
            timeout_seconds=timeout_seconds,
        )

    async def plan_read(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> SourcePlan:
        cfg = _config(binding, _SOURCE_KEYS)
        mode = str(cfg.get("mode") or binding.get("mode") or "snapshot")
        if mode != "snapshot":
            raise ConnectorConfigError(
                "PostgreSQL source only supports snapshot reads",
                code="PMCONN855",
                provider=PROVIDER,
            )
        schema, table = _table_parts(binding, cfg)
        intent = {
            "schema": schema,
            "table": table,
            "row_limit": _bounded_integer(
                cfg.get("row_limit"),
                name="row_limit",
                default=DEFAULT_ROW_LIMIT,
                maximum=MAX_ROW_LIMIT,
            ),
            "batch_size": _bounded_integer(
                cfg.get("batch_size"),
                name="batch_size",
                default=DEFAULT_BATCH_SIZE,
                maximum=MAX_BATCH_SIZE,
            ),
            "max_bytes": _bounded_integer(
                cfg.get("max_bytes"),
                name="max_bytes",
                default=DEFAULT_BYTE_LIMIT,
                maximum=MAX_BYTE_LIMIT,
            ),
            "timeout_seconds": _bounded_integer(
                cfg.get("timeout_seconds"),
                name="timeout_seconds",
                default=DEFAULT_TIMEOUT_SECONDS,
                maximum=MAX_TIMEOUT_SECONDS,
            ),
        }
        return SourcePlan(
            provider=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            mode="snapshot",
            identity_scheme="postgresql_transaction_snapshot/1",
            listing_intent=intent,
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=_qualified(schema, table),
            secret_refs=_secret_ref_names(binding),
        )

    async def plan_read_partitions(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
        partition_ids: tuple[str, ...],
    ) -> SourcePlan:
        """Plan a bounded PostgreSQL read using configured partition values."""
        cfg = _config(binding, _SOURCE_KEYS)
        partition_column = cfg.get("partition_column")
        if not isinstance(partition_column, str) or not _IDENTIFIER.fullmatch(
            partition_column
        ):
            raise ConnectorConfigError(
                "PostgreSQL partition reads require a valid partition_column",
                code="PMCONN880",
                provider=PROVIDER,
            )
        normalized_ids = _normalize_partition_ids(partition_ids)
        base = await self.plan_read(binding=binding, context=context)
        intent = dict(base.listing_intent)
        intent.update(
            {
                "partition_column": partition_column,
                "partition_ids": list(normalized_ids),
            }
        )
        return SourcePlan(
            provider=base.provider,
            protocol=base.protocol,
            mode=base.mode,
            identity_scheme="postgresql_partition_snapshot/1",
            listing_intent=intent,
            required_capabilities=(SOURCE_PARTITIONED,),
            config_fingerprint=base.config_fingerprint,
            root_ref=base.root_ref,
            secret_refs=base.secret_refs,
        )

    async def read_batches(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AsyncIterator[ReadBatch]:
        from anyio import to_thread
        from sqlalchemy import MetaData, Table, select

        intent = dict(plan.listing_intent)
        schema = str(intent["schema"])
        table_name = str(intent["table"])
        row_limit = _bounded_integer(
            intent.get("row_limit"),
            name="row_limit",
            default=DEFAULT_ROW_LIMIT,
            maximum=MAX_ROW_LIMIT,
        )
        batch_size = _bounded_integer(
            intent.get("batch_size"),
            name="batch_size",
            default=DEFAULT_BATCH_SIZE,
            maximum=MAX_BATCH_SIZE,
        )
        max_bytes = _bounded_integer(
            intent.get("max_bytes"),
            name="max_bytes",
            default=DEFAULT_BYTE_LIMIT,
            maximum=MAX_BYTE_LIMIT,
        )
        if plan.config_fingerprint != fingerprint_public_config(
            _config(binding, _SOURCE_KEYS)
        ):
            raise ConnectorReadError(
                "PostgreSQL source plan does not match its binding",
                code="PMCONN875",
                provider=PROVIDER,
            )
        partition_ids = context.get("etlantic.partition_ids")
        if partition_ids is not None:
            if not isinstance(partition_ids, (list, tuple)):
                raise ConnectorReadError(
                    "PostgreSQL partition selector is invalid",
                    code="PMCONN881",
                    provider=PROVIDER,
                )
            expected_plan = await self.plan_read_partitions(
                binding=binding,
                context=context,
                partition_ids=tuple(cast(Sequence[str], partition_ids)),
            )
        else:
            expected_plan = await self.plan_read(binding=binding, context=context)
        if (
            plan.listing_intent != expected_plan.listing_intent
            or plan.root_ref != expected_plan.root_ref
            or plan.provider != expected_plan.provider
        ):
            raise ConnectorReadError(
                "PostgreSQL source plan content does not match its binding",
                code="PMCONN877",
                provider=PROVIDER,
            )

        def fetch() -> list[dict[str, Any]]:
            engine = _engine(context, timeout_seconds=int(intent["timeout_seconds"]))
            try:
                with engine.connect() as conn:
                    conn = conn.execution_options(isolation_level="REPEATABLE READ")
                    tx = conn.begin()
                    try:
                        table = Table(
                            table_name, MetaData(), schema=schema, autoload_with=conn
                        )
                        query = select(table)
                        partition_ids = intent.get("partition_ids")
                        if partition_ids is not None:
                            from sqlalchemy import Text
                            from sqlalchemy import cast as sql_cast

                            partition_column = str(intent["partition_column"])
                            if partition_column not in table.c:
                                raise ConnectorReadError(
                                    "PostgreSQL partition column is missing",
                                    code="PMCONN882",
                                    provider=PROVIDER,
                                )
                            query = query.where(
                                sql_cast(table.c[partition_column], Text).in_(
                                    list(cast(Sequence[str], partition_ids))
                                )
                            )
                        result = conn.execution_options(stream_results=True).execute(
                            query.limit(row_limit + 1)
                        )
                        rows: list[dict[str, Any]] = []
                        byte_count = 0
                        for row in result:
                            if len(rows) >= row_limit:
                                raise ConnectorReadError(
                                    f"PostgreSQL snapshot exceeds row_limit ({row_limit})",
                                    code="PMCONN855",
                                    provider=PROVIDER,
                                )
                            item = dict(cast(Mapping[str, Any], row._mapping))
                            byte_count += _json_bytes(item)
                            if byte_count > max_bytes:
                                raise ConnectorReadError(
                                    f"PostgreSQL snapshot exceeds max_bytes ({max_bytes})",
                                    code="PMCONN856",
                                    provider=PROVIDER,
                                )
                            rows.append(item)
                        tx.commit()
                        return rows
                    except Exception:
                        tx.rollback()
                        raise
            finally:
                engine.dispose()

        try:
            rows = await to_thread.run_sync(fetch)
        except ConnectorReadError:
            raise
        except Exception as exc:
            raise ConnectorReadError(
                "PostgreSQL read failed; connection details were redacted",
                code="PMCONN857",
                provider=PROVIDER,
            ) from exc
        chunks: list[list[dict[str, Any]]] = [
            rows[i : i + batch_size] for i in range(0, len(rows), batch_size)
        ]
        if not chunks:
            chunks = [[]]
        for index, chunk in enumerate(chunks):
            yield ReadBatch(
                records=tuple(chunk),
                batch_index=index,
                exhausted=index == len(chunks) - 1,
                metadata={
                    "table": _qualified(schema, table_name),
                    "snapshot": "repeatable_read",
                },
            )

    async def propose_cursor(
        self,
        *,
        plan: SourcePlan,
        manifest: LandingReadManifest,
        context: Mapping[str, Any],
    ) -> CursorProposal | None:
        return None


@dataclass
class LivePostgresSinkConnector:
    """Transactional PostgreSQL writes with a provisioned durable effect ledger."""

    _sessions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: dict[str, dict[str, Any]](), repr=False
    )

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SINK_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=tuple(sorted(SINK_CAPS)),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={
                "dialect": "postgresql",
                "backend": "live",
                "effect_ledger": "provisioned",
            },
            configuration_schema=deepcopy(SINK_CONFIG_SCHEMA),
        )

    async def resource_identities(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> tuple[str, ...]:
        cfg = _config(binding, _SINK_KEYS)
        schema, table = _table_parts(binding, cfg)
        timeout_seconds = _bounded_integer(
            cfg.get("timeout_seconds"),
            name="timeout_seconds",
            default=DEFAULT_TIMEOUT_SECONDS,
            maximum=MAX_TIMEOUT_SECONDS,
        )
        return await _postgres_resource_identities(
            context,
            schema=schema,
            table=table,
            timeout_seconds=timeout_seconds,
        )

    async def plan_write(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> SinkPlan:
        cfg = _config(binding, _SINK_KEYS)
        schema, table = _table_parts(binding, cfg)
        mode = str(
            cfg.get("mode")
            or binding.get("mode")
            or context.get("write_mode")
            or "append"
        )
        if mode == "merge":
            mode = "upsert"
        if mode not in {"append", "overwrite", "replace", "upsert"}:
            raise ConnectorConfigError(
                f"unsupported postgresql write mode {mode!r}",
                code="PMCONN842",
                provider=PROVIDER,
            )
        keys = cfg.get("key_columns") or ()
        if isinstance(keys, str) or not isinstance(keys, Sequence):
            raise ConnectorConfigError(
                "key_columns must be a list of column names",
                code="PMCONN858",
                provider=PROVIDER,
            )
        normalized_keys: tuple[str, ...] = tuple(
            str(key) for key in cast(Sequence[Any], keys)
        )
        if mode == "upsert" and not normalized_keys:
            raise ConnectorConfigError(
                "PostgreSQL upsert requires key_columns",
                code="PMCONN859",
                provider=PROVIDER,
            )
        effect_table_raw = cfg.get("effect_table") or DEFAULT_EFFECT_TABLE
        effect_schema, effect_table = _split_effect_table(str(effect_table_raw))
        return SinkPlan(
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            write_mode=mode,
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=_qualified(schema, table),
            secret_refs=_secret_ref_names(binding),
            metadata={
                "schema": schema,
                "table": table,
                "key_columns": list(normalized_keys),
                "effect_schema": effect_schema,
                "effect_table": effect_table,
                "timeout_seconds": _bounded_integer(
                    cfg.get("timeout_seconds"),
                    name="timeout_seconds",
                    default=DEFAULT_TIMEOUT_SECONDS,
                    maximum=MAX_TIMEOUT_SECONDS,
                ),
            },
        )

    async def plan_write_partitions(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
        partition_ids: tuple[str, ...],
    ) -> SinkPlan:
        """Plan atomic replacement of the selected partition values."""
        cfg = _config(binding, _SINK_KEYS)
        partition_column = cfg.get("partition_column")
        if not isinstance(partition_column, str) or not _IDENTIFIER.fullmatch(
            partition_column
        ):
            raise ConnectorConfigError(
                "PostgreSQL partition replacement requires a valid partition_column",
                code="PMCONN883",
                provider=PROVIDER,
            )
        normalized_ids = _normalize_partition_ids(partition_ids)
        base = await self.plan_write(binding=binding, context=context)
        metadata = dict(base.metadata)
        metadata.update(
            {
                "partition_column": partition_column,
                "partition_ids": list(normalized_ids),
            }
        )
        return SinkPlan(
            provider=base.provider,
            protocol=base.protocol,
            write_mode="partition_replace",
            required_capabilities=(WRITE_PARTITION_REPLACE, IDEMPOTENCY),
            config_fingerprint=base.config_fingerprint,
            root_ref=base.root_ref,
            secret_refs=base.secret_refs,
            metadata=metadata,
        )

    async def begin_write(
        self,
        *,
        plan: SinkPlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> WriteSession:
        cfg = _config(binding, _SINK_KEYS)
        partition_ids = context.get("etlantic.partition_ids")
        if partition_ids is not None:
            if not isinstance(partition_ids, (list, tuple)):
                raise ConnectorWriteError(
                    "PostgreSQL partition selector is invalid",
                    code="PMCONN884",
                    provider=PROVIDER,
                )
            expected_plan = await self.plan_write_partitions(
                binding=binding,
                context=context,
                partition_ids=tuple(cast(Sequence[str], partition_ids)),
            )
        else:
            expected_plan = await self.plan_write(binding=binding, context=context)
        if (
            plan != expected_plan
            or plan.config_fingerprint != fingerprint_public_config(cfg)
        ):
            raise ConnectorWriteError(
                "PostgreSQL sink plan does not match its binding",
                code="PMCONN878",
                provider=PROVIDER,
            )
        effect_id = _effect_id(context, str(plan.root_ref or ""))
        session_metadata = {
            "table": plan.root_ref,
            "effect_id": effect_id,
            "effect_schema": plan.metadata.get("effect_schema"),
            "effect_table": plan.metadata.get("effect_table"),
            "timeout_seconds": plan.metadata.get("timeout_seconds"),
        }
        self._sessions[effect_id] = {
            "plan": plan,
            "rows": [],
            "byte_count": 0,
            "context": context,
            "status": "open",
            "connection": None,
            "transaction": None,
            "engine": None,
            "receipt": None,
            "session_metadata": session_metadata,
        }
        return WriteSession(
            session_id=effect_id,
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            metadata=session_metadata,
        )

    async def write_batch(
        self, session: WriteSession, batch: Any, *, context: Mapping[str, Any]
    ) -> None:
        state = self._require(session.session_id)
        if state["status"] != "open":
            raise ConnectorWriteError(
                "PostgreSQL write session is not open",
                code="PMCONN860",
                provider=PROVIDER,
            )
        rows: list[dict[str, Any]] = state["rows"]
        new_rows: list[dict[str, Any]] = []
        if isinstance(batch, Mapping):
            new_rows = [dict(cast(Mapping[str, Any], batch))]
        elif isinstance(batch, (list, tuple)):
            for item in cast(Sequence[Any], batch):
                if not isinstance(item, Mapping):
                    raise ConnectorWriteError(
                        "PostgreSQL sinks accept records as mappings",
                        code="PMCONN861",
                        provider=PROVIDER,
                    )
                new_rows.append(dict(cast(Mapping[str, Any], item)))
        else:
            raise ConnectorWriteError(
                "PostgreSQL sinks accept records as mappings",
                code="PMCONN861",
                provider=PROVIDER,
            )
        # Keep staging bounded before any database transaction is opened.
        if len(rows) + len(new_rows) > MAX_ROW_LIMIT:
            raise ConnectorWriteError(
                f"PostgreSQL sink exceeds row limit ({MAX_ROW_LIMIT})",
                code="PMCONN862",
                provider=PROVIDER,
            )
        new_byte_count = state["byte_count"] + sum(_json_bytes(row) for row in new_rows)
        if new_byte_count > MAX_BYTE_LIMIT:
            raise ConnectorWriteError(
                f"PostgreSQL sink exceeds byte limit ({MAX_BYTE_LIMIT})",
                code="PMCONN863",
                provider=PROVIDER,
            )
        rows.extend(new_rows)
        state["byte_count"] = new_byte_count

    async def prepare(
        self, session: WriteSession, *, context: Mapping[str, Any]
    ) -> None:
        from anyio import to_thread

        await to_thread.run_sync(self._prepare_sync, session)

    def _prepare_sync(self, session: WriteSession) -> None:
        from sqlalchemy import MetaData, Table, inspect, select, text

        state = self._require(session.session_id)
        if state["status"] == "committed":
            return
        if state["status"] != "open":
            raise ConnectorWriteError(
                "PostgreSQL write session cannot be prepared",
                code="PMCONN860",
                provider=PROVIDER,
            )
        plan: SinkPlan = state["plan"]
        meta = dict(plan.metadata)
        rows: list[dict[str, Any]] = state["rows"]
        connection_context = state["context"]
        engine = _engine(
            connection_context,
            timeout_seconds=int(meta["timeout_seconds"]),
        )
        connection = engine.connect()
        transaction = connection.begin()
        try:
            # Serialize concurrent retries for the same accepted effect. The
            # database releases this lock automatically on commit or rollback.
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:effect_id, 0))"),
                {"effect_id": session.session_id},
            )
            effect_table = Table(
                str(meta["effect_table"]),
                MetaData(),
                schema=str(meta["effect_schema"]),
                autoload_with=connection,
            )
            needed = {"effect_id", "intent_fingerprint", "publication_id", "row_count"}
            if not needed.issubset(set(effect_table.c.keys())):
                raise ConnectorWriteError(
                    "PostgreSQL effect ledger lacks required columns",
                    code="PMCONN864",
                    provider=PROVIDER,
                )
            ledger_primary_key = set(
                inspect(connection)
                .get_pk_constraint(
                    str(meta["effect_table"]), schema=str(meta["effect_schema"])
                )
                .get("constrained_columns")
                or ()
            )
            ledger_uniques = [
                set(item.get("column_names") or ())
                for item in inspect(connection).get_unique_constraints(
                    str(meta["effect_table"]), schema=str(meta["effect_schema"])
                )
            ]
            if (
                ledger_primary_key != {"effect_id"}
                and {"effect_id"} not in ledger_uniques
            ):
                raise ConnectorWriteError(
                    "PostgreSQL effect ledger must uniquely constrain effect_id",
                    code="PMCONN879",
                    provider=PROVIDER,
                )
            intent_fingerprint = _intent_fingerprint(plan, rows)
            prior = (
                connection.execute(
                    select(effect_table).where(
                        effect_table.c.effect_id == session.session_id
                    )
                )
                .mappings()
                .first()
            )
            if prior is not None:
                if str(prior["intent_fingerprint"]) != intent_fingerprint:
                    raise ConnectorWriteError(
                        "PostgreSQL effect ID is already bound to different write intent",
                        code="PMCONN865",
                        provider=PROVIDER,
                    )
                transaction.rollback()
                connection.close()
                engine.dispose()
                state["status"] = "committed"
                state["receipt"] = CommitReceipt(
                    status="committed",
                    session_id=session.session_id,
                    provider=PROVIDER,
                    publication_id=str(prior["publication_id"]),
                    message="PostgreSQL effect recovered from durable ledger",
                    metadata={
                        "table": plan.root_ref,
                        "row_count": int(prior["row_count"]),
                    },
                )
                return

            target = Table(
                str(meta["table"]),
                MetaData(),
                schema=str(meta["schema"]),
                autoload_with=connection,
            )
            mode = str(plan.write_mode or "append")
            if mode == "partition_replace":
                from sqlalchemy import Text, delete
                from sqlalchemy import cast as sql_cast

                partition_column = str(meta.get("partition_column") or "")
                partition_ids = _normalize_partition_ids(
                    cast(Sequence[str], meta.get("partition_ids") or ())
                )
                if not partition_column or partition_column not in target.c:
                    raise ConnectorWriteError(
                        "PostgreSQL partition column is missing",
                        code="PMCONN885",
                        provider=PROVIDER,
                    )
                if any(
                    partition_column not in row
                    or row[partition_column] is None
                    or str(row[partition_column]) not in partition_ids
                    for row in rows
                ):
                    raise ConnectorWriteError(
                        "PostgreSQL partition replacement rows do not match the selected partitions",
                        code="PMCONN886",
                        provider=PROVIDER,
                    )
                connection.execute(
                    delete(target).where(
                        sql_cast(target.c[partition_column], Text).in_(
                            list(partition_ids)
                        )
                    )
                )
            if rows:
                supplied_columns: set[str] = {column for row in rows for column in row}
                target_columns = set(target.c.keys())
                unknown = supplied_columns - target_columns
                if unknown:
                    raise ConnectorWriteError(
                        "PostgreSQL rows contain unknown target columns: "
                        + ", ".join(sorted(unknown)),
                        code="PMCONN866",
                        provider=PROVIDER,
                    )
                if any(set(row) != set(rows[0]) for row in rows):
                    raise ConnectorWriteError(
                        "PostgreSQL rows must have identical column sets",
                        code="PMCONN867",
                        provider=PROVIDER,
                    )
                missing_required = {
                    col.name
                    for col in target.columns
                    if not col.nullable
                    and col.default is None
                    and col.server_default is None
                    and not col.primary_key
                    and col.name not in supplied_columns
                }
                if missing_required:
                    raise ConnectorWriteError(
                        "PostgreSQL rows omit required target columns: "
                        + ", ".join(sorted(missing_required)),
                        code="PMCONN868",
                        provider=PROVIDER,
                    )
            if mode in {"overwrite", "replace"}:
                from sqlalchemy import delete

                connection.execute(delete(target))
            if rows:
                if mode == "upsert":
                    from sqlalchemy.dialects.postgresql import insert

                    keys = tuple(str(key) for key in meta.get("key_columns", []))
                    if not set(keys).issubset(set(target.c.keys())):
                        raise ConnectorWriteError(
                            "PostgreSQL key_columns include unknown target columns",
                            code="PMCONN869",
                            provider=PROVIDER,
                        )
                    inspector = inspect(connection)
                    unique_constraints = [
                        set(item.get("column_names") or ())
                        for item in inspector.get_unique_constraints(
                            str(meta["table"]), schema=str(meta["schema"])
                        )
                    ]
                    primary_key = set(
                        inspector.get_pk_constraint(
                            str(meta["table"]), schema=str(meta["schema"])
                        ).get("constrained_columns")
                        or ()
                    )
                    if set(keys) not in unique_constraints and set(keys) != primary_key:
                        raise ConnectorWriteError(
                            "PostgreSQL upsert keys must match a primary or unique constraint",
                            code="PMCONN870",
                            provider=PROVIDER,
                        )
                    bind_parameters_per_row = len(rows[0])
                    rows_per_statement = _MAX_BIND_PARAMETERS // max(
                        bind_parameters_per_row, 1
                    )
                    if rows_per_statement == 0:
                        raise ConnectorWriteError(
                            "PostgreSQL upsert row exceeds the bind-parameter limit",
                            code="PMCONN888",
                            provider=PROVIDER,
                        )

                    def execute_upsert_chunk(
                        chunk: Sequence[Mapping[str, Any]],
                    ) -> None:
                        savepoint = connection.begin_nested()
                        statement = insert(target).values(list(chunk))
                        updates = {
                            column: getattr(statement.excluded, column)
                            for column in rows[0]
                            if column not in keys
                        }
                        if updates:
                            statement = statement.on_conflict_do_update(
                                index_elements=[target.c[key] for key in keys],
                                set_=updates,
                            )
                        else:
                            statement = statement.on_conflict_do_nothing(
                                index_elements=[target.c[key] for key in keys]
                            )
                        try:
                            connection.execute(statement)
                        except Exception as exc:
                            savepoint.rollback()
                            original = getattr(exc, "orig", None)
                            sqlstate = getattr(original, "sqlstate", None) or getattr(
                                original, "pgcode", None
                            )
                            diagnostic = getattr(original, "diag", None)
                            source_function = getattr(
                                diagnostic, "source_function", None
                            )
                            # PostgreSQL cannot update one conflict key twice in a
                            # single statement. Split only that chunk so duplicate
                            # keys keep their input order across statement boundaries.
                            if (
                                sqlstate != "21000"
                                or source_function != "ExecOnConflictUpdate"
                                or len(chunk) < 2
                            ):
                                raise
                            midpoint = len(chunk) // 2
                            execute_upsert_chunk(chunk[:midpoint])
                            execute_upsert_chunk(chunk[midpoint:])
                        else:
                            savepoint.commit()

                    for offset in range(0, len(rows), rows_per_statement):
                        execute_upsert_chunk(rows[offset : offset + rows_per_statement])
                else:
                    connection.execute(target.insert(), rows)

            publication_id = "pgpub-" + session.session_id.removeprefix("pgfx-")
            connection.execute(
                effect_table.insert().values(
                    effect_id=session.session_id,
                    intent_fingerprint=intent_fingerprint,
                    publication_id=publication_id,
                    row_count=len(rows),
                )
            )
            state.update(
                {
                    "status": "prepared",
                    "engine": engine,
                    "connection": connection,
                    "transaction": transaction,
                    "publication_id": publication_id,
                    "intent_fingerprint": intent_fingerprint,
                }
            )
            state["session_metadata"].update(
                {
                    "intent_fingerprint": intent_fingerprint,
                    "publication_id": publication_id,
                }
            )
        except ConnectorWriteError:
            transaction.rollback()
            connection.close()
            engine.dispose()
            raise
        except Exception as exc:
            transaction.rollback()
            connection.close()
            engine.dispose()
            raise ConnectorWriteError(
                "PostgreSQL staging failed; database details were redacted",
                code="PMCONN876",
                provider=PROVIDER,
            ) from exc

    async def commit(
        self, session: WriteSession, *, context: Mapping[str, Any]
    ) -> CommitReceipt:
        from anyio import to_thread

        return await to_thread.run_sync(self._commit_sync, session)

    def _commit_sync(self, session: WriteSession) -> CommitReceipt:
        state = self._require(session.session_id)
        if state["status"] == "committed":
            return state["receipt"]
        if state["status"] != "prepared":
            raise ConnectorWriteError(
                "PostgreSQL write must be prepared before commit",
                code="PMCONN871",
                provider=PROVIDER,
            )
        transaction = state["transaction"]
        connection = state["connection"]
        engine = state["engine"]
        try:
            transaction.commit()
        except Exception as exc:
            state["status"] = "unknown"
            raise ConnectorWriteError(
                "PostgreSQL commit acknowledgement is unknown; reconcile the effect",
                code="PMCONN872",
                provider=PROVIDER,
            ) from exc
        finally:
            connection.close()
            engine.dispose()
            state["connection"] = None
            state["transaction"] = None
            state["engine"] = None
        state["status"] = "committed"
        state["receipt"] = CommitReceipt(
            status="committed",
            session_id=session.session_id,
            provider=PROVIDER,
            publication_id=str(state["publication_id"]),
            message="PostgreSQL transaction committed",
            metadata={
                "table": state["plan"].root_ref,
                "row_count": len(state["rows"]),
                "effect_id": session.session_id,
            },
        )
        return state["receipt"]

    async def abort(
        self, session: WriteSession, *, context: Mapping[str, Any]
    ) -> CommitReceipt:
        from anyio import to_thread

        return await to_thread.run_sync(self._abort_sync, session)

    def _abort_sync(self, session: WriteSession) -> CommitReceipt:
        state = self._require(session.session_id)
        if state["status"] == "committed":
            return state["receipt"]
        if state["status"] == "unknown":
            return CommitReceipt(
                status="unknown",
                session_id=session.session_id,
                provider=PROVIDER,
                message="PostgreSQL commit outcome still requires reconciliation",
                metadata=dict(state["session_metadata"]),
            )
        connection = state.get("connection")
        engine = state.get("engine")
        try:
            if state.get("transaction") is not None:
                state["transaction"].rollback()
            state["status"] = "rolled_back"
            return CommitReceipt(
                status="rolled_back",
                session_id=session.session_id,
                provider=PROVIDER,
                message="PostgreSQL transaction rolled back",
                metadata={"effect_id": session.session_id},
            )
        except Exception:
            state["status"] = "unknown"
            return CommitReceipt(
                status="unknown",
                session_id=session.session_id,
                provider=PROVIDER,
                message="PostgreSQL rollback could not be confirmed",
                metadata=dict(state["session_metadata"]),
            )
        finally:
            if connection is not None:
                connection.close()
            if engine is not None:
                engine.dispose()

    async def reconcile(
        self, receipt: CommitReceipt, *, context: Mapping[str, Any]
    ) -> ReconciliationResult:
        from anyio import to_thread
        from sqlalchemy import MetaData, Table, select, text

        effect_id = str(
            (receipt.metadata or {}).get("effect_id") or receipt.session_id or ""
        )
        if not effect_id:
            return ReconciliationResult(
                status="unknown", message="missing effect identity"
            )
        try:
            local = self._sessions.get(effect_id, {})
            plan = local.get("plan")
            if plan is not None:
                meta = dict(plan.metadata)
            else:
                metadata = dict(receipt.metadata or {})
                effect_schema = metadata.get("effect_schema")
                effect_table = metadata.get("effect_table")
                if not effect_schema or not effect_table:
                    return ReconciliationResult(
                        status="unknown",
                        message="effect ledger reference is unavailable for reconciliation",
                    )
                meta = {
                    "effect_schema": effect_schema,
                    "effect_table": effect_table,
                }

            def lookup() -> tuple[bool, Any]:
                engine = _engine(
                    context,
                    timeout_seconds=int(
                        meta.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
                    ),
                )
                try:
                    with engine.connect() as connection:
                        # The writer holds this lock through COMMIT/rollback.
                        # An invisible ledger row cannot establish rollback
                        # while that transaction is still able to commit.
                        connection = connection.execution_options(
                            isolation_level="READ COMMITTED"
                        )
                        settled = connection.execute(
                            text(
                                "SELECT pg_try_advisory_xact_lock("
                                "hashtextextended(:effect_id, 0))"
                            ),
                            {"effect_id": effect_id},
                        ).scalar_one()
                        if not settled:
                            return False, None
                        # Read in a separate statement so the snapshot follows
                        # acquisition of the effect lock, even if a writer
                        # committed just as reconciliation began.
                        table = Table(
                            str(meta["effect_table"]),
                            MetaData(),
                            schema=str(meta["effect_schema"]),
                            autoload_with=connection,
                        )
                        return True, (
                            connection.execute(
                                select(table).where(table.c.effect_id == effect_id)
                            )
                            .mappings()
                            .first()
                        )
                finally:
                    engine.dispose()

            settled, row = await to_thread.run_sync(lookup)
        except Exception:
            return ReconciliationResult(
                status="unknown",
                message="PostgreSQL effect ledger could not be queried",
            )
        if not settled:
            return ReconciliationResult(
                status="unknown",
                message="PostgreSQL effect transaction is still active",
                metadata={"effect_id": effect_id},
            )
        if row is None:
            return ReconciliationResult(
                status="rolled_back",
                message="effect is absent from the durable PostgreSQL ledger",
                metadata={"effect_id": effect_id},
            )
        expected = local.get("intent_fingerprint") or dict(receipt.metadata or {}).get(
            "intent_fingerprint"
        )
        if expected is not None and str(row["intent_fingerprint"]) != str(expected):
            return ReconciliationResult(
                status="unknown",
                message="effect ledger intent does not match the active attempt",
            )
        return ReconciliationResult(
            status="committed",
            publication_id=str(row["publication_id"]),
            message="effect confirmed in durable PostgreSQL ledger",
            metadata={
                "effect_id": effect_id,
                "effect_schema": meta["effect_schema"],
                "effect_table": meta["effect_table"],
                "intent_fingerprint": str(row["intent_fingerprint"]),
                "row_count": int(row["row_count"]),
            },
        )

    async def cleanup(
        self, receipt: CommitReceipt, *, context: Mapping[str, Any]
    ) -> CleanupReceipt:
        return CleanupReceipt(status="skipped", message="no cleanup is required")

    def _require(self, session_id: str) -> dict[str, Any]:
        state = self._sessions.get(session_id)
        if state is None:
            raise ConnectorWriteError(
                "unknown PostgreSQL write session",
                code="PMCONN843",
                provider=PROVIDER,
            )
        return state


@dataclass
class LivePostgresStorageConnector:
    """Read-only schema and bounded statistics inspection for PostgreSQL."""

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=STORAGE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=(SOURCE_SCHEMA_DISCOVERY, SOURCE_STATISTICS_BOUNDED),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={
                "dialect": "postgresql",
                "backend": "live",
                "read_only_inspection": True,
            },
            configuration_schema=deepcopy(STORAGE_CONFIG_SCHEMA),
        )

    async def inspect_schema(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> SchemaInspection:
        from anyio import to_thread
        from sqlalchemy import MetaData, Table, text

        cfg = _config(binding, _STORAGE_KEYS)
        schema, table_name = _table_parts(binding, cfg)

        def inspect_target() -> SchemaInspection:
            engine = _engine(
                context,
                timeout_seconds=_bounded_integer(
                    cfg.get("timeout_seconds"),
                    name="timeout_seconds",
                    default=DEFAULT_TIMEOUT_SECONDS,
                    maximum=MAX_TIMEOUT_SECONDS,
                ),
            )
            try:
                with engine.connect() as connection:
                    table = Table(
                        table_name, MetaData(), schema=schema, autoload_with=connection
                    )
                    fields = tuple(
                        {
                            "name": column.name,
                            "type": str(column.type),
                            "nullable": bool(column.nullable),
                            "primary_key": bool(column.primary_key),
                        }
                        for column in table.columns
                    )
                    estimate = connection.execute(
                        text(
                            "SELECT GREATEST(c.reltuples, 0)::bigint "
                            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE n.nspname=:schema AND c.relname=:table"
                        ),
                        {"schema": schema, "table": table_name},
                    ).scalar_one_or_none()
                    return SchemaInspection(
                        provider=PROVIDER,
                        fields=fields,
                        row_estimate=int(estimate) if estimate is not None else None,
                        metadata={
                            "table": _qualified(schema, table_name),
                            "inspection": "read_only",
                        },
                    )
            finally:
                engine.dispose()

        try:
            return await to_thread.run_sync(inspect_target)
        except Exception as exc:
            if isinstance(exc, ConnectorConfigError):
                raise
            raise ConnectorReadError(
                "PostgreSQL schema inspection failed; connection details were redacted",
                code="PMCONN873",
                provider=PROVIDER,
            ) from exc


def _split_effect_table(value: str) -> tuple[str, str]:
    parts = value.split(".")
    if len(parts) == 1:
        schema, table = "public", parts[0]
    elif len(parts) == 2:
        schema, table = parts
    else:
        schema, table = "", ""
    if (
        not schema
        or not table
        or not _IDENTIFIER.fullmatch(schema)
        or not _IDENTIFIER.fullmatch(table)
    ):
        raise ConnectorConfigError(
            "effect_table must be table or schema.table",
            code="PMCONN874",
            provider=PROVIDER,
        )
    return schema, table


def _effect_id(context: Mapping[str, Any], table: str) -> str:
    supplied = context.get("effect_id")
    run_id = context.get("run_id")
    if supplied is not None:
        raw = str(supplied)
    elif run_id is not None:
        raw = f"{run_id}:{context.get('node') or context.get('binding') or table}"
    else:
        raw = uuid.uuid4().hex
    return "pgfx-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _intent_fingerprint(plan: SinkPlan, rows: Sequence[Mapping[str, Any]]) -> str:
    payload = {
        "provider": PROVIDER,
        "root_ref": plan.root_ref,
        "write_mode": plan.write_mode,
        "config_fingerprint": plan.config_fingerprint,
        "metadata": dict(plan.metadata),
        "rows": list(rows),
    }
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


__all__ = [
    "LivePostgresSinkConnector",
    "LivePostgresSourceConnector",
    "LivePostgresStorageConnector",
]
