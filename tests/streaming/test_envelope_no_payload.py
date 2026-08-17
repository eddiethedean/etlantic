"""Change envelopes never carry payloads."""

from __future__ import annotations

import pytest

from etlantic.streaming.envelope import (
    ChangeEnvelopeMetadata,
    ChangeOp,
    assert_no_payload,
)


def test_envelope_roundtrip() -> None:
    env = ChangeEnvelopeMetadata(
        op=ChangeOp.INSERT,
        source_position="offset:12",
        order_key="12",
        schema_identity="sub:1",
        transaction_id="txn-1",
    )
    cloned = ChangeEnvelopeMetadata.from_dict(env.to_dict())
    assert cloned.op is ChangeOp.INSERT
    assert "payload" not in env.to_dict()


def test_forbidden_payload_keys() -> None:
    with pytest.raises(ValueError, match="payloads"):
        assert_no_payload({"op": "insert", "payload": {"secret": "x"}})
    with pytest.raises(ValueError):
        ChangeEnvelopeMetadata.from_dict(
            {
                "op": "insert",
                "source_position": "1",
                "order_key": "1",
                "schema_identity": "s",
                "body": "nope",
            }
        )
