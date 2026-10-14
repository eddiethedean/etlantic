from __future__ import annotations

import json
import threading
import time
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import replace
from typing import Any, cast

import pytest
from etlantic_rsconnect import (
    DeliveryConfig,
    DeliveryError,
    HttpsTriggerDelivery,
    OccurrenceContext,
    build_trigger_envelope,
)

from etlantic.control_plane import TriggerEnvelope, TriggerReceipt
from etlantic.outbound import OutboundDecision, OutboundPolicy
from etlantic.secrets import SecretRef


def _delivery(*, attempts: int = 2) -> HttpsTriggerDelivery:
    config = DeliveryConfig(
        endpoint_url="https://receiver.example.com/base",
        credential_ref=SecretRef("env", "receiver", "token"),
        outbound_policy=OutboundPolicy(
            allowed_hosts=("receiver.example.com",),
            max_response_bytes=65_536,
        ),
        max_attempts=attempts,
    )
    client = HttpsTriggerDelivery(
        config,
        lambda _ref: "runtime-secret-value",
        sleep=lambda _seconds: None,
        monotonic=lambda: 1.0,
        random_value=lambda: 0.0,
    )

    def destination(run_id: str, *, deadline: float | None = None) -> tuple[str, ...]:
        return ("203.0.113.10",)

    vars(client)["_destination"] = destination
    return client


def _envelope() -> TriggerEnvelope:
    return build_trigger_envelope(
        schedule_id="schedule/alpha",
        schedule_revision_id="revision-1",
        timer_owner_generation=3,
        occurrence=OccurrenceContext(
            scheduled_at="2026-10-13T12:00:00Z",
            delivery_attempt_id="attempt-1",
            correlation_id="correlation-1",
        ),
    )


def _accepted_receipt(envelope: TriggerEnvelope) -> TriggerReceipt:
    return TriggerReceipt(
        status="accepted",
        firing_status="accepted",
        schedule_id=envelope.schedule_id,
        schedule_revision_id=envelope.schedule_revision_id,
        occurrence_id=envelope.occurrence_id,
        submission_id="submission-1",
        status_reference=(
            "/v1/schedules/schedule%2Falpha/occurrences/" + envelope.occurrence_id
        ),
    )


def test_delivery_retries_identical_envelope_after_response_loss() -> None:
    client = _delivery()
    envelope = _envelope()
    requests: list[tuple[str, bytes]] = []

    def request(
        host: str,
        address: str,
        port: int,
        path: str,
        body: bytes | None,
        headers: Mapping[str, str],
        *,
        timeout: float,
        deadline: float,
        method: str = "POST",
    ) -> tuple[int, Mapping[str, str], bytes]:
        requests.append((path, body or b""))
        assert headers["Authorization"] == "Bearer runtime-secret-value"
        if len(requests) == 1:
            raise OSError("connection closed after request")
        return (
            200,
            {"content-type": "application/json"},
            json.dumps(_accepted_receipt(envelope).to_dict()).encode(),
        )

    vars(client)["_request"] = request
    result = client.deliver(envelope)

    assert result.attempts == 2
    assert result.receipt == _accepted_receipt(envelope)
    assert len(requests) == 2
    assert requests[0] == requests[1]
    sent = json.loads(requests[0][1])
    assert sent["occurrence_id"] == envelope.occurrence_id
    assert sent["scheduled_at"] == envelope.scheduled_at


def test_delivery_rejects_mismatched_receipt_as_uncertain() -> None:
    client = _delivery(attempts=1)
    envelope = _envelope()
    wrong = TriggerReceipt(
        status="accepted",
        firing_status="accepted",
        schedule_id=envelope.schedule_id,
        schedule_revision_id=envelope.schedule_revision_id,
        occurrence_id="occ-" + "0" * 64,
        submission_id="submission-1",
        status_reference=(
            "/v1/schedules/schedule%2Falpha/occurrences/" + "occ-" + "0" * 64
        ),
    )

    def wrong_receipt(
        host: str,
        address: str,
        port: int,
        path: str,
        body: bytes | None,
        headers: Mapping[str, str],
        *,
        timeout: float,
        deadline: float,
        method: str = "POST",
    ) -> tuple[int, Mapping[str, str], bytes]:
        return (
            200,
            {"content-type": "application/json"},
            json.dumps(wrong.to_dict()).encode(),
        )

    vars(client)["_request"] = wrong_receipt

    with pytest.raises(DeliveryError, match="does not match") as error:
        client.deliver(envelope)
    assert error.value.uncertain


