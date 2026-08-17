"""Change-envelope metadata (046-E). Never carries event payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

FORBIDDEN_ENVELOPE_KEYS = frozenset(
    {"payload", "value", "body", "record", "event", "row", "bytes"}
)


class ChangeOp(StrEnum):
    """Versioned change-event operation."""

    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    TOMBSTONE = "tombstone"


@dataclass(frozen=True, slots=True)
class ChangeEnvelopeMetadata:
    """Envelope **metadata** only: op, position, order, schema identity."""

    op: ChangeOp
    source_position: str
    order_key: str
    schema_identity: str
    transaction_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "op": self.op.value,
            "source_position": self.source_position,
            "order_key": self.order_key,
            "schema_identity": self.schema_identity,
            "transaction_id": self.transaction_id,
        }
        assert_no_payload(payload)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ChangeEnvelopeMetadata:
        assert_no_payload(data)
        txn = data.get("transaction_id")
        return cls(
            op=ChangeOp(str(data["op"])),
            source_position=str(data["source_position"]),
            order_key=str(data["order_key"]),
            schema_identity=str(data["schema_identity"]),
            transaction_id=None if txn in (None, "") else str(txn),
        )


def assert_no_payload(data: Mapping[str, Any]) -> None:
    """Fail closed when a mapping smuggles event payload keys."""
    hits = sorted(k for k in data if str(k).lower() in FORBIDDEN_ENVELOPE_KEYS)
    if hits:
        raise ValueError(
            "Change envelopes must not contain event payloads; "
            f"forbidden keys: {', '.join(hits)}"
        )
