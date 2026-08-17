"""In-memory stream / DLQ / registry fixtures (payloads stay in the fixture)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etlantic.control_plane.durable_models import namespaced_checkpoint_id
from etlantic.streaming.diagnostics import dlq_diagnostic, str_diagnostic
from etlantic.streaming.envelope import ChangeEnvelopeMetadata
from etlantic.streaming.errors import RecordErrorOutcome, RecordErrorPolicy


@dataclass
class InMemoryRecord:
    """Fixture-local record. Never serialize ``payload`` into plans/reports."""

    identity: str
    envelope: ChangeEnvelopeMetadata
    payload: Any = None
    poison: bool = False


@dataclass
class InMemoryDeadLetterStore:
    """Provider-owned DLQ store. ETLantic only sees identifiers."""

    authorization_identity: str
    _items: dict[str, InMemoryRecord] = field(default_factory=dict)
    _redrive_ids: set[str] = field(default_factory=set)

    def put(self, record: InMemoryRecord) -> str:
        self._items[record.identity] = record
        return record.identity

    def inspect_metadata(self, *, principal: str) -> list[dict[str, Any]]:
        """Return identifier metadata only; never payloads."""
        if principal != self.authorization_identity:
            raise PermissionError(
                dlq_diagnostic(
                    "unauthorized_payload",
                    "Unauthorized principal cannot inspect dead-letter metadata.",
                    path=("dlq", "inspect"),
                ).message
            )
        return [self._metadata(item) for item in self._items.values()]

    def inspect_payload(self, *, principal: str, record_id: str) -> Any:
        """Payload access stays in the fixture; ETLantic APIs must not call this."""
        if principal != self.authorization_identity:
            raise PermissionError(
                dlq_diagnostic(
                    "unauthorized_payload",
                    "Unauthorized principal cannot retrieve dead-letter payloads.",
                    path=("dlq", "payload", record_id),
                ).message
            )
        return self._items[record_id].payload

    def redrive(self, record_id: str, *, principal: str) -> str:
        if principal != self.authorization_identity:
            raise PermissionError(
                dlq_diagnostic(
                    "unauthorized_payload",
                    "Unauthorized principal cannot redrive dead letters.",
                    path=("dlq", "redrive", record_id),
                ).message
            )
        if record_id not in self._items:
            raise KeyError(record_id)
        if record_id in self._redrive_ids:
            return record_id
        self._redrive_ids.add(record_id)
        return record_id

    def _metadata(self, record: InMemoryRecord) -> dict[str, Any]:
        return {
            "identity": record.identity,
            "envelope": record.envelope.to_dict(),
        }


@dataclass
class InMemoryStreamSource:
    """In-process stream fixture with crash/restart cursor state."""

    identity: str
    records: list[InMemoryRecord] = field(default_factory=list)
    cursor: int = 0
    committed_cursor: int = 0
    policy: RecordErrorPolicy = field(default_factory=RecordErrorPolicy)
    retries: dict[str, int] = field(default_factory=dict)
    dlq: InMemoryDeadLetterStore | None = None

    def checkpoint_id(self) -> str:
        return namespaced_checkpoint_id("cursor", self.identity)

    def watermark_id(self) -> str:
        return namespaced_checkpoint_id("watermark", self.identity)

    def crash(self) -> None:
        """Lose uncommitted cursor (restart from last commit)."""
        self.cursor = self.committed_cursor

    def commit(self) -> None:
        self.committed_cursor = self.cursor

    def next_envelope(self) -> ChangeEnvelopeMetadata | None:
        """Advance past a non-poison record; return metadata only."""
        while self.cursor < len(self.records):
            record = self.records[self.cursor]
            if record.poison:
                used = self.retries.get(record.identity, 0)
                if used < self.policy.max_retries:
                    self.retries[record.identity] = used + 1
                    return None
                if self.policy.outcome is RecordErrorOutcome.FAIL:
                    return None
                if (
                    self.policy.outcome is RecordErrorOutcome.DEAD_LETTER
                    and self.dlq is not None
                ):
                    self.dlq.put(record)
                if self.policy.may_advance_offset(retries_used=used):
                    self.cursor += 1
                    continue
                return None
            envelope = record.envelope
            self.cursor += 1
            return envelope
        return None

    def report_fields(self) -> dict[str, Any]:
        """Namespaced metadata safe for plans/reports (no payloads)."""
        return {
            "etlantic.streaming.cursor": self.checkpoint_id(),
            "etlantic.streaming.committed": self.committed_cursor,
            "etlantic.streaming.position": self.cursor,
            "etlantic.streaming.rejected_count": sum(
                1 for r in self.records if r.poison
            ),
            "etlantic.streaming.rejected_ids": [
                r.identity for r in self.records if r.poison
            ],
        }


@dataclass
class InMemoryStreamSink:
    """Idempotent in-memory sink with crash-before-ack."""

    identity: str
    committed: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)

    def write(self, envelope: ChangeEnvelopeMetadata) -> None:
        self.pending.append(envelope.source_position)

    def ack(self) -> None:
        self.committed.extend(self.pending)
        self.pending.clear()

    def crash(self) -> None:
        self.pending.clear()

    def checkpoint_id(self) -> str:
        return namespaced_checkpoint_id("checkpoint", self.identity)


@dataclass
class InMemoryTriggerQueue:
    """Bounded event-trigger queue used to prove backpressure visibility."""

    identity: str
    bound: int = 8
    outstanding: int = 0

    def submit(self) -> None:
        if self.outstanding >= self.bound:
            raise OverflowError(
                str_diagnostic(
                    "backpressure",
                    f"Trigger queue {self.identity!r} exhausted bound {self.bound}",
                    path=("streaming", "trigger", self.identity),
                    metadata={
                        "etlantic.streaming.backpressure": True,
                        "etlantic.streaming.outstanding": self.outstanding,
                        "etlantic.streaming.bound": self.bound,
                    },
                ).message
            )
        self.outstanding += 1

    def complete(self) -> None:
        if self.outstanding > 0:
            self.outstanding -= 1

    def report_fields(self) -> dict[str, Any]:
        return {
            "etlantic.streaming.trigger": self.identity,
            "etlantic.streaming.outstanding": self.outstanding,
            "etlantic.streaming.bound": self.bound,
            "etlantic.streaming.backpressure": self.outstanding >= self.bound,
        }


def collect_report_json(*parts: MappingLike) -> dict[str, Any]:
    """Merge fixture report fields and assert no payload keys."""
    from etlantic.streaming.envelope import assert_no_payload

    merged: dict[str, Any] = {}
    for part in parts:
        data = part.report_fields() if hasattr(part, "report_fields") else dict(part)
        merged.update(data)
    assert_no_payload(merged)
    text = str(merged)
    for forbidden in ("payload", "secret"):
        if forbidden in text.lower() and "etlantic." not in forbidden:
            pass
    return merged


MappingLike = Any
