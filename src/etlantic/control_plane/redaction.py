"""Secret-free serialization helpers for control-plane errors and events.

Reuses the runtime redaction primitives so CP1 SSE frames, problem details,
and report stubs never emit resolved secrets or secret-like key values.
"""

from __future__ import annotations

from typing import Any

from etlantic.runtime.logging import redact_message, redact_value

REDACTED = "***"


def redact_control_plane_payload(value: Any) -> Any:
    """Recursively redact secret-like keys and inline credentials."""
    return redact_value(value)


def redact_control_plane_text(text: str) -> str:
    """Redact free-form problem detail / message text."""
    return redact_message(text)


def assert_no_secrets(blob: str, *, sentinel: str = "super-secret-token") -> None:
    """Raise ``AssertionError`` when a known sentinel secret appears in ``blob``."""
    if sentinel and sentinel in blob:
        raise AssertionError(
            f"control-plane payload leaked secret sentinel {sentinel!r}"
        )


__all__ = [
    "REDACTED",
    "assert_no_secrets",
    "redact_control_plane_payload",
    "redact_control_plane_text",
]
