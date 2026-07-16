"""Lifecycle events and breakpoint bus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    """Immutable lifecycle event (secret-free)."""

    kind: str
    run_id: str
    pipeline_id: str
    at: datetime = field(default_factory=lambda: datetime.now(UTC))
    step_name: str | None = None
    attempt: int | None = None
    status: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "at": self.at.isoformat(),
            "step_name": self.step_name,
            "attempt": self.attempt,
            "status": self.status,
            "message": self.message,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    """Immutable security audit event (never includes secret values)."""

    kind: str
    run_id: str
    provider: str
    secret_identity: str
    outcome: str
    at: datetime = field(default_factory=lambda: datetime.now(UTC))
    step_name: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "run_id": self.run_id,
            "provider": self.provider,
            "secret_identity": self.secret_identity,
            "outcome": self.outcome,
            "at": self.at.isoformat(),
            "step_name": self.step_name,
            "message": self.message,
        }


EventListener = Callable[[LifecycleEvent | SecurityEvent], None]


@dataclass
class EventBus:
    """Simple in-process event / breakpoint bus."""

    _listeners: list[EventListener] = field(default_factory=list)
    _events: list[LifecycleEvent | SecurityEvent] = field(default_factory=list)

    def subscribe(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    def emit(self, event: LifecycleEvent | SecurityEvent) -> None:
        self._events.append(event)
        for listener in list(self._listeners):
            listener(event)

    @property
    def events(self) -> tuple[LifecycleEvent | SecurityEvent, ...]:
        return tuple(self._events)
