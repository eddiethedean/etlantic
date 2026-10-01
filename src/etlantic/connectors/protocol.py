"""Runtime-checkable source, sink, and storage connector protocols."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any, Protocol, runtime_checkable

from etlantic.connectors.models import (
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
)

SOURCE_PROTOCOL = "etlantic.source/1"
SINK_PROTOCOL = "etlantic.sink/1"
STORAGE_PROTOCOL = "etlantic.storage/1"


@runtime_checkable
class SourceConnector(Protocol):
    """Plan and perform bounded reads (``etlantic.source/1``)."""

    def info(self) -> ConnectorInfo:
        """Return static connector identity and capabilities."""
        ...

    async def plan_read(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SourcePlan:
        """Build a static source plan without live listing."""
        ...

    def read_batches(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AsyncIterator[ReadBatch]:
        """Yield bounded read batches for a run."""
        ...

    async def propose_cursor(
        self,
        *,
        plan: SourcePlan,
        manifest: LandingReadManifest,
        context: Mapping[str, Any],
    ) -> CursorProposal | None:
        """Stage a cursor/ledger proposal before publication commit."""
        ...


@runtime_checkable
class PartitionedSourceConnector(SourceConnector, Protocol):
    """Source connector that can restrict extraction to opaque partition ids."""

    async def plan_read_partitions(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
        partition_ids: tuple[str, ...],
    ) -> SourcePlan:
        """Plan a bounded read of only the selected partitions."""
        ...


@runtime_checkable
class SinkConnector(Protocol):
    """Stage, commit, abort, and reconcile writes (``etlantic.sink/1``)."""

    def info(self) -> ConnectorInfo:
        """Return static connector identity and capabilities."""
        ...

    async def plan_write(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SinkPlan:
        """Build a static sink plan without live writes."""
        ...

    async def begin_write(
        self,
        *,
        plan: SinkPlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> WriteSession:
        """Open a staged write session."""
        ...

    async def write_batch(
        self,
        session: WriteSession,
        batch: Any,
        *,
        context: Mapping[str, Any],
    ) -> None:
        """Stage one batch into the open session."""
        ...

    async def prepare(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> None:
        """Prepare publication (optional staging barrier)."""
        ...

    async def commit(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        """Commit publication; status is committed|rolled_back|unknown."""
        ...

    async def abort(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        """Abort the session and discard staged work."""
        ...

    async def reconcile(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> ReconciliationResult:
        """Resolve an unknown publication outcome when supported."""
        ...

    async def cleanup(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> CleanupReceipt:
        """Post-commit cleanup when supported."""
        ...


@runtime_checkable
class PartitionedSinkConnector(SinkConnector, Protocol):
    """Sink connector that atomically replaces or repairs selected partitions."""

    async def plan_write_partitions(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
        partition_ids: tuple[str, ...],
    ) -> SinkPlan:
        """Plan a bounded, idempotent partition publication."""
        ...


@runtime_checkable
class StorageConnector(Protocol):
    """Object/table storage primitives used by connectors (``etlantic.storage/1``)."""

    def info(self) -> ConnectorInfo:
        """Return static connector identity and capabilities."""
        ...

    async def inspect_schema(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SchemaInspection:
        """Bounded, row-free schema inspection."""
        ...


@runtime_checkable
class ResourceIdentityConnector(Protocol):
    """Optional connector contract for runtime overlap detection.

    Returned values are opaque equality tokens. Connectors must not include
    credentials or raw resource names; the runtime keeps tokens in memory and
    rejects a write when a source and sink resolve to the same identity.
    """

    async def resource_identities(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> tuple[str, ...]:
        """Return opaque identities for the bound resource and its aliases."""
        ...


__all__ = [
    "SINK_PROTOCOL",
    "SOURCE_PROTOCOL",
    "STORAGE_PROTOCOL",
    "PartitionedSinkConnector",
    "PartitionedSourceConnector",
    "ResourceIdentityConnector",
    "SinkConnector",
    "SourceConnector",
    "StorageConnector",
]
