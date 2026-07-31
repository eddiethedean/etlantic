"""Bounded connector observability event helpers (no rows / no secrets)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from etlantic.connectors.cdk.config import is_secret_like_key

DEFAULT_MAX_EVENT_BYTES = 8_192
DEFAULT_MAX_METADATA_KEYS = 32
DEFAULT_MAX_STRING_LEN = 512


def _truncate_str(value: str, *, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def _sanitize(value: Any, *, max_string_len: int, depth: int = 0) -> Any:
    if depth > 4:
        return "<truncated>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _truncate_str(value, max_len=max_string_len)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for index, (key, child) in enumerate(value.items()):
            if index >= DEFAULT_MAX_METADATA_KEYS:
                out["__truncated__"] = True
                break
            key_s = str(key)
            if is_secret_like_key(key_s):
                out[key_s] = "***"
                continue
            out[key_s] = _sanitize(
                child, max_string_len=max_string_len, depth=depth + 1
            )
        return out
    if isinstance(value, (list, tuple)):
        items = [
            _sanitize(item, max_string_len=max_string_len, depth=depth + 1)
            for item in list(value)[:DEFAULT_MAX_METADATA_KEYS]
        ]
        if len(value) > DEFAULT_MAX_METADATA_KEYS:
            items.append("<truncated>")
        return items
    return _truncate_str(type(value).__name__, max_len=max_string_len)


def emit_connector_event(
    event_type: str,
    *,
    provider: str | None = None,
    run_id: str | None = None,
    code: str | None = None,
    message: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    max_bytes: int = DEFAULT_MAX_EVENT_BYTES,
    max_string_len: int = DEFAULT_MAX_STRING_LEN,
) -> dict[str, Any]:
    """Build a bounded, secret-free connector event dict.

    Does not include row payloads or resolved configuration. Oversized
    metadata is truncated; the returned dict always serializes under
    *max_bytes* when possible.
    """
    event: dict[str, Any] = {
        "schema": "etlantic.connector_event/1",
        "event_type": str(event_type),
    }
    if provider is not None:
        event["provider"] = str(provider)
    if run_id is not None:
        event["run_id"] = str(run_id)
    if code is not None:
        event["code"] = str(code)
    if message is not None:
        event["message"] = _truncate_str(str(message), max_len=max_string_len)
    if metadata:
        event["metadata"] = _sanitize(dict(metadata), max_string_len=max_string_len)

    encoded = json.dumps(event, sort_keys=True, default=str)
    if len(encoded.encode("utf-8")) <= max_bytes:
        return event

    # Drop metadata first, then truncate message.
    slim = {k: v for k, v in event.items() if k != "metadata"}
    slim["metadata"] = {"truncated": True, "reason": "max_bytes"}
    if "message" in slim:
        slim["message"] = _truncate_str(str(slim["message"]), max_len=128)
    return slim


__all__ = [
    "DEFAULT_MAX_EVENT_BYTES",
    "DEFAULT_MAX_METADATA_KEYS",
    "DEFAULT_MAX_STRING_LEN",
    "emit_connector_event",
]
