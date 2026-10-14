"""Bounded HTTPS delivery for the ETLantic trigger envelope/1 contract."""

from __future__ import annotations

import http.client
import json
import math
import random
import socket
import ssl
import threading
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from contextvars import copy_context
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from queue import Empty, Queue
from typing import Any, cast
from urllib.parse import quote, urlsplit

from etlantic.control_plane import (
    TriggerEnvelope,
    TriggerReceipt,
    external_occurrence_id,
)
from etlantic.outbound import (
    OutboundDecision,
    OutboundPolicy,
    evaluate_outbound_url,
)
from etlantic.secrets import SecretRef, SecretValue
from etlantic_rsconnect.limits import (
    MAX_DELIVERY_ATTEMPTS,
    MAX_DELIVERY_ELAPSED_SECONDS,
    MAX_REQUEST_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
    MAX_RETRY_AFTER_SECONDS,
)

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_RETRYABLE_EXCEPTIONS = (
    OSError,
    TimeoutError,
    http.client.HTTPException,
    ssl.SSLError,
)
_RESOLVER_SLOTS = threading.BoundedSemaphore(4)
_CREDENTIAL_SLOTS = threading.BoundedSemaphore(4)


class DeliveryError(RuntimeError):
    """A redacted, bounded trigger-delivery failure."""

    def __init__(self, message: str, *, uncertain: bool = False) -> None:
        super().__init__(message)
        self.uncertain = uncertain


class _StrictChunkedHTTPResponse(http.client.HTTPResponse):
    """Require the final chunk and trailer terminator before accepting a body."""

    def _read_and_discard_trailer(self) -> None:
        consumed = 0
        while True:
            line = self.fp.readline(65_537)
            consumed += len(line)
            if consumed > 65_536 or len(line) > 65_536:
                raise http.client.LineTooLong("response trailer")
            if not line or not line.endswith(b"\r\n"):
                raise http.client.IncompleteRead(b"")
            if line == b"\r\n":
                return


