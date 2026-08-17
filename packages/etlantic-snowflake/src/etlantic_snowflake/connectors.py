"""Snowflake source / sink / storage connectors (fake by default)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from etlantic.connectors.capabilities import (
    IDEMPOTENCY,
    PUBLICATION_ATOMIC,
    RECONCILIATION,
    SOURCE_BATCH_SNAPSHOT,
    SOURCE_SCHEMA_DISCOVERY,
    SOURCE_STATISTICS_BOUNDED,
    TRANSACTIONS,
    WRITE_APPEND,
    WRITE_MERGE,
    WRITE_OVERWRITE,
)
from etlantic.connectors.errors import ConnectorConfigError, ConnectorWriteError
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
from etlantic_snowflake.fake import FakeSnowflakeConnection, snowflake_sdk_available

PROVIDER = "snowflake"
PACKAGE_VERSION = "0.46.0"

SOURCE_CAPS = frozenset(
    {
        SOURCE_BATCH_SNAPSHOT,
        SOURCE_SCHEMA_DISCOVERY,
        SOURCE_STATISTICS_BOUNDED,
        IDEMPOTENCY,
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
    }
)


def _public_config(binding: Mapping[str, Any]) -> dict[str, Any]:
    raw = binding.get("config")
    if isinstance(raw, dict):
        return dict(raw)
    keys = ("table", "schema", "database", "mode", "warehouse")
    return {k: binding[k] for k in keys if k in binding and binding[k] is not None}


def _table_name(binding: Mapping[str, Any], cfg: Mapping[str, Any]) -> str:
    table = str(cfg.get("table") or binding.get("location") or "")
    if not table:
        raise ConnectorConfigError(
            "snowflake binding requires table",
            code="PMCONN831",
            provider=PROVIDER,
        )
    schema = cfg.get("schema")
    database = cfg.get("database")
    parts = [p for p in (database, schema, table) if p]
    return ".".join(str(p) for p in parts)


@dataclass
class SnowflakeSourceConnector:
    connection: FakeSnowflakeConnection = field(default_factory=FakeSnowflakeConnection)

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=tuple(sorted(SOURCE_CAPS)),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={
                "fake": not snowflake_sdk_available(),
                "autocommit": False,
            },
        )

    async def plan_read(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SourcePlan:
        cfg = _public_config(binding)
        table = _table_name(binding, cfg)
        return SourcePlan(
            provider=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            mode="snapshot",
            identity_scheme="snowflake_query_id/1",
            listing_intent={"table": table},
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=table,
            secret_refs=tuple(
                sorted(str(k) for k in (binding.get("secret_refs") or {}))
            ),
        )

    async def read_batches(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AsyncIterator[ReadBatch]:
        table = str(plan.listing_intent.get("table") or "")
        result = self.connection.select(table)
        yield ReadBatch(
            records=result.rows,
            batch_index=0,
            exhausted=True,
            metadata={"table": table, "query_id": result.query_id},
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
class SnowflakeSinkConnector:
    connection: FakeSnowflakeConnection = field(default_factory=FakeSnowflakeConnection)
    _sessions: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SINK_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=tuple(sorted(SINK_CAPS)),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={
                "fake": not snowflake_sdk_available(),
                "autocommit": False,
                "evidence": "query_id",
            },
        )

    async def plan_write(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SinkPlan:
        cfg = _public_config(binding)
        table = _table_name(binding, cfg)
        mode = str(cfg.get("mode") or binding.get("mode") or "append")
        if mode not in {"append", "overwrite", "replace", "merge"}:
            raise ConnectorConfigError(
                f"unsupported snowflake write mode {mode!r}",
                code="PMCONN832",
                provider=PROVIDER,
            )
        return SinkPlan(
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            write_mode=mode,
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=table,
            secret_refs=tuple(
                sorted(str(k) for k in (binding.get("secret_refs") or {}))
            ),
            metadata={"table": table},
        )

    async def begin_write(
        self,
        *,
        plan: SinkPlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> WriteSession:
        if self.connection.autocommit:
            raise ConnectorWriteError(
                "snowflake transactional path requires autocommit=False",
                code="PMCONN833",
                provider=PROVIDER,
            )
        session_id = f"sf-{uuid.uuid4().hex[:12]}"
        self._sessions[session_id] = {
            "table": str(plan.metadata.get("table") or plan.root_ref),
            "mode": plan.write_mode or "append",
            "rows": [],
            "query_ids": [],
            "status": "open",
        }
        return WriteSession(
            session_id=session_id,
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            metadata={"table": plan.metadata.get("table"), "autocommit": False},
        )

    async def write_batch(
        self,
        session: WriteSession,
        batch: Any,
        *,
        context: Mapping[str, Any],
    ) -> None:
        state = self._require(session.session_id)
        if isinstance(batch, Mapping):
            state["rows"].append(dict(batch))
        elif isinstance(batch, (list, tuple)):
            for item in batch:
                state["rows"].append(
                    dict(item) if isinstance(item, Mapping) else {"value": item}
                )
        else:
            state["rows"].append({"value": batch})

    async def prepare(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> None:
        state = self._require(session.session_id)
        result = self.connection.execute(
            f"STAGE {state['mode']} INTO {state['table']}",
            table=str(state["table"]),
            rows=list(state["rows"]),
            operation=str(state["mode"]),
        )
        state["query_ids"].append(result.query_id)
        state["prepared"] = True

    async def commit(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        state = self._require(session.session_id)
        if not state.get("prepared"):
            await self.prepare(session, context=context)
        query_ids = self.connection.commit()
        # Prefer session-staged ids; fall back to connection commit list.
        evidence_ids = list(state["query_ids"]) or query_ids
        primary = evidence_ids[-1] if evidence_ids else None
        state["status"] = "committed"
        return CommitReceipt(
            status="committed",
            session_id=session.session_id,
            provider=PROVIDER,
            publication_id=primary,
            message="snowflake transaction committed",
            metadata={
                "table": state["table"],
                "query_id": primary,
                "query_ids": evidence_ids,
                "autocommit": False,
            },
        )

    async def abort(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        state = self._require(session.session_id)
        self.connection.rollback()
        state["status"] = "aborted"
        return CommitReceipt(
            status="rolled_back",
            session_id=session.session_id,
            provider=PROVIDER,
            message="snowflake transaction rolled back",
            metadata={
                "table": state["table"],
                "query_ids": list(state["query_ids"]),
                "autocommit": False,
            },
        )

    async def reconcile(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> ReconciliationResult:
        query_id = receipt.publication_id or (receipt.metadata or {}).get("query_id")
        if not query_id:
            return ReconciliationResult(status="unknown", message="missing query_id")
        found = self.connection.lookup_query(str(query_id))
        if found is None:
            return ReconciliationResult(
                status="rolled_back",
                message="query_id not found",
                metadata={"query_id": query_id},
            )
        if str(query_id) in self.connection._pending_queries:
            return ReconciliationResult(
                status="unknown",
                publication_id=str(query_id),
                message="query still pending in open transaction",
                metadata={"query_id": query_id},
            )
        return ReconciliationResult(
            status="committed",
            publication_id=str(query_id),
            message="query_id found in committed history",
            metadata={"query_id": query_id},
        )

    async def cleanup(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> CleanupReceipt:
        return CleanupReceipt(status="skipped", message="no cleanup for snowflake fake")

    def _require(self, session_id: str) -> dict[str, Any]:
        state = self._sessions.get(session_id)
        if state is None:
            raise ConnectorWriteError(
                f"unknown snowflake session {session_id!r}",
                code="PMCONN834",
                provider=PROVIDER,
            )
        return state


@dataclass
class SnowflakeStorageConnector:
    connection: FakeSnowflakeConnection = field(default_factory=FakeSnowflakeConnection)

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=STORAGE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=(SOURCE_SCHEMA_DISCOVERY, SOURCE_STATISTICS_BOUNDED),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"fake": not snowflake_sdk_available()},
        )

    async def inspect_schema(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SchemaInspection:
        cfg = _public_config(binding)
        table = _table_name(binding, cfg)
        rows = self.connection.tables.get(table, [])
        fields: tuple[dict[str, Any], ...] = ()
        if rows:
            fields = tuple(
                {"name": k, "type": type(v).__name__} for k, v in rows[0].items()
            )
        return SchemaInspection(
            provider=PROVIDER,
            fields=fields,
            row_estimate=len(rows),
            metadata={"table": table},
        )


def create_source() -> SnowflakeSourceConnector:
    return SnowflakeSourceConnector()


def create_sink() -> SnowflakeSinkConnector:
    return SnowflakeSinkConnector()


def create_storage() -> SnowflakeStorageConnector:
    return SnowflakeStorageConnector()


__all__ = [
    "SnowflakeSinkConnector",
    "SnowflakeSourceConnector",
    "SnowflakeStorageConnector",
    "create_sink",
    "create_source",
    "create_storage",
]