def test_delivery_attempt_limit_covers_all_resolved_addresses() -> None:
    client = _delivery(attempts=2)

    def destination(run_id: str, *, deadline: float | None = None) -> tuple[str, ...]:
        return (
            "203.0.113.10",
            "203.0.113.11",
            "203.0.113.12",
        )

    vars(client)["_destination"] = destination
    attempted: list[str] = []

    def request(
        host: str,
        address: str,
        port: int,
        path: str,
        body: bytes | None,
        headers: Mapping[str, str],
        *,
        timeout: float,
        deadline: float,
        method: str = "POST",
    ) -> tuple[int, Mapping[str, str], bytes]:
        attempted.append(address)
        raise OSError("simulated connection failure")

    vars(client)["_request"] = request
    with pytest.raises(DeliveryError, match="connection failed"):
        client.deliver(_envelope())

    assert attempted == ["203.0.113.10", "203.0.113.11"]


def test_dns_resolution_is_limited_by_delivery_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import etlantic_rsconnect.delivery as delivery_module

    config = DeliveryConfig(
        endpoint_url="https://receiver.example.com/base",
        credential_ref=SecretRef("env", "receiver", "token"),
        outbound_policy=OutboundPolicy(
            allowed_hosts=("receiver.example.com",),
            max_response_bytes=65_536,
        ),
        max_elapsed_seconds=0.05,
    )
    client = HttpsTriggerDelivery(
        config,
        lambda _ref: "runtime-secret-value",
        monotonic=time.monotonic,
    )
    release_resolver = threading.Event()

    def stalled_resolver(*_args: Any, **_kwargs: Any) -> None:
        release_resolver.wait(1)
        raise TimeoutError("simulated resolver stall")

    monkeypatch.setattr(delivery_module, "evaluate_outbound_url", stalled_resolver)
    try:
        started = time.monotonic()
        with pytest.raises(DeliveryError, match="DNS resolution exceeded"):
            client.deliver(_envelope())
        assert time.monotonic() - started < 0.5
    finally:
        release_resolver.set()


@pytest.mark.parametrize("operation", ["deliver", "reconcile"])
def test_credential_resolution_shares_the_delivery_deadline(operation: str) -> None:
    client = _delivery(attempts=1)
    client.config = replace(client.config, max_elapsed_seconds=0.1)
    vars(client)["_monotonic"] = time.monotonic
    release = threading.Event()
    finished = threading.Event()

    def resolve(_ref: SecretRef) -> str:
        try:
            release.wait(2)
            return "late-synthetic-credential"
        finally:
            finished.set()

    def destination(run_id: str, *, deadline: float | None = None) -> tuple[str, ...]:
        time.sleep(0.03)
        return ("203.0.113.10",)

    client.resolve_secret = resolve
    vars(client)["_destination"] = destination
    started = time.monotonic()
    try:
        with pytest.raises(
            DeliveryError, match="credential resolution exceeded"
        ) as error:
            getattr(client, operation)(_envelope())
        assert time.monotonic() - started < 0.5
        assert not error.value.uncertain
        assert "late-synthetic-credential" not in str(error.value)
    finally:
        release.set()
        assert finished.wait(1)


def test_credential_provider_errors_are_redacted() -> None:
    client = _delivery(attempts=1)

    def resolve(_ref: SecretRef) -> str:
        raise ValueError("synthetic-credential-in-provider-error")

    client.resolve_secret = resolve
    with pytest.raises(
        DeliveryError, match="credential could not be resolved"
    ) as error:
        client.deliver(_envelope())
    assert "synthetic-credential-in-provider-error" not in str(error.value)


def test_credential_provider_preserves_the_calling_context() -> None:
    client = _delivery(attempts=1)
    envelope = _envelope()
    scope: ContextVar[str] = ContextVar("test_credential_scope", default="unscoped")

    def resolve(_ref: SecretRef) -> str:
        assert scope.get() == "tenant-a"
        return "synthetic-scoped-token"

    def request(*_args: Any, **_kwargs: Any) -> tuple[int, Mapping[str, str], bytes]:
        return (
            200,
            {"content-type": "application/json"},
            json.dumps(_accepted_receipt(envelope).to_dict()).encode(),
        )

    client.resolve_secret = resolve
    vars(client)["_request"] = request
    token = scope.set("tenant-a")
    try:
        assert client.deliver(envelope).receipt.status == "accepted"
    finally:
        scope.reset(token)


