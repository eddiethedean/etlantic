"""Cross-backend write-semantics parity helpers."""

from __future__ import annotations

from typing import Any

from etlantic.reliability import WriteIntent, WriteMode

SUPPORTED_WRITE_MODES = (
    WriteMode.APPEND,
    WriteMode.OVERWRITE,
    WriteMode.MERGE,
    WriteMode.UPSERT,
    WriteMode.NO_WRITE,
)


def assert_write_intent_parity(
    backends: dict[str, Any],
    *,
    subject_id: str,
    mode: WriteMode,
) -> dict[str, Any]:
    """Assert each backend can declare the same write intent vocabulary.

    ``backends`` maps engine name → object with ``supports_write_mode(mode)``
    or a ``capabilities`` mapping containing write mode strings.
    """
    intent = WriteIntent(subject_id=subject_id, mode=mode)
    results: dict[str, Any] = {"intent": intent.to_dict(), "backends": {}}
    for engine, backend in backends.items():
        supports = False
        if hasattr(backend, "supports_write_mode"):
            supports = bool(backend.supports_write_mode(mode))
        elif hasattr(backend, "capabilities"):
            caps = backend.capabilities
            if hasattr(caps, "supports"):
                supports = bool(caps.supports(mode.value) or caps.supports("write"))
            elif isinstance(caps, dict):
                supports = mode.value in caps or "write" in caps
        else:
            raise AssertionError(
                f"Backend {engine!r} must expose supports_write_mode() or "
                "capabilities for write-semantics parity checks"
            )
        results["backends"][engine] = {"supports": supports}
        if not supports:
            raise AssertionError(
                f"Backend {engine!r} does not support write mode {mode.value!r}"
            )
    return results


def run_write_semantics_parity_suite(
    backends: dict[str, Any],
    *,
    subject_id: str = "parity",
    modes: tuple[WriteMode, ...] = (WriteMode.APPEND, WriteMode.OVERWRITE),
) -> list[dict[str, Any]]:
    """Run parity checks for shared write intents across backends."""
    return [
        assert_write_intent_parity(backends, subject_id=subject_id, mode=mode)
        for mode in modes
    ]
