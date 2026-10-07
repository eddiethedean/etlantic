# pyright: reportUnknownVariableType=false
"""Run-scoped publication barrier coordinating sink commit and source ledger."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import anyio

from etlantic.connectors.errors import ConnectorReadError, ConnectorWriteError
from etlantic.connectors.models import CommitReceipt, SinkPlan, WriteSession
from etlantic.runtime.invoke import maybe_await

if TYPE_CHECKING:
    from etlantic.storage.protocol import StorageBinding


@dataclass
class PublicationBarrier:
    """Collect required sink receipts; advance source state only when all commit."""

    receipts: list[CommitReceipt] = field(default_factory=list)
    source_connector: Any | None = None
    source_binding: dict[str, Any] = field(default_factory=dict)
    source_context: dict[str, Any] = field(default_factory=dict)
    expected_sink_commits: int = 0

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

    @property
    def is_complete(self) -> bool:
        """True when every required sink receipt has been recorded."""
        expected = self.expected_sink_commits
        if expected <= 0:
            return bool(self.receipts)
        return len(self.receipts) >= expected

    async def finalize_source(self) -> None:
        """Advance landing ledger / consume only after proven commits."""
        if self.source_connector is None:
            return
        # Wait until every required sink has reported before advancing or discard.
        if not self.is_complete:
            return
        if not self.all_committed:
            # Unknown publications may already be durable — hold lease/proposal.
            if self.has_unknown:
                return
            if hasattr(self.source_connector, "discard_proposal"):
                self.source_connector.discard_proposal()
            return
        publication_id = None
        for receipt in self.receipts:
            if receipt.publication_id:
                publication_id = receipt.publication_id
                break
        if hasattr(self.source_connector, "commit_ledger"):
            await self.source_connector.commit_ledger(
                publication_id=publication_id,
                context=self.source_context,
            )
        if hasattr(self.source_connector, "consume_after_commit"):
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
    # Lazy import: avoid connectors → storage → runtime → profile cycles at import time.
    from etlantic.connectors.compatibility import StorageBindingAdapter

    adapter = StorageBindingAdapter(storage, provider=getattr(storage, "name", None))
    plan: SinkPlan = await adapter.plan_write(binding=binding, context=context)
    session: WriteSession = await adapter.begin_write(
        plan=plan, binding=binding, context=context
    )
    commit_started = False
    try:
        await adapter.write_batch(session, data, context=context)
        await adapter.prepare(session, context=context)
        # Once commit starts, a raised exception or cancellation cannot prove
        # that the legacy StorageBinding had no effect. Never abort that write.
        commit_started = True
        return await adapter.commit(session, context=context)
    except BaseException as exc:
        if commit_started:
            receipt = getattr(exc, "commit_receipt", None)
            if not isinstance(receipt, CommitReceipt):
                receipt = CommitReceipt(
                    status="unknown",
                    session_id=session.session_id,
                    provider=session.provider,
                    message="Storage write outcome was not acknowledged",
                    metadata=dict(session.metadata),
                )
            with suppress(AttributeError, TypeError):
                cast(Any, exc).commit_receipt = receipt
            if not isinstance(exc, Exception):
                raise
            return receipt

        try:
            # Do not let cancellation interrupt cleanup of the local adapter
            # session before the external write has started.
            with anyio.CancelScope(shield=True):
                await adapter.abort(session, context=context)
        except BaseException:
            if not isinstance(exc, Exception):
                raise exc from None
        if not isinstance(exc, Exception):
            raise
        raise ConnectorWriteError(
            str(exc),
            code="PMCONN801",
            provider=str(getattr(storage, "name", "storage")),
        ) from exc


async def write_via_sink_connector(
    connector: Any,
    *,
    binding: Mapping[str, Any],
    data: Any,
    context: Mapping[str, Any],
) -> CommitReceipt:
    """Run one bounded sink connector transaction and classify its outcome.

    Failures before commit are aborted and reported as rolled back when the
    provider confirms that abort. A lost commit acknowledgement stays unknown;
    the caller can ask the same connector to reconcile the stable session.
    """
    partition_ids = context.get("etlantic.partition_ids")
    if partition_ids is not None:
        planner = getattr(connector, "plan_write_partitions", None)
        if not callable(planner):
            raise ConnectorWriteError(
                "Sink connector does not implement bounded partition writes",
                code="PMCONN802",
                provider=str(getattr(connector, "name", "sink")),
            )
        plan = await maybe_await(
            planner,
            binding=binding,
            context=context,
            partition_ids=tuple(partition_ids),
        )
        required = {"write.partition_replace", "idempotency"}
        info = connector.info() if callable(getattr(connector, "info", None)) else None
        plan_capabilities = cast(
            Sequence[str], getattr(plan, "required_capabilities", ())
        )
        info_capabilities = cast(Sequence[str], getattr(info, "capabilities", ()))
        if not required.issubset(plan_capabilities) or not required.issubset(
            info_capabilities
        ):
            raise ConnectorWriteError(
                "Sink connector did not prove idempotent partition replacement",
                code="PMCONN802",
                provider=str(getattr(connector, "name", "sink")),
            )
    else:
        plan = await connector.plan_write(binding=binding, context=context)
    try:
        session = await connector.begin_write(
            plan=plan, binding=binding, context=context
        )
    except Exception as exc:
        details_raw: object = getattr(exc, "details", None)
        if not isinstance(details_raw, Mapping):
            raise
        details = cast(Mapping[str, Any], details_raw)
        if not details.get("effect_unknown"):
            raise
        plan_metadata_raw: object = getattr(plan, "metadata", None)
        plan_metadata = (
            cast(Mapping[str, Any], plan_metadata_raw)
            if isinstance(plan_metadata_raw, Mapping)
            else {}
        )
        metadata: dict[str, Any] = {
            name: value for name, value in plan_metadata.items()
        }
        effect_id = metadata.get("effect_id")
        return CommitReceipt(
            status="unknown",
            session_id=str(effect_id) if effect_id is not None else None,
            provider=getattr(plan, "provider", None),
            message="Sink transaction creation acknowledgement was not received",
            metadata=metadata,
        )
    try:
        await connector.write_batch(session, data, context=context)
        await connector.prepare(session, context=context)
    except BaseException as exc:
        aborted: object = None
        try:
            # Cancellation must not interrupt provider rollback after a session
            # has been created. The caller still observes the original cancel.
            with anyio.CancelScope(shield=True):
                aborted = await connector.abort(session, context=context)
        except BaseException:
            if not isinstance(exc, Exception):
                raise exc from None
            return CommitReceipt(
                status="unknown",
                session_id=session.session_id,
                provider=session.provider,
                message="Sink staging failed and abort could not be confirmed",
                metadata=dict(session.metadata),
            )
        if not isinstance(exc, Exception):
            raise exc from None
        if isinstance(aborted, CommitReceipt) and aborted.status == "rolled_back":
            return aborted
        return CommitReceipt(
            status="unknown",
            session_id=session.session_id,
            provider=session.provider,
            message="Sink staging failed and rollback could not be confirmed",
            metadata=dict(session.metadata),
        )
    try:
        receipt = await connector.commit(session, context=context)
    except Exception:
        return CommitReceipt(
            status="unknown",
            session_id=session.session_id,
            provider=session.provider,
            message="Sink commit acknowledgement was not received",
            metadata=dict(session.metadata),
        )
    except BaseException as exc:
        # Commit may have taken effect before cancellation reached the caller.
        # Never abort after commit starts; reconcile under a shield and attach
        # the classified outcome to the cancellation for the orchestrator.
        receipt = CommitReceipt(
            status="unknown",
            session_id=session.session_id,
            provider=session.provider,
            message="Sink commit was cancelled before its outcome was acknowledged",
            metadata=dict(session.metadata),
        )
        reconcile = getattr(connector, "reconcile", None)
        if callable(reconcile):
            result: object = None
            try:
                with anyio.CancelScope(shield=True):
                    result = await maybe_await(reconcile, receipt, context=context)
                if isinstance(result, CommitReceipt) and result.status in {
                    "committed",
                    "rolled_back",
                    "unknown",
                }:
                    receipt = result
            except BaseException:
                pass
        with suppress(AttributeError, TypeError):
            cast(Any, exc).commit_receipt = receipt
        raise
    if not isinstance(receipt, CommitReceipt):
        return CommitReceipt(
            status="unknown",
            session_id=session.session_id,
            provider=session.provider,
            message="Sink returned an invalid commit receipt",
            metadata=dict(session.metadata),
        )
    if receipt.status not in {"committed", "rolled_back", "unknown"}:
        return CommitReceipt(
            status="unknown",
            session_id=session.session_id,
            provider=session.provider,
            message="Sink returned an unsupported commit status",
        )
    return receipt


async def run_source_connector_extract(
    connector: Any,
    *,
    binding: Mapping[str, Any],
    context: dict[str, Any],
) -> tuple[list[Any], Any | None]:
    """Execute plan_read + read_batches for a source connector; return records."""
    partition_ids = context.get("etlantic.partition_ids")
    if partition_ids is not None:
        planner = getattr(connector, "plan_read_partitions", None)
        if not callable(planner):
            raise ConnectorReadError(
                "Source connector does not implement bounded partition reads",
                code="PMCONN803",
                provider=str(getattr(connector, "name", "source")),
            )
        plan = await maybe_await(
            planner,
            binding=binding,
            context=context,
            partition_ids=tuple(partition_ids),
        )
        plan_capabilities = cast(
            Sequence[str], getattr(plan, "required_capabilities", ())
        )
        if "source.partitioned" not in plan_capabilities:
            raise ConnectorReadError(
                "Source plan did not prove bounded partition reads",
                code="PMCONN803",
                provider=str(getattr(connector, "name", "source")),
            )
        info = connector.info() if callable(getattr(connector, "info", None)) else None
        info_capabilities = cast(Sequence[str], getattr(info, "capabilities", ()))
        if "source.partitioned" not in info_capabilities:
            raise ConnectorReadError(
                "Source connector did not advertise bounded partition reads",
                code="PMCONN803",
                provider=str(getattr(connector, "name", "source")),
            )
    else:
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
    "write_via_sink_connector",
    "write_via_storage_session",
]
