"""Iceberg source / sink / storage connectors (fake catalog by default)."""

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
    SOURCE_PARTITIONED,
    SOURCE_SCHEMA_DISCOVERY,
    WRITE_APPEND,
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
from etlantic_iceberg.fake import FakeIcebergCatalog, pyiceberg_available

PROVIDER = "iceberg"
PACKAGE_VERSION = "0.46.0"

SOURCE_CAPS = frozenset(
    {
        SOURCE_BATCH_SNAPSHOT,
        SOURCE_PARTITIONED,
        SOURCE_SCHEMA_DISCOVERY,
        IDEMPOTENCY,
    }
)
SINK_CAPS = frozenset(
    {
        WRITE_APPEND,
        WRITE_OVERWRITE,
        PUBLICATION_ATOMIC,
        RECONCILIATION,
        IDEMPOTENCY,
    }
)


def _public_config(binding: Mapping[str, Any]) -> dict[str, Any]:
    raw = binding.get("config")
    if isinstance(raw, dict):
        return dict(raw)
    keys = ("table", "namespace", "mode", "identifier")
    return {k: binding[k] for k in keys if k in binding and binding[k] is not None}


def _table_id(binding: Mapping[str, Any], cfg: Mapping[str, Any]) -> str:
    ident = cfg.get("identifier") or binding.get("location")
    if ident:
        return str(ident)
    ns = str(cfg.get("namespace") or "default")
    table = str(cfg.get("table") or "")
    if not table:
        raise ConnectorConfigError(
            "iceberg binding requires table or identifier",
            code="PMCONN821",
            provider=PROVIDER,
        )
    return f"{ns}.{table}"


