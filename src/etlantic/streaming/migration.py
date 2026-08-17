"""Envelope and stream-state migration records (046-C). In-process fakes only."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from etlantic.streaming.envelope import (
    ChangeEnvelopeMetadata,
    assert_no_payload,
)

ENVELOPE_SCHEMA_V1 = "etlantic.envelope/1"
STATE_SCHEMA_V1 = "etlantic.stream-state/1"

_LEGACY_OP = {
    "i": "insert",
    "u": "update",
    "d": "delete",
    "t": "tombstone",
}


@dataclass(frozen=True, slots=True)
class StreamStateRecord:
    """Versioned stream-state identity (no payloads, no offsets as rows)."""

    schema: str
    identity: str
    envelope_schema: str
    watermark: str | None = None
    cursor_identity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": self.schema,
            "identity": self.identity,
            "envelope_schema": self.envelope_schema,
            "watermark": self.watermark,
            "cursor_identity": self.cursor_identity,
        }
        assert_no_payload(payload)
        return payload


def migrate_envelope_dict(data: Mapping[str, Any]) -> ChangeEnvelopeMetadata:
    """Upgrade mixed-version envelope metadata to ``etlantic.envelope/1``."""
    assert_no_payload(data)
    if "op" in data and "source_position" in data:
        return ChangeEnvelopeMetadata.from_dict(data)
    op = str(data.get("o") or data.get("op") or "insert")
    op = _LEGACY_OP.get(op, op)
    return ChangeEnvelopeMetadata.from_dict(
        {
            "op": op,
            "source_position": str(
                data.get("pos") or data.get("source_position") or "0"
            ),
            "order_key": str(data.get("ord") or data.get("order_key") or "0"),
            "schema_identity": str(
                data.get("schema_id") or data.get("schema_identity") or "unknown"
            ),
            "transaction_id": data.get("txn") or data.get("transaction_id"),
        }
    )


def migrate_state_dict(data: Mapping[str, Any]) -> StreamStateRecord:
    """Upgrade mixed-version stream-state records to ``etlantic.stream-state/1``."""
    assert_no_payload(data)
    schema = str(data.get("schema") or STATE_SCHEMA_V1)
    if schema not in {STATE_SCHEMA_V1, "etlantic.stream-state/0"}:
        raise ValueError(f"Unknown stream-state schema {schema!r}")
    return StreamStateRecord(
        schema=STATE_SCHEMA_V1,
        identity=str(data.get("identity") or data.get("id") or ""),
        envelope_schema=str(data.get("envelope_schema") or ENVELOPE_SCHEMA_V1),
        watermark=None
        if data.get("watermark") in (None, "")
        else str(data.get("watermark")),
        cursor_identity=(
            None
            if (data.get("cursor_identity") or data.get("cursor")) in (None, "")
            else str(data.get("cursor_identity") or data.get("cursor"))
        ),
    )
