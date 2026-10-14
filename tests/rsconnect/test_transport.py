"""Actual verified TLS I/O, including HTTPResponse's closing-socket handoff."""

from __future__ import annotations

import json
import os
import socket
import ssl
import subprocess
import sys
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path

import pytest
from etlantic_rsconnect import (
    DeliveryConfig,
    DeliveryError,
    HttpsTriggerDelivery,
    OccurrenceContext,
    build_trigger_bundle,
    build_trigger_envelope,
)

from etlantic.outbound import OutboundPolicy
from etlantic.secrets import SecretRef

_FIXTURES = Path(__file__).with_name("fixtures")
_CERT = _FIXTURES / "tls-cert.pem"
_KEY = _FIXTURES / "tls-key.pem"


class _SlowTlsReceiver:
    def __init__(self, fault: str, close_response: bool) -> None:
        self.fault = fault
        self.close_response = close_response
        self.stop = threading.Event()
        self.completed_drip = threading.Event()
        self.request_count = 0
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(2)
        self.endpoint = f"https://127.0.0.1:{self.listener.getsockname()[1]}"
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(_CERT, _KEY)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def drip(self, conn: ssl.SSLSocket, payload: bytes) -> None:
        for byte in payload:
            if self.stop.is_set():
                return
            conn.sendall(bytes([byte]))
            if self.stop.wait(0.03):
                return
        self.completed_drip.set()

    def serve(self) -> None:
        try:
            raw, _ = self.listener.accept()
            raw.settimeout(2)
            with self.context.wrap_socket(raw, server_side=True) as conn:
                request = bytearray()
                while b"\r\n\r\n" not in request:
                    chunk = conn.recv(8192)
                    if not chunk:
                        return
                    request.extend(chunk)
                    if len(request) > 32_768:
                        raise AssertionError("unexpectedly large test request")
                self.request_count += 1
                connection = "close" if self.close_response else "keep-alive"
                headers = (
                    "HTTP/1.1 200 OK\r\n"
                    f"Connection: {connection}\r\n"
                    "Content-Type: application/json\r\n"
                    "Transfer-Encoding: chunked\r\n\r\n"
                ).encode()
                if self.fault == "headers":
                    self.drip(conn, headers)
                    return
                conn.sendall(headers)
                if self.fault == "chunk_header":
                    # Leading zeroes are legal chunk-size syntax. Each byte
                    # arrives within the socket timeout, but the line takes
                    # longer than the total deadline to complete.
                    self.drip(conn, b"0" * 60 + b"1\r\nx\r\n0\r\n\r\n")
                elif self.fault == "trailers":
                    conn.sendall(b"0\r\n")
                    self.drip(conn, b"X-Test: " + b"a" * 60 + b"\r\n\r\n")
                else:
                    raise AssertionError("unknown TLS test fault")
        except OSError:
            # Deadline interruption closes the connection during a write.
            return


@contextmanager
def _receiver(fault: str, close_response: bool) -> Generator[_SlowTlsReceiver]:
    receiver = _SlowTlsReceiver(fault, close_response)
    try:
        yield receiver
    finally:
        receiver.stop.set()
        with suppress(OSError):
            receiver.listener.close()
        receiver.thread.join(3)
        assert not receiver.thread.is_alive(), "TLS fixture did not shut down"


def _policy() -> OutboundPolicy:
    return OutboundPolicy(
        allowed_hosts=("127.0.0.1",),
        allow_loopback=True,
        allow_private=True,
        timeout_seconds=1,
        max_response_bytes=65_536,
    )


@pytest.mark.parametrize("fault", ["headers", "chunk_header", "trailers"])
@pytest.mark.parametrize("close_response", [True, False])
def test_client_deadline_interrupts_verified_tls_reads(
    fault: str, close_response: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSL_CERT_FILE", str(_CERT))
    with _receiver(fault, close_response) as receiver:
        client = HttpsTriggerDelivery(
            DeliveryConfig(
                endpoint_url=receiver.endpoint,
                credential_ref=SecretRef("env", "receiver", "token"),
                outbound_policy=_policy(),
                timeout_seconds=1,
                max_elapsed_seconds=0.2,
                max_attempts=1,
            ),
            lambda _ref: "synthetic-trigger-token",
        )
        envelope = build_trigger_envelope(
            schedule_id="schedule-1",
            schedule_revision_id="revision-1",
            timer_owner_generation=1,
            occurrence=OccurrenceContext(
                scheduled_at="2026-10-13T12:00:00Z",
                delivery_attempt_id="attempt-1",
                correlation_id="correlation-1",
            ),
        )
        started = time.monotonic()
        with pytest.raises(DeliveryError) as error:
            client.deliver(envelope)
        assert time.monotonic() - started < 1
        assert error.value.uncertain
        assert "synthetic-trigger-token" not in str(error.value)
        assert receiver.request_count == 1
        assert not receiver.completed_drip.is_set()


@pytest.mark.parametrize("fault", ["chunk_header", "trailers"])
def test_generated_runner_deadline_survives_closing_tls_response(
    fault: str, tmp_path: Path
) -> None:
    with _receiver(fault, True) as receiver:
        bundle = build_trigger_bundle(
            schedule_id="schedule-1",
            schedule_revision_id="revision-1",
            timer_owner_generation=1,
            endpoint_url=receiver.endpoint,
            credential_ref=SecretRef("env", "receiver", "token"),
            credential_env="ETLANTIC_TRIGGER_TOKEN",
            outbound_policy=_policy(),
            timeout_seconds=1,
            # The generated subprocess imports its runtime before starting
            # the delivery deadline. Leave enough time for a loaded Windows
            # runner to reach the TLS request, then interrupt the deliberately
            # slow response body.
            max_elapsed_seconds=1,
            max_attempts=1,
        )
        target = bundle.write_to(tmp_path / "content")
        config_path = target / "etlantic-trigger.json"
        config = json.loads(config_path.read_text())
        # Only this fixture provides synthetic trusted invocation context.
        config["occurrence_context_provider"] = "test-fixture"
        config_path.write_text(json.dumps(config))
        env = {
            "SSL_CERT_FILE": str(_CERT),
            "ETLANTIC_TRIGGER_ARMED": "true",
            "ETLANTIC_TRIGGER_TOKEN": "synthetic-trigger-token",
            "ETLANTIC_SCHEDULED_AT": "2026-10-13T12:00:00Z",
            "ETLANTIC_DELIVERY_ATTEMPT_ID": "attempt-1",
            "ETLANTIC_CORRELATION_ID": "correlation-1",
        }
        if system_root := os.environ.get("SYSTEMROOT"):
            env["SYSTEMROOT"] = system_root
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, str(target / "etlantic-trigger.py")],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        assert time.monotonic() - started < 4
        assert result.returncode != 0
        assert "synthetic-trigger-token" not in result.stdout + result.stderr
        assert receiver.request_count == 1
        assert not receiver.completed_drip.is_set()
