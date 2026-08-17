"""Remote-runtime negotiate, placement, signed artifacts."""

from __future__ import annotations

import pytest

from etlantic.control_plane.remote_runtime import FakeRemoteHost


def test_negotiate_submit_and_recover() -> None:
    host = FakeRemoteHost()
    session = host.negotiate(
        {
            "version": "0.47.0",
            "capabilities": {"map": True, "branch": True, "stream": True},
        }
    )
    plan = {"nodes": [{"kind": "map"}], "fingerprint": "abc"}
    envelope = host.sign_plan(plan, nonce="n1")
    accepted = host.submit(session.session_id, envelope, plan)
    assert accepted["accepted"]
    host.disconnect(session.session_id)
    recovered = host.recover(session.session_id)
    assert recovered.disconnected is False


def test_missing_dyn_caps_rejected() -> None:
    host = FakeRemoteHost()
    with pytest.raises(ValueError, match="PMFED110"):
        host.negotiate({"version": "0.47.0", "capabilities": {"map": False}})


def test_placement_rejects_before_transfer() -> None:
    host = FakeRemoteHost()
    with pytest.raises(ValueError, match="PMRES110"):
        host.evaluate_placement({"required_capabilities": ["gpu"]})
    decision = host.evaluate_placement({"required_capabilities": ["map"]})
    assert decision["transferred"] is False


def test_tamper_partial_replay() -> None:
    host = FakeRemoteHost()
    plan = {"fingerprint": "abc"}
    envelope = host.sign_plan(plan, nonce="once")
    with pytest.raises(ValueError):
        host.sign_plan(plan, nonce="once")
    tampered = dict(envelope)
    tampered["hmac"] = "00" * 32
    with pytest.raises(ValueError, match="PMFED"):
        host.verify_plan(tampered, plan)
    dirty = {"fingerprint": "abc", "payload": {"row": 1}}
    session = host.negotiate(
        {
            "version": "0.47.0",
            "capabilities": {"map": True, "branch": True, "stream": True},
        }
    )
    envelope2 = host.sign_plan(dirty, nonce="n2")
    with pytest.raises(ValueError, match="PMFED140"):
        host.submit(session.session_id, envelope2, dirty)
