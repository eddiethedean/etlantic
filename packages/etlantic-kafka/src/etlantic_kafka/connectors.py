"""Kafka source/sink using FakeKafka (live path skipped unless env is set)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Mapping
from typing import Any

from etlantic.connectors.capabilities import (
    IDEMPOTENCY,
    PUBLICATION_ATOMIC,
    SINK_EXACTLY_ONCE,
    SINK_STREAM,
    SOURCE_STREAM,
    SOURCE_WATERMARK,
    TRANSACTIONS,
)
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
    SinkPlan,
    SourcePlan,
    WriteSession,
    fingerprint_public_config,
)
from etlantic_kafka.fake import FakeKafka

_DEFAULT_GROUP = "default"


def _consumer_group(binding: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    raw = (
        binding.get("group")
        or binding.get("consumer_group")
        or context.get("group")
        or context.get("consumer_group")
        or _DEFAULT_GROUP
    )
    return str(raw)


class KafkaSourceConnector:
    def __init__(self, broker: FakeKafka | None = None) -> None:
        self._broker = FakeKafka() if broker is None else broker
        self._last_end_offsets: dict[int, int] = {}
        self._last_group = _DEFAULT_GROUP

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="kafka",
            protocol=SOURCE_PROTOCOL,
            version="0.47.0",
            provider="kafka",
            capabilities=(SOURCE_STREAM, SOURCE_WATERMARK, IDEMPOTENCY),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"live": False},
        )

    async def plan_read(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SourcePlan:
        return SourcePlan(
            provider="kafka",
            mode="incremental",
            required_capabilities=(SOURCE_STREAM,),
            config_fingerprint=fingerprint_public_config(dict(binding)),
            metadata={"topic": str(binding.get("topic") or "events")},
        )

    def read_batches(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AsyncIterator[ReadBatch]:
        async def _gen() -> AsyncIterator[ReadBatch]:
            group = _consumer_group(binding, context)
            records: list[Any] = []
            end_offsets: dict[int, int] = {}
            for partition in range(self._broker.partitions):
                start = int(self._broker.committed.get(group, {}).get(partition, 0))
                batch = self._broker.fetch(partition, start)
                records.extend(batch)
                end_offsets[partition] = start + len(batch)
            self._last_group = group
            self._last_end_offsets = end_offsets
            yield ReadBatch(
                records=tuple(records),
                batch_index=0,
                exhausted=True,
                metadata={
                    "count": len(records),
                    "group": group,
                    "offsets": {str(k): v for k, v in sorted(end_offsets.items())},
                },
            )

        return _gen()

    async def propose_cursor(
        self,
        *,
        plan: SourcePlan,
        manifest: LandingReadManifest,
        context: Mapping[str, Any],
    ) -> CursorProposal | None:
        group = self._last_group
        offsets = dict(self._last_end_offsets)
        if not offsets:
            for partition in range(self._broker.partitions):
                offsets[partition] = int(
                    self._broker.committed.get(group, {}).get(partition, 0)
                )
        candidate = ",".join(f"{part}:{off}" for part, off in sorted(offsets.items()))
        return CursorProposal(
            subject_id=str(plan.metadata.get("topic") or "events"),
            candidate=candidate,
            metadata={
                "group": group,
                "offsets": {str(k): v for k, v in sorted(offsets.items())},
            },
        )


class KafkaSinkConnector:
    def __init__(self, broker: FakeKafka | None = None) -> None:
        self._broker = FakeKafka() if broker is None else broker
        self._staged: dict[str, list[Any]] = {}

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="kafka",
            protocol=SINK_PROTOCOL,
            version="0.47.0",
            provider="kafka",
            capabilities=(
                SINK_STREAM,
                SINK_EXACTLY_ONCE,
                TRANSACTIONS,
                PUBLICATION_ATOMIC,
                IDEMPOTENCY,
            ),
            maturity=ConnectorMaturity.EXPERIMENTAL,
        )

    async def plan_write(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SinkPlan:
        return SinkPlan(
            provider="kafka",
            required_capabilities=(SINK_STREAM,),
            config_fingerprint=fingerprint_public_config(dict(binding)),
            metadata={"topic": str(binding.get("topic") or "events")},
        )

    async def begin_write(
        self,
        *,
        plan: SinkPlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> WriteSession:
        session = WriteSession(
            session_id=f"kafka-{uuid.uuid4().hex}",
            provider="kafka",
        )
        self._staged[session.session_id] = []
        self._broker.begin_txn(session.session_id)
        return session

    async def write_batch(
        self,
        session: WriteSession,
        batch: Any,
        *,
        context: Mapping[str, Any],
    ) -> None:
        self._staged.setdefault(session.session_id, []).append(batch)

    async def prepare(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> None:
        return None

    async def commit(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        for item in self._staged.pop(session.session_id, []):
            record = item if isinstance(item, dict) else {"value_id": str(item)}
            self._broker.produce(0, record, txn=session.session_id)
        self._broker.commit_txn(session.session_id)
        return CommitReceipt(
            session_id=session.session_id,
            provider="kafka",
            status="committed",
        )

    async def abort(
        self,
        session: WriteSession,
        *,
        context: Mapping[str, Any],
    ) -> CommitReceipt:
        self._staged.pop(session.session_id, None)
        self._broker.abort_txn(session.session_id)
        return CommitReceipt(
            session_id=session.session_id,
            provider="kafka",
            status="rolled_back",
        )

    async def reconcile(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> ReconciliationResult:
        return ReconciliationResult(
            status=receipt.status, publication_id=receipt.publication_id
        )

    async def cleanup(
        self,
        receipt: CommitReceipt,
        *,
        context: Mapping[str, Any],
    ) -> CleanupReceipt:
        return CleanupReceipt(status="completed")


def create_source(broker: FakeKafka | None = None) -> KafkaSourceConnector:
    return KafkaSourceConnector(broker)


def create_sink(broker: FakeKafka | None = None) -> KafkaSinkConnector:
    return KafkaSinkConnector(broker)
