# pyright: reportUnknownVariableType=false
"""IDE/debug breakpoint helpers over the lifecycle EventBus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from etlantic.runtime.events import EventBus, LifecycleEvent, SecurityEvent

BreakpointListener = Callable[[LifecycleEvent | SecurityEvent], None]

BREAKPOINT_KINDS = frozenset(
    {
        "validation",
        "step_started",
        "step_completed",
        "step_failed",
        "publication",
        "run_started",
        "run_completed",
        "run_failed",
    }
)


@dataclass
class BreakpointBus:
    """Thin wrapper that filters EventBus emissions to breakpoint kinds."""

    events: EventBus
    _listeners: list[BreakpointListener] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.events.subscribe(self._dispatch)

    def on(self, kind: str, listener: BreakpointListener) -> None:
        def _filtered(event: LifecycleEvent | SecurityEvent) -> None:
            if getattr(event, "kind", None) == kind:
                listener(event)

        self._listeners.append(_filtered)
        self.events.subscribe(_filtered)

    def on_any(self, listener: BreakpointListener) -> None:
        def _filtered(event: LifecycleEvent | SecurityEvent) -> None:
            if getattr(event, "kind", None) in BREAKPOINT_KINDS:
                listener(event)

        self._listeners.append(_filtered)
        self.events.subscribe(_filtered)

    def _dispatch(self, event: LifecycleEvent | SecurityEvent) -> None:
        # Events already fan out via EventBus.subscribe; this exists for hooks.
        return None
