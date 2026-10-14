"""Standalone source copied into a Connect trigger bundle.

This module intentionally uses only the Python standard library. It is not
imported by the ETLantic runtime and is copied verbatim into rendered content.
"""

RUNNER_SOURCE = r"""from __future__ import annotations
import hashlib
import http.client
import ipaddress
import json
import os
import random
import socket
import ssl
import threading
import time
from queue import Empty, Queue
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, urlsplit

CONFIG = json.loads(Path(__file__).with_name("etlantic-trigger.json").read_text())
MAX_RESPONSE_BYTES = CONFIG["max_response_bytes"]
RECEIPT_FIELDS = {
    "schema", "status", "firing_status", "schedule_id", "schedule_revision_id",
    "occurrence_id", "submission_id", "run_id", "status_reference", "duplicate",
}
SKIP_STATUSES = {"skipped_overlap", "skipped_misfire", "skipped_window", "failed_preparation"}
BLOCKED_HOSTS = {"metadata", "metadata.google.internal", "169.254.169.254"}

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, port, timeout, deadline):
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self.address = address
        self.deadline = deadline
        self.transport_socket = None
    def connect(self):
        sock = socket.create_connection((self.address, self.port), self.timeout)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            sock.close()
            raise TimeoutError("receiver connection exceeded the delivery deadline")
        sock.settimeout(min(self.timeout, remaining))
        try:
            tls_sock = self._context.wrap_socket(sock, server_hostname=self.host, do_handshake_on_connect=False)
            self.sock = tls_sock
            self.transport_socket = tls_sock
            if time.monotonic() >= self.deadline:
                raise TimeoutError("receiver connection exceeded the delivery deadline")
            tls_sock.do_handshake()
        except Exception:
            if self.transport_socket is not None:
                self.transport_socket.close()
            sock.close()
            raise

def interrupt(conn):
    sock = conn.transport_socket
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass

def bounded_getaddrinfo(host, port, timeout):
    result = Queue(maxsize=1)
    def resolve():
        try:
            result.put((True, socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
        except BaseException as exc:
            result.put((False, exc))
    worker = threading.Thread(target=resolve, daemon=True)
    worker.start()
    try:
        succeeded, value = result.get(timeout=max(0.0, timeout))
    except Empty:
        raise TimeoutError("receiver DNS resolution exceeded the delivery deadline") from None
    if not succeeded:
        raise value
    return value

def allowed_ip(value):
    ip = ipaddress.ip_address(value)
    if ip.is_loopback and not CONFIG["allow_loopback"]:
        return False
    if ip.is_link_local and not CONFIG["allow_link_local"]:
        return False
    if ip.is_private and not CONFIG["allow_private"]:
        return False
    if ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        return False
    if str(ip) == "169.254.169.254":
        return False
    return True

def occurrence():
    scheduled_at = os.environ.get("ETLANTIC_SCHEDULED_AT", "")
    attempt_id = os.environ.get("ETLANTIC_DELIVERY_ATTEMPT_ID", "")
    correlation_id = os.environ.get("ETLANTIC_CORRELATION_ID", "")
    if not scheduled_at or not attempt_id or not correlation_id:
        raise RuntimeError("no qualified scheduled occurrence context; refusing delivery")
    try:
        parsed = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    except ValueError:
        raise RuntimeError("scheduled occurrence timestamp is invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("scheduled occurrence must include a timezone")
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if scheduled_at != canonical:
        raise RuntimeError("scheduled occurrence must use canonical UTC form")
    for value in (attempt_id, correlation_id):
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise RuntimeError("scheduled occurrence metadata is invalid")
    semantic = json.dumps(
        [CONFIG["schedule_id"], CONFIG["schedule_revision_id"], scheduled_at],
        separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return {
        "schema": CONFIG["schema"],
        "schedule_id": CONFIG["schedule_id"],
        "schedule_revision_id": CONFIG["schedule_revision_id"],
        "timer_owner_generation": CONFIG["timer_owner_generation"],
        "occurrence_id": "occ-" + hashlib.sha256(semantic).hexdigest(),
        "scheduled_at": scheduled_at,
        "delivery_attempt_id": attempt_id,
        "correlation_id": correlation_id,
    }

def safe_receipt(receipt, envelope, http_status):
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
        return False
    allowed = {"pending"} if http_status == 202 else {"accepted", "skipped"}
    if (receipt.get("schema") != "etlantic.trigger_receipt/1" or
        receipt.get("status") not in allowed or
        receipt.get("schedule_id") != envelope["schedule_id"] or
        receipt.get("schedule_revision_id") != envelope["schedule_revision_id"] or
        receipt.get("occurrence_id") != envelope["occurrence_id"] or
        type(receipt.get("duplicate")) is not bool):
        return False
    status = receipt["status"]
    firing = receipt.get("firing_status")
    submission_id = receipt.get("submission_id")
    for key in ("schedule_id", "schedule_revision_id", "occurrence_id"):
        value = receipt.get(key)
        if not isinstance(value, str) or not value.strip():
            return False
    if status == "pending":
        if firing != "accepted" or submission_id is not None:
            return False
    elif status == "accepted":
        if (
            firing != "accepted"
            or not isinstance(submission_id, str)
            or not submission_id.strip()
        ):
            return False
    else:
        if firing not in SKIP_STATUSES:
            return False
        if submission_id is not None and (
            not isinstance(submission_id, str) or not submission_id.strip()
        ):
            return False
    for key in ("run_id", "status_reference"):
        value = receipt.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            return False
    status_reference = receipt.get("status_reference")
    if status_reference is not None:
        expected_ref = "/v1/schedules/" + quote(envelope["schedule_id"], safe="") + "/occurrences/" + quote(envelope["occurrence_id"], safe="")
        if status_reference != expected_ref:
            return False
    return True

def read_bounded(response, conn, deadline):
    content_length = response.getheader("Content-Length")
    if content_length is not None:
        try:
            if int(content_length) < 0 or int(content_length) > MAX_RESPONSE_BYTES:
                raise RuntimeError("receiver response exceeds its byte bound")
        except ValueError:
            raise RuntimeError("receiver returned an invalid response length") from None
    body = bytearray()
    while len(body) <= MAX_RESPONSE_BYTES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("receiver response exceeded the delivery deadline")
        if conn.transport_socket is not None:
            conn.transport_socket.settimeout(min(CONFIG["timeout_seconds"], remaining))
        chunk = response.read1(min(8192, MAX_RESPONSE_BYTES + 1 - len(body)))
        if not chunk:
            break
        body.extend(chunk)
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("receiver response exceeds its byte bound")
    return bytes(body)

def retry_delay(attempt, retry_after, remaining):
    delay = min(0.25 * (2 ** attempt) + random.random() * 0.1, 2.0)
    if retry_after:
        try:
            requested = max(0.0, float(retry_after))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                requested = max(0.0, (retry_at.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                requested = 0.0
        delay = max(delay, min(requested, CONFIG["max_retry_after_seconds"]))
    time.sleep(min(delay, max(0.0, remaining)))

def main():
    if os.environ.get("ETLANTIC_TRIGGER_ARMED", "false").lower() != "true":
        print(json.dumps({"status": "disarmed"}))
        return
    if not CONFIG.get("occurrence_context_provider"):
        raise RuntimeError("no qualified Connect occurrence provider; refusing delivery")
    envelope = occurrence()
    endpoint = urlsplit(CONFIG["endpoint_url"])
    if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or
        endpoint.password or endpoint.query or endpoint.fragment):
        raise RuntimeError("configured receiver URL is invalid")
    host = endpoint.hostname.lower()
    if host in BLOCKED_HOSTS or host not in CONFIG["allowed_hosts"]:
        raise RuntimeError("receiver host is outside the configured allowlist")
    started = time.monotonic()
    deadline = started + CONFIG["max_elapsed_seconds"]
    try:
        infos = bounded_getaddrinfo(
            host,
            endpoint.port or 443,
            deadline - time.monotonic(),
        )
    except OSError:
        raise RuntimeError("receiver DNS resolution failed") from None
    except TimeoutError:
        raise RuntimeError("receiver DNS resolution exceeded the delivery deadline") from None
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not addresses or any(not allowed_ip(address) for address in addresses):
        raise RuntimeError("receiver DNS result is denied by outbound policy")
    token = os.environ.get(CONFIG["credential_env"], "")
    if not token or any(char in token for char in "\r\n\x00"):
        raise RuntimeError("receiver credential is unavailable")
    prefix = endpoint.path.rstrip("/")
    path = prefix + "/v1/schedules/" + quote(envelope["schedule_id"], safe="") + "/external-trigger"
    body = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json", "Connection": "close"}
    last_error = "receiver response was lost or unavailable"
    request_attempts = 0
    for attempt in range(CONFIG["max_attempts"]):
        retry_after = None
        transient = False
        for address in addresses:
            if request_attempts >= CONFIG["max_attempts"]:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            request_deadline = min(
                deadline, time.monotonic() + CONFIG["timeout_seconds"]
            )
            request_timeout = request_deadline - time.monotonic()
            if request_timeout <= 0:
                break
            request_attempts += 1
            conn = PinnedHTTPS(
                host,
                address,
                endpoint.port or 443,
                request_timeout,
                request_deadline,
            )
            deadline_timer = threading.Timer(
                max(0.0, request_deadline - time.monotonic()), interrupt, args=(conn,)
            )
            deadline_timer.daemon = True
            deadline_timer.start()
            response = None
            try:
                conn.request("POST", path, body=body, headers=headers)
                response = conn.getresponse()
                data = read_bounded(response, conn, request_deadline)
                if response.status in (429, 500, 502, 503, 504):
                    retry_after = response.getheader("Retry-After")
                    last_error = "receiver returned a transient error"
                    transient = True
                    break
                if response.status not in (200, 202):
                    raise RuntimeError("receiver rejected the trigger")
                media_type = (response.getheader("Content-Type") or "").partition(";")[0].strip().lower()
                if media_type != "application/json" and not media_type.endswith("+json"):
                    raise RuntimeError("receiver returned a non-JSON receipt")
                def unique_pairs(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError("duplicate receipt field")
                        result[key] = value
                    return result
                try:
                    receipt = json.loads(data.decode("utf-8"), object_pairs_hook=unique_pairs)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
                    raise RuntimeError("receiver returned an invalid receipt") from None
                if not safe_receipt(receipt, envelope, response.status):
                    raise RuntimeError("receiver receipt does not match the submitted occurrence")
                print(json.dumps({"status": receipt["status"], "occurrence_id": envelope["occurrence_id"]}))
                return
            except (OSError, TimeoutError, http.client.HTTPException, ssl.SSLError):
                last_error = "receiver response was lost or unavailable"
            finally:
                deadline_timer.cancel()
                if response is not None:
                    response.close()
                conn.close()
                if conn.transport_socket is not None:
                    conn.transport_socket.close()
        remaining = deadline - time.monotonic()
        if attempt + 1 < CONFIG["max_attempts"] and remaining > 0:
            retry_delay(attempt, retry_after if transient else None, remaining)
    raise RuntimeError(last_error + "; reconcile the same occurrence")

if __name__ == "__main__":
    main()
"""
