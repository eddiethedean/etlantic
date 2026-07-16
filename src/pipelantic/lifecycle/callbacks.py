"""Outcome callbacks and failure actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FailureAction(StrEnum):
    """How the runtime should proceed after a callback."""

    CONTINUE = "continue"
    RETRY = "retry"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class StepFailureContext:
    """Context passed to step-failure callbacks."""

    run_id: str
    pipeline_id: str
    step_name: str
    attempt: int
    error: BaseException
    stage: str | None = None


@dataclass
class CallbackRegistry:
    """Lifecycle outcome callbacks."""

    _handlers: dict[str, list[Callable[..., Any]]] = field(default_factory=dict)

    def on(self, event: str, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._handlers.setdefault(event, []).append(handler)
        return handler

    def on_complete(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        return self.on("run_completed", handler)

    def on_failure(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        return self.on("run_failed", handler)

    def on_step_failed(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        return self.on("step_failed", handler)

    async def emit(self, event: str, context: Any) -> list[Any]:
        from pipelantic.runtime.invoke import maybe_await

        results: list[Any] = []
        for handler in self._handlers.get(event, ()):
            results.append(await maybe_await(handler, context))
        return results