def test_response_header_stall_is_interrupted_by_delivery_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import etlantic_rsconnect.delivery as delivery_module

    client = _delivery(attempts=1)
    vars(client)["_monotonic"] = time.monotonic
    interrupted = threading.Event()

    class SlowSocket:
        def shutdown(self, _how: int) -> None:
            interrupted.set()

        def close(self) -> None:
            interrupted.set()

    class SlowHeadersConnection:
        transport_socket = SlowSocket()

        def request(self, *_args: Any, **_kwargs: Any) -> None:
            return

        def getresponse(self) -> None:
            if interrupted.wait(1):
                raise OSError("response headers interrupted")
            raise AssertionError("delivery deadline did not interrupt response")

        def close(self) -> None:
            interrupted.set()

    connection = SlowHeadersConnection()

    def create_connection(*_args: Any, **_kwargs: Any) -> SlowHeadersConnection:
        return connection

    monkeypatch.setattr(
        cast(Any, delivery_module), "_PinnedHttpsConnection", create_connection
    )
    started = time.monotonic()
    with pytest.raises(OSError, match="headers interrupted"):
        cast(Any, client)._request(
            "receiver.example.com",
            "203.0.113.10",
            443,
            "/trigger",
            b"{}",
            {},
            timeout=1,
            deadline=started + 0.05,
        )
    assert interrupted.is_set()
    assert time.monotonic() - started < 0.5


def test_delivery_connects_only_to_addresses_returned_by_shared_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import etlantic_rsconnect.delivery as delivery_module

    config = DeliveryConfig(
        endpoint_url="https://receiver.example.com/base",
        credential_ref=SecretRef("env", "receiver", "token"),
        outbound_policy=OutboundPolicy(
            allowed_hosts=("receiver.example.com",),
            max_response_bytes=65_536,
        ),
    )
    client = HttpsTriggerDelivery(
        config,
        lambda _ref: "runtime-secret-value",
        sleep=lambda _seconds: None,
        monotonic=lambda: 1.0,
        random_value=lambda: 0.0,
    )
    envelope = _envelope()
    observed_addresses: list[str] = []
    receipt_body = json.dumps(_accepted_receipt(envelope).to_dict()).encode()

    def evaluate_outbound_url(
        url: str, policy: OutboundPolicy, *, run_id: str
    ) -> OutboundDecision:
        return OutboundDecision(
            allowed=True,
            url=config.endpoint_url,
            reason="allowed",
            host="receiver.example.com",
            scheme="https",
            resolved_addresses=("198.51.100.24",),
        )

    monkeypatch.setattr(delivery_module, "evaluate_outbound_url", evaluate_outbound_url)

    def request(
        host: str,
        address: str,
        port: int,
        path: str,
        body: bytes | None,
        headers: Mapping[str, str],
        *,
        timeout: float,
        deadline: float,
        method: str = "POST",
    ) -> tuple[int, Mapping[str, str], bytes]:
        observed_addresses.append(address)
        return 200, {"content-type": "application/json"}, receipt_body

    vars(client)["_request"] = request
    client.deliver(envelope)

    assert observed_addresses == ["198.51.100.24"]


def test_reconcile_queries_the_same_occurrence_receipt() -> None:
    client = _delivery(attempts=1)
    envelope = _envelope()
    requests: list[tuple[str, str | None]] = []

    def request(
        host: str,
        address: str,
        port: int,
        path: str,
        body: bytes | None,
        headers: Mapping[str, str],
        *,
        timeout: float,
        deadline: float,
        method: str = "POST",
    ) -> tuple[int, Mapping[str, str], bytes]:
        requests.append((path, method))
        assert body is None
        return 404, {"content-type": "application/json"}, b"{}"

    vars(client)["_request"] = request

    assert client.reconcile(envelope) is None
    assert requests == [
        (
            "/base/v1/schedules/schedule%2Falpha/occurrences/" + envelope.occurrence_id,
            "GET",
        )
    ]


def test_delivery_configuration_cannot_exceed_frozen_time_budget() -> None:
    with pytest.raises(ValueError, match="supported bounds"):
        DeliveryConfig(
            endpoint_url="https://receiver.example.com/base",
            credential_ref=SecretRef("env", "receiver", "token"),
            outbound_policy=OutboundPolicy(
                allowed_hosts=("receiver.example.com",),
                max_response_bytes=65_536,
            ),
            max_elapsed_seconds=301,
        )