@dataclass
class IcebergSourceConnector:
    catalog: FakeIcebergCatalog = field(default_factory=FakeIcebergCatalog)

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=tuple(sorted(SOURCE_CAPS)),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={
                "fake": not pyiceberg_available(),
                "publication_identity": "snapshot_id",
            },
        )

    async def plan_read(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SourcePlan:
        cfg = _public_config(binding)
        table_id = _table_id(binding, cfg)
        return SourcePlan(
            provider=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            mode="snapshot",
            identity_scheme="iceberg_snapshot_id/1",
            listing_intent={"table": table_id},
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=table_id,
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
        table_id = str(plan.listing_intent.get("table") or "")
        table = self.catalog.tables.get(table_id)
        rows = table.current_rows if table else ()
        yield ReadBatch(
            records=rows,
            batch_index=0,
            exhausted=True,
            metadata={
                "table": table_id,
                "snapshot_id": table.current_snapshot_id if table else None,
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
class IcebergSinkConnector:
    catalog: FakeIcebergCatalog = field(default_factory=FakeIcebergCatalog)
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
                "fake": not pyiceberg_available(),
                "publication_identity": "snapshot_id",
            },
        )

    async def plan_write(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SinkPlan:
        cfg = _public_config(binding)
        table_id = _table_id(binding, cfg)
        mode = str(cfg.get("mode") or binding.get("mode") or "append")
        if mode not in {"append", "overwrite"}:
            raise ConnectorConfigError(
                f"unsupported iceberg write mode {mode!r}",
                code="PMCONN822",
                provider=PROVIDER,
            )
        return SinkPlan(
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            write_mode=mode,
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=table_id,
            secret_refs=tuple(
                sorted(str(k) for k in (binding.get("secret_refs") or {}))
            ),
            metadata={"table": table_id},
        )

    async def begin_write(
        self,
        *,
        plan: SinkPlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> WriteSession:
        table_id = str(plan.metadata.get("table") or plan.root_ref)
        self.catalog.ensure_table(table_id)
        session_id = f"iceberg-{uuid.uuid4().hex[:12]}"
        self._sessions[session_id] = {
            "table": table_id,
            "mode": plan.write_mode or "append",
            "rows": [],
            "staged_snapshot_id": None,
            "status": "open",
        }
        return WriteSession(
            session_id=session_id,
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            metadata={"table": table_id},
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
        # Staging barrier: rows held in session until commit creates snapshot.
        state = self._require(session.session_id)
        state["prepared"] = True

    async def commit(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        state = self._require(session.session_id)
        table_id = str(state["table"])
        mode = str(state["mode"])
        rows = list(state["rows"])
        if mode == "overwrite":
            snap = self.catalog.overwrite(table_id, rows)
        else:
            snap = self.catalog.append(table_id, rows)
        # Clear staging so a later abort cannot roll back the published snapshot.
        state["staged_snapshot_id"] = None
        state["published_snapshot_id"] = snap.snapshot_id
        state["status"] = "committed"
        # Snapshot id is the publication identity.
        return CommitReceipt(
            status="committed",
            session_id=session.session_id,
            provider=PROVIDER,
            publication_id=str(snap.snapshot_id),
            message="iceberg snapshot committed",
            metadata={
                "table": table_id,
                "snapshot_id": snap.snapshot_id,
                "operation": snap.operation,
                "parent_id": snap.parent_id,
            },
        )

    async def abort(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        state = self._require(session.session_id)
        # Abort only uncommitted staging — never roll back a published snapshot.
        if state.get("status") == "committed":
            return CommitReceipt(
                status="committed",
                session_id=session.session_id,
                provider=PROVIDER,
                publication_id=(
                    str(state["published_snapshot_id"])
                    if state.get("published_snapshot_id") is not None
                    else None
                ),
                message="iceberg abort ignored after successful commit",
                metadata={
                    "table": state["table"],
                    "snapshot_id": state.get("published_snapshot_id"),
                },
            )
        staged = state.get("staged_snapshot_id")
        if staged is not None:
            self.catalog.rollback(str(state["table"]), int(staged))
        state["rows"] = []
        state["status"] = "aborted"
        return CommitReceipt(
            status="rolled_back",
            session_id=session.session_id,
            provider=PROVIDER,
            message="iceberg write aborted",
            metadata={"table": state["table"]},
        )

    async def reconcile(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> ReconciliationResult:
        meta = dict(receipt.metadata)
        table_id = str(meta.get("table") or context.get("table") or "")
        snap_raw = meta.get("snapshot_id") or receipt.publication_id
        if not table_id or snap_raw is None:
            return ReconciliationResult(status="unknown", message="missing evidence")
        snap = self.catalog.get_snapshot(table_id, int(snap_raw))
        table = self.catalog.tables.get(table_id)
        if snap is None:
            return ReconciliationResult(
                status="rolled_back",
                message="snapshot not found",
                metadata=meta,
            )
        if table and table.current_snapshot_id == snap.snapshot_id:
            return ReconciliationResult(
                status="committed",
                publication_id=str(snap.snapshot_id),
                message="current snapshot matches",
                metadata=meta,
            )
        return ReconciliationResult(
            status="committed",
            publication_id=str(snap.snapshot_id),
            message="snapshot exists in history",
            metadata=meta,
        )

    async def cleanup(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> CleanupReceipt:
        return CleanupReceipt(status="skipped", message="no cleanup for iceberg fake")

    def _require(self, session_id: str) -> dict[str, Any]:
        state = self._sessions.get(session_id)
        if state is None:
            raise ConnectorWriteError(
                f"unknown iceberg session {session_id!r}",
                code="PMCONN823",
                provider=PROVIDER,
            )
        return state


@dataclass
class IcebergStorageConnector:
    catalog: FakeIcebergCatalog = field(default_factory=FakeIcebergCatalog)

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=STORAGE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=(SOURCE_SCHEMA_DISCOVERY,),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"fake": not pyiceberg_available()},
        )

    async def inspect_schema(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SchemaInspection:
        cfg = _public_config(binding)
        table_id = _table_id(binding, cfg)
        table = self.catalog.tables.get(table_id)
        fields = table.schema_fields if table else ()
        if table and not fields and table.current_rows:
            sample = table.current_rows[0]
            fields = tuple(
                {"name": k, "type": type(v).__name__} for k, v in sample.items()
            )
        return SchemaInspection(
            provider=PROVIDER,
            fields=tuple(fields),
            row_estimate=len(table.current_rows) if table else 0,
            metadata={
                "table": table_id,
                "snapshot_id": table.current_snapshot_id if table else None,
            },
        )


def create_source() -> IcebergSourceConnector:
    return IcebergSourceConnector()


def create_sink() -> IcebergSinkConnector:
    return IcebergSinkConnector()


def create_storage() -> IcebergStorageConnector:
    return IcebergStorageConnector()


__all__ = [
    "IcebergSinkConnector",
    "IcebergSourceConnector",
    "IcebergStorageConnector",
    "create_sink",
    "create_source",
    "create_storage",
]