@dataclass(frozen=True, slots=True)
class OccurrenceContext:
    """Nominal slot resolved by a trusted platform/runtime integration."""

    scheduled_at: str
    delivery_attempt_id: str
    correlation_id: str

    def __post_init__(self) -> None:
        try:
            scheduled = datetime.fromisoformat(self.scheduled_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("scheduled_at must be canonical UTC ISO-8601") from exc
        if scheduled.tzinfo is None or scheduled.utcoffset() is None:
            raise ValueError("scheduled_at must be canonical UTC ISO-8601")
        if (
            scheduled.astimezone(UTC).isoformat().replace("+00:00", "Z")
            != self.scheduled_at
        ):
            raise ValueError("scheduled_at must be canonical UTC ISO-8601")
        for name in ("delivery_attempt_id", "correlation_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{name} must contain 1 to 256 characters")


def build_trigger_envelope(
    *,
    schedule_id: str,
    schedule_revision_id: str,
    timer_owner_generation: int,
    occurrence: OccurrenceContext,
) -> TriggerEnvelope:
    """Build the canonical wire value from a previously resolved nominal slot."""
    return TriggerEnvelope(
        schedule_id=schedule_id,
        schedule_revision_id=schedule_revision_id,
        timer_owner_generation=timer_owner_generation,
        occurrence_id=external_occurrence_id(
            schedule_id, schedule_revision_id, occurrence.scheduled_at
        ),
        scheduled_at=occurrence.scheduled_at,
        delivery_attempt_id=occurrence.delivery_attempt_id,
        correlation_id=occurrence.correlation_id,
    )


@dataclass(frozen=True, slots=True)
class DeliveryConfig:
    """Secret-free explicit receiver and bounded transport configuration."""

    endpoint_url: str
    credential_ref: SecretRef
    outbound_policy: OutboundPolicy
    timeout_seconds: float = 10.0
    max_attempts: int = 3
    max_elapsed_seconds: float = 30.0
    max_response_bytes: int = 65_536
    max_retry_after_seconds: float = 5.0

    def __post_init__(self) -> None:
        parsed = urlsplit(self.endpoint_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "endpoint_url must be HTTPS without user info, query, or fragment"
            )
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("endpoint_url port is invalid") from exc
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("endpoint_url port is invalid")
        if (
            type(self.timeout_seconds) not in (int, float)
            or type(self.max_elapsed_seconds) not in (int, float)
            or not math.isfinite(self.timeout_seconds)
            or not math.isfinite(self.max_elapsed_seconds)
            or self.timeout_seconds <= 0
            or self.max_elapsed_seconds <= 0
            or self.timeout_seconds > MAX_REQUEST_TIMEOUT_SECONDS
            or self.max_elapsed_seconds > MAX_DELIVERY_ELAPSED_SECONDS
        ):
            raise ValueError("delivery timeouts are outside the supported bounds")
        if (
            type(self.max_attempts) is not int
            or not 1 <= self.max_attempts <= MAX_DELIVERY_ATTEMPTS
        ):
            raise ValueError(
                f"max_attempts must be between 1 and {MAX_DELIVERY_ATTEMPTS}"
            )
        if (
            type(self.max_response_bytes) is not int
            or not 1 <= self.max_response_bytes <= MAX_RESPONSE_BYTES
        ):
            raise ValueError(
                f"max_response_bytes must be between 1 and {MAX_RESPONSE_BYTES}"
            )
        if (
            type(self.max_retry_after_seconds) not in (int, float)
            or not math.isfinite(self.max_retry_after_seconds)
            or self.max_retry_after_seconds < 0
            or self.max_retry_after_seconds > MAX_RETRY_AFTER_SECONDS
        ):
            raise ValueError("max_retry_after_seconds is outside the supported bounds")
        if "https" not in {
            scheme.lower() for scheme in self.outbound_policy.allowed_schemes
        }:
            raise ValueError("outbound policy must allow HTTPS")
        if self.outbound_policy.forward_ambient_credentials:
            raise ValueError("ambient credential forwarding is prohibited")
        if self.timeout_seconds > self.outbound_policy.timeout_seconds:
            raise ValueError("delivery timeout exceeds the outbound policy")
        if self.max_response_bytes > self.outbound_policy.max_response_bytes:
            raise ValueError("response bound exceeds the outbound policy")
        if self.outbound_policy.allow_redirects:
            raise ValueError("trigger delivery does not allow redirects")
        if (
            type(self.outbound_policy.timeout_seconds) not in (int, float)
            or not math.isfinite(self.outbound_policy.timeout_seconds)
            or self.outbound_policy.timeout_seconds <= 0
            or type(self.outbound_policy.max_response_bytes) is not int
            or self.outbound_policy.max_response_bytes < 1
        ):
            raise ValueError("outbound policy bounds are invalid")
        if parsed.hostname.lower() not in {
            host.lower() for host in self.outbound_policy.allowed_hosts
        }:
            raise ValueError(
                "endpoint host must be explicitly present in outbound allowlist"
            )


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    receipt: TriggerReceipt
    attempts: int
    elapsed_seconds: float


class _PinnedHttpsConnection(http.client.HTTPSConnection):
    """HTTPS connection pinned to an already policy-checked IP address."""

    response_class = _StrictChunkedHTTPResponse

    def __init__(
        self,
        host: str,
        address: str,
        port: int,
        *,
        timeout: float,
        deadline: float,
        monotonic: Callable[[], float],
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(host, port=port, timeout=timeout, context=context)
        self._pinned_address = address
        self._ssl_context = context
        self._deadline = deadline
        self._monotonic = monotonic
        self.transport_socket: socket.socket | None = None

    def connect(self) -> None:
        sock = socket.create_connection((self._pinned_address, self.port), self.timeout)
        remaining = self._deadline - self._monotonic()
        if remaining <= 0:
            sock.close()
            raise TimeoutError("receiver connection exceeded the delivery deadline")
        sock.settimeout(min(self.timeout or remaining, remaining))
        # Keep the transport independently of HTTPConnection.sock, which is
        # cleared when a closing response takes ownership of its file object.
        try:
            tls_sock = self._ssl_context.wrap_socket(
                sock, server_hostname=self.host, do_handshake_on_connect=False
            )
            self.sock = tls_sock
            self.transport_socket = tls_sock
            if self._monotonic() >= self._deadline:
                raise TimeoutError("receiver connection exceeded the delivery deadline")
            tls_sock.do_handshake()
        except Exception:
            if self.transport_socket is not None:
                self.transport_socket.close()
            sock.close()
            raise


def _secret_text(value: object) -> str:
    if isinstance(value, SecretValue):
        value = value.get_secret_value()
    if (
        not isinstance(value, str)
        or not value
        or any(char in value for char in "\r\n\x00")
    ):
        raise DeliveryError("trigger credential could not be resolved")
    return value


def _json_object_without_duplicate_keys(body: bytes) -> Mapping[str, Any]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result

    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise DeliveryError(
            "receiver returned a malformed or ambiguous receipt", uncertain=True
        ) from None
    if not isinstance(value, Mapping):
        raise DeliveryError("receiver receipt must be a JSON object", uncertain=True)
    return cast(Mapping[str, Any], value)


class HttpsTriggerDelivery:
    """Send the same canonical occurrence through a policy-enforced HTTPS path.

    Secret resolvers execute in bounded daemon workers with the caller's
    contextvars. Providers must support background-thread calls. Timed-out
    results are discarded; a stuck provider cannot extend the caller's budget.
    """

    def __init__(
        self,
        config: DeliveryConfig,
        resolve_secret: Callable[[SecretRef], str | SecretValue],
        *,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        self.config = config
        self.resolve_secret = resolve_secret
        self._sleep = sleep
        self._monotonic = monotonic
        self._random = random_value

    def deliver(self, envelope: TriggerEnvelope) -> DeliveryResult:
        started = self._monotonic()
        body = json.dumps(
            envelope.to_dict(), separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        parsed = urlsplit(self.config.endpoint_url)
        deadline = started + self.config.max_elapsed_seconds
        addresses = self._destination(envelope.occurrence_id, deadline=deadline)
        token = self._credential(deadline=deadline)

        path_prefix = parsed.path.rstrip("/")
        path = (
            f"{path_prefix}/v1/schedules/{quote(envelope.schedule_id, safe='')}"
            "/external-trigger"
        )
        request_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Content-Length": str(len(body)),
            "Connection": "close",
        }
        last_error = "receiver delivery failed"
        for attempt in range(1, self.config.max_attempts + 1):
            remaining = self.config.max_elapsed_seconds - (self._monotonic() - started)
            if remaining <= 0:
                raise DeliveryError(
                    "trigger delivery deadline expired; reconcile occurrence receipt",
                    uncertain=True,
                )
            address = addresses[(attempt - 1) % len(addresses)]
            try:
                response = self._request(
                    parsed.hostname or "",
                    address,
                    parsed.port or 443,
                    path,
                    body,
                    request_headers,
                    timeout=min(self.config.timeout_seconds, remaining),
                    deadline=started + self.config.max_elapsed_seconds,
                )
            except _RETRYABLE_EXCEPTIONS:
                last_error = "receiver connection failed or response was lost"
                if attempt == self.config.max_attempts:
                    raise DeliveryError(
                        f"{last_error}; reconcile occurrence receipt",
                        uncertain=True,
                    ) from None
                self._backoff(attempt, started)
                continue
            status, headers, response_body = response
            if status in _RETRYABLE_STATUSES:
                if attempt == self.config.max_attempts:
                    raise DeliveryError(
                        f"receiver returned transient HTTP {status}; reconcile occurrence receipt",
                        uncertain=True,
                    )
                self._backoff(attempt, started, headers.get("retry-after"))
                continue
            if status not in (200, 202):
                raise DeliveryError(f"receiver rejected trigger with HTTP {status}")
            if not _is_json_content_type(headers.get("content-type")):
                raise DeliveryError(
                    "receiver returned a non-JSON receipt; reconcile occurrence",
                    uncertain=True,
                )
            raw_receipt = _json_object_without_duplicate_keys(response_body)
            try:
                receipt = TriggerReceipt.from_dict(raw_receipt)
            except Exception:
                raise DeliveryError(
                    "receiver receipt failed contract validation; reconcile occurrence",
                    uncertain=True,
                ) from None
            allowed_statuses = {"pending"} if status == 202 else {"accepted", "skipped"}
            if (
                receipt.status not in allowed_statuses
                or receipt.schedule_id != envelope.schedule_id
                or receipt.schedule_revision_id != envelope.schedule_revision_id
                or receipt.occurrence_id != envelope.occurrence_id
                or not self._valid_status_reference(receipt)
            ):
                raise DeliveryError(
                    "receiver receipt does not match the submitted occurrence; reconcile occurrence",
                    uncertain=True,
                )
            return DeliveryResult(
                receipt=receipt,
                attempts=attempt,
                elapsed_seconds=max(0.0, self._monotonic() - started),
            )
        raise DeliveryError("receiver delivery failed", uncertain=True)

    def reconcile(self, envelope: TriggerEnvelope) -> TriggerReceipt | None:
        """Read the retained receipt for this exact occurrence after uncertainty.

        A missing receipt returns ``None``; callers may then retry ``deliver``
        with the same envelope. This method never chooses a new scheduled slot.
        """
        started = self._monotonic()
        parsed = urlsplit(self.config.endpoint_url)
        deadline = started + self.config.max_elapsed_seconds
        addresses = self._destination(envelope.occurrence_id, deadline=deadline)
        token = self._credential(deadline=deadline)
        prefix = parsed.path.rstrip("/")
        path = (
            f"{prefix}/v1/schedules/{quote(envelope.schedule_id, safe='')}"
            f"/occurrences/{quote(envelope.occurrence_id, safe='')}"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Connection": "close",
        }
        last_status: int | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise DeliveryError(
                    "receipt reconciliation deadline expired", uncertain=True
                )
            address = addresses[(attempt - 1) % len(addresses)]
            try:
                response = self._request(
                    parsed.hostname or "",
                    address,
                    parsed.port or 443,
                    path,
                    None,
                    headers,
                    timeout=min(self.config.timeout_seconds, remaining),
                    deadline=deadline,
                    method="GET",
                )
            except _RETRYABLE_EXCEPTIONS:
                if attempt == self.config.max_attempts:
                    raise DeliveryError(
                        "receipt lookup failed; reconcile the occurrence",
                        uncertain=True,
                    ) from None
                self._backoff(attempt, started)
                continue
            status, response_headers, response_body = response
            last_status = status
            if status == 404:
                return None
            if status in _RETRYABLE_STATUSES:
                if attempt == self.config.max_attempts:
                    break
                self._backoff(attempt, started, response_headers.get("retry-after"))
                continue
            if status != 200:
                raise DeliveryError(
                    f"receiver receipt lookup returned HTTP {status}", uncertain=True
                )
            if not _is_json_content_type(response_headers.get("content-type")):
                raise DeliveryError(
                    "receiver returned a non-JSON receipt; reconcile occurrence",
                    uncertain=True,
                )
            receipt = self._parse_receipt(response_body)
            if not self._receipt_matches(receipt, envelope):
                raise DeliveryError(
                    "receiver receipt does not match the submitted occurrence",
                    uncertain=True,
                )
            return receipt
        raise DeliveryError(
            f"receipt lookup remained unavailable (HTTP {last_status})",
            uncertain=True,
        )

    def _destination(
        self, run_id: str, *, deadline: float | None = None
    ) -> tuple[str, ...]:
        parsed = urlsplit(self.config.endpoint_url)
        if parsed.hostname is None or parsed.hostname.lower() not in {
            host.lower() for host in self.config.outbound_policy.allowed_hosts
        }:
            raise DeliveryError("receiver destination denied by outbound policy")
        try:
            remaining = (
                self.config.max_elapsed_seconds
                if deadline is None
                else deadline - self._monotonic()
            )
            if remaining <= 0:
                raise TimeoutError("delivery deadline expired during DNS resolution")
            decision = _evaluate_outbound_url_bounded(
                self.config.endpoint_url,
                self.config.outbound_policy,
                run_id=run_id,
                timeout=remaining,
            )
        except TimeoutError:
            raise DeliveryError(
                "receiver DNS resolution exceeded the delivery deadline",
                uncertain=True,
            ) from None
        except Exception:
            raise DeliveryError(
                "receiver destination denied by outbound policy"
            ) from None
        if not decision.allowed or not decision.resolved_addresses:
            raise DeliveryError("receiver destination denied by outbound policy")
        addresses = decision.resolved_addresses
        if not addresses:
            raise DeliveryError("receiver destination denied by outbound policy")
        return addresses

    def _credential(self, *, deadline: float) -> str:
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise DeliveryError(
                "trigger credential resolution exceeded the delivery deadline"
            )
        if not _CREDENTIAL_SLOTS.acquire(blocking=False):
            raise DeliveryError("trigger credential resolver is saturated")
        # Never place a resolved credential in an abandoned queue. After a
        # timeout the worker discards its result, even if the provider returns.
        completed = threading.Event()
        lock = threading.Lock()
        abandoned = False
        resolved: str | None = None
        failed = False

        def resolve() -> None:
            nonlocal resolved, failed
            try:
                value = _secret_text(self.resolve_secret(self.config.credential_ref))
                with lock:
                    if not abandoned:
                        resolved = value
            except BaseException:
                with lock:
                    failed = True
            finally:
                _CREDENTIAL_SLOTS.release()
                completed.set()

        context = copy_context()
        worker = threading.Thread(
            target=context.run,
            args=(resolve,),
            name="etlantic-trigger-credential",
            daemon=True,
        )
        try:
            worker.start()
        except BaseException:
            _CREDENTIAL_SLOTS.release()
            raise
        finished = completed.wait(max(0.0, deadline - self._monotonic()))
        with lock:
            if not finished or self._monotonic() >= deadline:
                abandoned = True
                resolved = None
                raise DeliveryError(
                    "trigger credential resolution exceeded the delivery deadline"
                )
            if failed or resolved is None:
                raise DeliveryError("trigger credential could not be resolved")
            return resolved

    def _request(
        self,
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
        request_timeout = min(timeout, self.config.timeout_seconds)
        request_started = self._monotonic()
        request_deadline = min(deadline, request_started + request_timeout)
        if request_deadline <= request_started:
            raise TimeoutError("receiver request deadline expired")
        connection = _PinnedHttpsConnection(
            host,
            address,
            port,
            timeout=request_timeout,
            deadline=request_deadline,
            monotonic=self._monotonic,
            context=ssl.create_default_context(),
        )
        deadline_timer = threading.Timer(
            max(0.0, request_deadline - self._monotonic()),
            _interrupt_connection,
            args=(connection,),
        )
        deadline_timer.daemon = True
        deadline_timer.start()
        response: http.client.HTTPResponse | None = None
        try:
            connection.request(method, path, body=body, headers=dict(headers))
            response = connection.getresponse()
            response_headers: dict[str, str] = {}
            header_values: dict[str, list[str]] = {}
            for key, value in response.getheaders():
                normalized_key = key.lower()
                header_values.setdefault(normalized_key, []).append(value)
            content_lengths = header_values.get("content-length", [])
            transfer_encodings = header_values.get("transfer-encoding", [])
            if len(content_lengths) > 1 or len(transfer_encodings) > 1:
                raise DeliveryError(
                    "receiver returned ambiguous HTTP response framing; reconcile occurrence",
                    uncertain=True,
                )
            if content_lengths and transfer_encodings:
                raise DeliveryError(
                    "receiver returned conflicting HTTP response framing; reconcile occurrence",
                    uncertain=True,
                )
            for key, values in header_values.items():
                response_headers[key] = ", ".join(values)

            declared_length = content_lengths[0] if content_lengths else None
            declared_size: int | None = None
            if declared_length is not None:
                try:
                    normalized_length = declared_length.strip()
                    if (
                        not normalized_length.isascii()
                        or not normalized_length.isdigit()
                    ):
                        raise ValueError
                    declared_size = int(normalized_length)
                    if (
                        declared_size < 0
                        or declared_size > self.config.max_response_bytes
                    ):
                        raise DeliveryError(
                            "receiver response exceeds the configured byte limit",
                            uncertain=True,
                        )
                except ValueError:
                    raise DeliveryError(
                        "receiver returned an invalid response length",
                        uncertain=True,
                    ) from None
            if transfer_encodings and (
                transfer_encodings[0].strip().lower() != "chunked"
                or not response.chunked
            ):
                raise DeliveryError(
                    "receiver returned unsupported HTTP response framing; reconcile occurrence",
                    uncertain=True,
                )
            response_chunks = bytearray()
            while len(response_chunks) <= self.config.max_response_bytes:
                remaining = request_deadline - self._monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        "receiver response exceeded the per-request deadline"
                    )
                if connection.transport_socket is not None:
                    connection.transport_socket.settimeout(
                        min(request_timeout, remaining)
                    )
                chunk = response.read1(
                    min(8192, self.config.max_response_bytes + 1 - len(response_chunks))
                )
                if not chunk:
                    break
                response_chunks.extend(chunk)
            response_body = bytes(response_chunks)
            if len(response_body) > self.config.max_response_bytes:
                raise DeliveryError(
                    "receiver response exceeds the configured byte limit",
                    uncertain=True,
                )
            if declared_size is not None and len(response_body) != declared_size:
                raise DeliveryError(
                    "receiver response did not match its declared length; reconcile occurrence",
                    uncertain=True,
                )
            return response.status, response_headers, response_body
        finally:
            deadline_timer.cancel()
            if response is not None:
                response.close()
            connection.close()
            if connection.transport_socket is not None:
                connection.transport_socket.close()

    def _parse_receipt(self, body: bytes) -> TriggerReceipt:
        raw_receipt = _json_object_without_duplicate_keys(body)
        try:
            return TriggerReceipt.from_dict(raw_receipt)
        except Exception:
            raise DeliveryError(
                "receiver receipt failed contract validation; reconcile occurrence",
                uncertain=True,
            ) from None

    def _receipt_matches(
        self, receipt: TriggerReceipt, envelope: TriggerEnvelope
    ) -> bool:
        return (
            receipt.schedule_id == envelope.schedule_id
            and receipt.schedule_revision_id == envelope.schedule_revision_id
            and receipt.occurrence_id == envelope.occurrence_id
            and self._valid_status_reference(receipt)
        )

    def _backoff(
        self, attempt: int, started: float, retry_after: str | None = None
    ) -> None:
        remaining = self.config.max_elapsed_seconds - (self._monotonic() - started)
        if remaining <= 0:
            return
        delay = min(0.25 * (2 ** (attempt - 1)) + 0.1 * self._random(), 2.0)
        if retry_after is not None:
            try:
                requested = float(retry_after)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=UTC)
                    requested = max(
                        0.0,
                        (retry_at.astimezone(UTC) - datetime.now(UTC)).total_seconds(),
                    )
                except (TypeError, ValueError, OverflowError):
                    requested = 0.0
            delay = max(
                delay,
                min(max(0.0, requested), self.config.max_retry_after_seconds),
            )
        self._sleep(min(delay, remaining))

    @staticmethod
    def _valid_status_reference(receipt: TriggerReceipt) -> bool:
        if receipt.status_reference is None:
            return True
        expected = (
            f"/v1/schedules/{quote(receipt.schedule_id, safe='')}"
            f"/occurrences/{quote(receipt.occurrence_id, safe='')}"
        )
        return receipt.status_reference == expected


def _evaluate_outbound_url_bounded(
    url: str,
    policy: OutboundPolicy,
    *,
    run_id: str,
    timeout: float,
) -> OutboundDecision:
    """Run policy DNS resolution with a bounded caller wait.

    libc DNS calls cannot be cancelled from Python. A small daemon-worker pool
    bounds both caller latency and the number of abandoned resolver calls; once
    saturated, new resolutions fail closed until a worker returns.
    """
    if not _RESOLVER_SLOTS.acquire(blocking=False):
        raise TimeoutError("outbound resolver is saturated")
    result: Queue[tuple[bool, object]] = Queue(maxsize=1)

    def evaluate() -> None:
        try:
            result.put(
                (
                    True,
                    evaluate_outbound_url(url, policy, run_id=run_id),
                )
            )
        except BaseException as exc:
            result.put((False, exc))
        finally:
            _RESOLVER_SLOTS.release()

    worker = threading.Thread(
        target=evaluate, name="etlantic-outbound-dns", daemon=True
    )
    try:
        worker.start()
    except BaseException:
        _RESOLVER_SLOTS.release()
        raise
    try:
        succeeded, value = result.get(timeout=max(0.0, timeout))
    except Empty:
        raise TimeoutError("outbound DNS resolution timed out") from None
    if not succeeded:
        if isinstance(value, BaseException):
            raise value
        raise RuntimeError("outbound DNS resolution failed")
    return cast(OutboundDecision, value)


def _interrupt_connection(connection: _PinnedHttpsConnection) -> None:
    sock = connection.transport_socket
    if sock is None:
        return
    with suppress(OSError):
        sock.shutdown(socket.SHUT_RDWR)
    with suppress(OSError):
        sock.close()


def _is_json_content_type(value: str | None) -> bool:
    if value is None:
        return False
    media_type = value.partition(";")[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")
