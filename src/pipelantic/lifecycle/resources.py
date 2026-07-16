"""Resource injection markers and scoped resource cache."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Inject:
    """Annotation marker for hierarchical resource injection."""

    name: str
    scope: str = "run"  # runtime | run | execution_region | step | attempt


@dataclass
class _CachedResource:
    value: Any
    cleanup: Callable[[], Any] | None = None
    scope: str = "run"
    scope_key: str = ""


@dataclass
class ResourceManager:
    """Scoped resource acquisition with yield cleanup exactly once."""

    providers: dict[str, Callable[..., Any]] = field(default_factory=dict)
    _cache: dict[tuple[str, str], _CachedResource] = field(default_factory=dict)

    def override(self, name: str, provider: Callable[..., Any]) -> None:
        self.providers[name] = provider

    async def get(
        self,
        name: str,
        *,
        scope: str = "run",
        scope_key: str = "",
        context: dict[str, Any] | None = None,
    ) -> Any:
        from pipelantic.runtime.invoke import maybe_await

        cache_key = (name, f"{scope}:{scope_key}")
        if cache_key in self._cache:
            return self._cache[cache_key].value
        provider = self.providers.get(name)
        if provider is None:
            raise KeyError(f"No resource provider registered for {name!r}")
        value = await maybe_await(provider, context or {})
        cleanup: Callable[[], Any] | None = None
        if hasattr(value, "__aenter__") and hasattr(value, "__aexit__"):
            cm: AbstractAsyncContextManager[Any] = value
            value = await cm.__aenter__()

            async def _cleanup() -> None:
                await cm.__aexit__(None, None, None)

            cleanup = _cleanup
        self._cache[cache_key] = _CachedResource(
            value=value, cleanup=cleanup, scope=scope, scope_key=scope_key
        )
        return value

    async def cleanup_scope(self, scope: str, scope_key: str = "") -> None:
        from pipelantic.runtime.invoke import maybe_await

        keys = [
            key
            for key, entry in self._cache.items()
            if entry.scope == scope and entry.scope_key == scope_key
        ]
        for key in keys:
            entry = self._cache.pop(key)
            if entry.cleanup is not None:
                await maybe_await(entry.cleanup)

    @asynccontextmanager
    async def scope(self, scope: str, scope_key: str = "") -> AsyncIterator[None]:
        try:
            yield
        finally:
            await self.cleanup_scope(scope, scope_key)
