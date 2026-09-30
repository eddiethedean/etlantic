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


def redact_or_preserve_execution_envelope(text: str | None) -> str | None:
    """Preserve a verified secret-free envelope as canonical JSON.

    Generic text redaction can corrupt harmless secret references inside an
    execution envelope, making the accepted plan unverifiable. Envelopes have
    their own strict validator, so retain their canonical bytes only after
    revalidating the schema, fingerprints, and secret-free fields. Unverified
    text continues through the ordinary redactor.
    """
    if text is None:
        return None
    try:
        from etlantic.control_plane.execution_envelope import ExecutionEnvelope

        return ExecutionEnvelope.from_json(text).to_json()
    except Exception:
        return redact_control_plane_text(text)


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
    "redact_or_preserve_execution_envelope",
]
