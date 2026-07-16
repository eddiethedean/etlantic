"""Middleware stacks for run / step / provider scopes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")

Middleware = Callable[[Any, Callable[[], Awaitable[T]]], Awaitable[T]]


@dataclass
class MiddlewareStack:
    """Deterministic ordered middleware stack."""

    _items: list[tuple[str, Middleware[Any]]] = field(default_factory=list)

    def add(self, middleware: Middleware[Any], *, name: str | None = None) -> None:
        label = name or getattr(middleware, "__name__", f"mw-{len(self._items)}")
        self._items.append((label, middleware))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self._items)

    async def run(self, context: Any, terminal: Callable[[], Awaitable[T]]) -> T:
        async def build(index: int) -> T:
            if index >= len(self._items):
                return await terminal()
            _name, middleware = self._items[index]

            async def call_next() -> T:
                return await build(index + 1)

            return await middleware(context, call_next)

        return await build(0)
