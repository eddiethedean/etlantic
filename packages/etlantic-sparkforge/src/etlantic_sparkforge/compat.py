"""Compatibility re-export — use ``medallantic.compat`` instead."""

from __future__ import annotations

from medallantic.compat import (
    COMPATIBILITY_MATRIX,
    assert_delta_capabilities,
    retry_policy_from_sparkforge,
    write_mode_from_sparkforge,
    write_mode_metadata,
)

__all__ = [
    "COMPATIBILITY_MATRIX",
    "assert_delta_capabilities",
    "retry_policy_from_sparkforge",
    "write_mode_from_sparkforge",
    "write_mode_metadata",
]
