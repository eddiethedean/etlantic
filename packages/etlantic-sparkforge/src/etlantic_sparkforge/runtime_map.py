"""Compatibility re-export — use ``medallantic.runtime_map`` instead."""

from __future__ import annotations

from medallantic.runtime_map import (
    bind_debug_session,
    debug_request_from_sparkforge,
    intent_from_sparkforge,
    selection_from_sparkforge,
)

__all__ = [
    "bind_debug_session",
    "debug_request_from_sparkforge",
    "intent_from_sparkforge",
    "selection_from_sparkforge",
]
