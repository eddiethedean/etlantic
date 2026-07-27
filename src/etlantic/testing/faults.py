"""Public failure-injection helpers for plugin and resilience conformance (0.23)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from etlantic.runtime.faults import (
    FaultBoundary,
    FaultSpec,
    FaultTrigger,
    active_faults,
    clear_faults,
    fault_injection_enabled,
    maybe_inject,
    maybe_inject_async,
    register_faults,
    reset_fault_counts,
)

__all__ = [
    "FaultBoundary",
    "FaultSpec",
    "FaultTrigger",
    "clear_faults",
    "fault_injection_enabled",
    "maybe_inject",
    "maybe_inject_async",
    "register_faults",
    "reset_fault_counts",
    "with_faults",
]


@contextmanager
def with_faults(*specs: FaultSpec) -> Iterator[None]:
    """Install fault specs for the duration of a test block."""
    with active_faults(*specs):
        reset_fault_counts()
        try:
            yield
        finally:
            reset_fault_counts()
