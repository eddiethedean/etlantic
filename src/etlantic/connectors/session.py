"""Run-scoped publication barrier coordinating sink commit and source ledger."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from etlantic.connectors.compatibility import StorageBindingAdapter
from etlantic.connectors.errors import ConnectorWriteError
from etlantic.connectors.local_files import LocalFilesSourceConnector
from etlantic.connectors.models import CommitReceipt, SinkPlan, WriteSession
from etlantic.storage.protocol import StorageBinding


@dataclass
class PublicationBarrier:
    """Collect required sink receipts; advance source state only when all commit."""

    receipts: list[CommitReceipt] = field(default_factory=list)
    source_connector: Any | None = None
    source_binding: dict[str, Any] = field(default_factory=dict)
    source_context: dict[str, Any] = field(default_factory=dict)

    def record(self, receipt: CommitReceipt) -> None:
        self.receipts.append(receipt)

    @property
    def all_committed(self) -> bool:
        return bool(self.receipts) and all(
            r.status == "committed" for r in self.receipts
        )

    @property
    def has_unknown(self) -> bool:
        return any(r.status == "unknown" for r in self.receipts)

    async def finalize_source(self) -> None:
        """Advance landing ledger / consume only after proven commits."""
        if self.source_connector is None:
            return
        if not self.all_committed:
            if hasattr(self.source_connector, "discard_proposal"):
                self.source_connector.discard_proposal()
            return
        publication_id = None
        for receipt in self.receipts:
            if receipt.publication_id:
                publication_id = receipt.publication_id
                break
        if isinstance(self.source_connector, LocalFilesSourceConnector):
            await self.source_connector.commit_ledger(
                publication_id=publication_id,
                context=self.source_context,
            )
            await self.source_connector.consume_after_commit(
                binding=self.source_binding,
                context=self.source_context,
            )


async def write_via_storage_session(
    storage: StorageBinding,
    *,
    binding: Mapping[str, Any],
    data: Any,
    context: Mapping[str, Any],
) -> CommitReceipt:
    """Minimal sink session wrapper emitting CommitReceipt for StorageBinding."""
    adapter = StorageBindingAdapter(storage, provider=getattr(storage, "name", None))
    plan: SinkPlan = await adapter.plan_write(binding=binding, context=context)
    session: WriteSession = await adapter.begin_write(
        plan=plan, binding=binding, context=context
    )
    try:
        await adapter.write_batch(session, data, context=context)
        await adapter.prepare(session, context=context)
        return await adapter.commit(session, context=context)
    except Exception as exc:
        await adapter.abort(session, context=context)
        raise ConnectorWriteError(
            str(exc),
            code="PMCONN801",
            provider=str(getattr(storage, "name", "storage")),
        ) from exc


async def run_source_connector_extract(
    connector: Any,
    *,
    binding: Mapping[str, Any],
    context: dict[str, Any],
) -> tuple[list[Any], Any | None]:
    """Execute plan_read + read_batches for a source connector; return records."""
    plan = await connector.plan_read(binding=binding, context=context)
    records: list[Any] = []
    last_batch = None
    async for batch in connector.read_batches(
        plan=plan, binding=binding, context=context
    ):
        last_batch = batch
        records.extend(list(batch.records))
    manifest = context.get("landing_read_manifest")
    if hasattr(connector, "propose_cursor") and manifest is not None:
        await connector.propose_cursor(plan=plan, manifest=manifest, context=context)
    return records, last_batch


def merge_receipts(receipts: Sequence[CommitReceipt]) -> CommitStatusSummary:
    """Classify aggregate publication outcome."""
    if not receipts:
        return CommitStatusSummary(status="unknown", message="no receipts")
    if any(r.status == "unknown" for r in receipts):
        return CommitStatusSummary(status="unknown", message="one or more unknown")
    if any(r.status == "rolled_back" for r in receipts):
        return CommitStatusSummary(
            status="rolled_back", message="one or more rolled_back"
        )
    if all(r.status == "committed" for r in receipts):
        return CommitStatusSummary(status="committed")
    return CommitStatusSummary(status="unknown", message="mixed outcomes")


@dataclass(frozen=True, slots=True)
class CommitStatusSummary:
    status: str
    message: str | None = None


__all__ = [
    "CommitStatusSummary",
    "PublicationBarrier",
    "merge_receipts",
    "run_source_connector_extract",
    "write_via_storage_session",
]
