"""PostgreSQL source/sink connectors for etlantic-sql (fake/sqlite CI path)."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
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

PROVIDER = "postgresql"
PACKAGE_VERSION = "0.41.0"

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
    keys = ("table", "schema", "mode", "url")
    return {k: binding[k] for k in keys if k in binding and binding[k] is not None}


def _table_name(binding: Mapping[str, Any], cfg: Mapping[str, Any]) -> str:
    table = str(cfg.get("table") or binding.get("location") or "")
    if not table:
        raise ConnectorConfigError(
            "postgresql binding requires table",
            code="PMCONN841",
            provider=PROVIDER,
        )
    schema = cfg.get("schema")
    if schema:
        return f"{schema}.{table}"
    return table


@dataclass
class FakePostgresConnection:
    """SQLite-backed transactional fake for CI without a live Postgres.

    Mirrors autocommit-off semantics: DML is held until commit/rollback.
    Pending query/op ids move to committed only on ``commit()``; ``rollback()``
    clears pending so reconciliation cannot treat aborted work as committed.
    """

    conn: sqlite3.Connection = field(
        default_factory=lambda: sqlite3.connect(":memory:")
    )
    _pending_ops: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _committed_ops: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _query_seq: int = 0

    def __post_init__(self) -> None:
        self.conn.isolation_level = None  # manual BEGIN/COMMIT
        self.conn.execute("BEGIN")
        self.conn.row_factory = sqlite3.Row

    def ensure_table(self, table: str, columns: Sequence[str] | None = None) -> None:
        cols = columns or ("id", "payload")
        col_sql = ", ".join(f'"{c}" TEXT' for c in cols)
        # SQLite cannot use schema.table; flatten.
        safe = table.replace(".", "_")
        self.conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{safe}" ({col_sql}, PRIMARY KEY ("{cols[0]}"))'
        )

    def begin(self) -> None:
        self.conn.execute("BEGIN")

    def execute_write(
        self,
        *,
        table: str,
        rows: list[dict[str, Any]],
        mode: str,
    ) -> str:
        self._query_seq += 1
        query_id = f"pgqid-{self._query_seq:08d}"
        safe = table.replace(".", "_")
        if not rows:
            self._pending_ops[query_id] = {
                "query_id": query_id,
                "table": table,
                "mode": mode,
            }
            return query_id
        cols = list(rows[0].keys())
        self.ensure_table(table, cols)
        if mode in {"overwrite", "replace"}:
            self.conn.execute(f'DELETE FROM "{safe}"')
        for row in rows:
            placeholders = ", ".join("?" for _ in cols)
            col_list = ", ".join(f'"{c}"' for c in cols)
            values = [row.get(c) for c in cols]
            if mode == "merge":
                updates = ", ".join(f'"{c}"=excluded."{c}"' for c in cols[1:])
                sql = (
                    f'INSERT INTO "{safe}" ({col_list}) VALUES ({placeholders}) '
                    f'ON CONFLICT("{cols[0]}") DO UPDATE SET {updates}'
                    if len(cols) > 1
                    else f'INSERT OR REPLACE INTO "{safe}" ({col_list}) VALUES ({placeholders})'
                )
            else:
                sql = f'INSERT INTO "{safe}" ({col_list}) VALUES ({placeholders})'
            self.conn.execute(sql, values)
        self._pending_ops[query_id] = {
            "query_id": query_id,
            "table": table,
            "mode": mode,
            "rows": len(rows),
        }
        return query_id

    def select(self, table: str) -> tuple[dict[str, Any], ...]:
        safe = table.replace(".", "_")
        try:
            cur = self.conn.execute(f'SELECT * FROM "{safe}"')
        except sqlite3.OperationalError:
            return ()
        return tuple(dict(r) for r in cur.fetchall())

    def commit(self) -> None:
        self.conn.execute("COMMIT")
        self._committed_ops.update(self._pending_ops)
        self._pending_ops.clear()
        self.conn.execute("BEGIN")

    def rollback(self) -> None:
        self.conn.execute("ROLLBACK")
        self._pending_ops.clear()
        self.conn.execute("BEGIN")

    def lookup_query(self, query_id: str) -> dict[str, Any] | None:
        return self._committed_ops.get(query_id) or self._pending_ops.get(query_id)


@dataclass
class PostgresSourceConnector:
    """Bounded reads against PostgreSQL (sqlite fake in CI)."""

    connection: FakePostgresConnection = field(default_factory=FakePostgresConnection)

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=tuple(sorted(SOURCE_CAPS)),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"ci_backend": "sqlite", "dialect": "postgresql"},
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
            identity_scheme="postgresql_query_id/1",
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
        rows = self.connection.select(table)
        yield ReadBatch(
            records=rows,
            batch_index=0,
            exhausted=True,
            metadata={"table": table},
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
class PostgresSinkConnector:
    """Transactional sink with commit/rollback and query-id evidence."""

    connection: FakePostgresConnection = field(default_factory=FakePostgresConnection)
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
                "ci_backend": "sqlite",
                "dialect": "postgresql",
                "merge": "ON CONFLICT",
                "transactions": True,
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
                f"unsupported postgresql write mode {mode!r}",
                code="PMCONN842",
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
        session_id = f"pg-{uuid.uuid4().hex[:12]}"
        self._sessions[session_id] = {
            "table": str(plan.metadata.get("table") or plan.root_ref),
            "mode": plan.write_mode or "append",
            "rows": [],
            "query_id": None,
            "status": "open",
        }
        return WriteSession(
            session_id=session_id,
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            metadata={"table": plan.metadata.get("table"), "transactions": True},
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
                    dict(item) if isinstance(item, Mapping) else {"value": str(item)}
                )
        else:
            state["rows"].append({"value": str(batch)})

    async def prepare(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> None:
        state = self._require(session.session_id)
        query_id = self.connection.execute_write(
            table=str(state["table"]),
            rows=list(state["rows"]),
            mode=str(state["mode"]),
        )
        state["query_id"] = query_id
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
        self.connection.commit()
        state["status"] = "committed"
        query_id = str(state["query_id"])
        return CommitReceipt(
            status="committed",
            session_id=session.session_id,
            provider=PROVIDER,
            publication_id=query_id,
            message="postgresql transaction committed",
            metadata={
                "table": state["table"],
                "query_id": query_id,
                "transactions": True,
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
            message="postgresql transaction rolled back",
            metadata={"table": state["table"], "query_id": state.get("query_id")},
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
        if str(query_id) in self.connection._pending_ops:
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
        return CleanupReceipt(
            status="skipped", message="no cleanup for postgresql fake"
        )

    def _require(self, session_id: str) -> dict[str, Any]:
        state = self._sessions.get(session_id)
        if state is None:
            raise ConnectorWriteError(
                f"unknown postgresql session {session_id!r}",
                code="PMCONN843",
                provider=PROVIDER,
            )
        return state


@dataclass
class PostgresStorageConnector:
    connection: FakePostgresConnection = field(default_factory=FakePostgresConnection)

    def info(self) -> ConnectorInfo:
        from etlantic.connectors.models import STORAGE_PROTOCOL

        return ConnectorInfo(
            name=PROVIDER,
            protocol=STORAGE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=(SOURCE_SCHEMA_DISCOVERY, SOURCE_STATISTICS_BOUNDED),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"ci_backend": "sqlite"},
        )

    async def inspect_schema(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SchemaInspection:
        cfg = _public_config(binding)
        table = _table_name(binding, cfg)
        rows = self.connection.select(table)
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


def create_source() -> PostgresSourceConnector:
    """Entry-point factory for ``etlantic.source_connectors`` (postgresql)."""
    return PostgresSourceConnector()


def create_sink() -> PostgresSinkConnector:
    """Entry-point factory for ``etlantic.sink_connectors`` (postgresql)."""
    return PostgresSinkConnector()


def create_storage() -> PostgresStorageConnector:
    """Entry-point factory for ``etlantic.storage_connectors`` (postgresql)."""
    return PostgresStorageConnector()


__all__ = [
    "FakePostgresConnection",
    "PostgresSinkConnector",
    "PostgresSourceConnector",
    "PostgresStorageConnector",
    "create_sink",
    "create_source",
    "create_storage",
]
