"""Deterministic failure injection for resilience testing (0.23).

Active only when ``ETLANTIC_FAULT_INJECTION=1`` or an in-process registry has
active specs. Production profiles ignore injection unless the env flag is set.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FaultBoundary(StrEnum):
    """Runtime boundaries where faults may be injected."""

    EXTRACT = "extract"
    CONVERT = "convert"
    TRANSFORM = "transform"
    VALIDATE = "validate"
    MATERIALIZE = "materialize"
    LOAD = "load"
    REPORT_PERSIST = "report_persist"
    CLEANUP = "cleanup"
    CALLBACK = "callback"
    OUTBOUND = "outbound"


class FaultTrigger(StrEnum):
    """When a fault spec fires."""

    ON_CALL = "on_call"
    AFTER_N_CALLS = "after_n_calls"
    ON_STEP = "on_step"


@dataclass(frozen=True, slots=True)
class FaultSpec:
    """One injectable fault at a boundary."""

    boundary: FaultBoundary | str
    error: type[BaseException] = RuntimeError
    message: str = "injected fault"
    trigger: FaultTrigger = FaultTrigger.ON_CALL
    after_n: int = 0
    step_name: str | None = None
    delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "boundary", FaultBoundary(str(self.boundary)))


@dataclass
class _FaultState:
    specs: tuple[FaultSpec, ...] = ()
    call_counts: dict[tuple[str, str | None], int] = field(default_factory=dict)


_active: ContextVar[_FaultState | None] = ContextVar("etlantic_fault_state", default=None)


def fault_injection_enabled() -> bool:
    """Return True when fault injection may fire."""
    if os.environ.get("ETLANTIC_FAULT_INJECTION", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return True
    state = _active.get()
    return state is not None and bool(state.specs)


def _current_state() -> _FaultState | None:
    if not fault_injection_enabled():
        return None
    return _active.get()


def register_faults(*specs: FaultSpec) -> None:
    """Replace active fault specs for the current context."""
    _active.set(_FaultState(specs=specs))


def clear_faults() -> None:
    """Clear active fault specs."""
    _active.set(None)


@contextmanager
def active_faults(*specs: FaultSpec) -> Iterator[None]:
    """Context manager installing fault specs for the current task/thread."""
    token = _active.set(_FaultState(specs=specs))
    try:
        yield
    finally:
        _active.reset(token)


def maybe_inject(
    boundary: FaultBoundary | str,
    *,
    step_name: str | None = None,
) -> None:
    """Raise or delay when a matching fault spec is active."""
    state = _current_state()
    if state is None or not state.specs:
        return
    bkey = str(boundary)
    for spec in state.specs:
        if spec.boundary.value != bkey:
            continue
        if spec.trigger == FaultTrigger.ON_STEP and spec.step_name != step_name:
            continue
        key = (bkey, step_name)
        count = state.call_counts.get(key, 0) + 1
        state.call_counts[key] = count
        if spec.trigger == FaultTrigger.AFTER_N_CALLS and count <= spec.after_n:
            continue
        if spec.delay_seconds > 0:
            time.sleep(spec.delay_seconds)
        raise spec.error(spec.message)


def reset_fault_counts() -> None:
    """Reset per-boundary call counters (for test isolation)."""
    state = _active.get()
    if state is not None:
        state.call_counts.clear()
