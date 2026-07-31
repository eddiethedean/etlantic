"""Resource injection markers and scoped resource cache."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, TypeVar

import anyio

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


def _provider_takes_context(provider: Callable[..., Any]) -> bool:
    """Return True when ``provider`` accepts a positional/context argument."""
    try:
        sig = inspect.signature(provider)
    except (TypeError, ValueError):
        return True
    if any(
        p.kind is inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values()
    ):
        return True
    if "context" in sig.parameters:
        return True
    positional = [
        p
        for p in sig.parameters.values()
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    return len(positional) >= 1


@dataclass
class ResourceManager:
    """Scoped resource acquisition with yield cleanup exactly once."""

    providers: dict[str, Callable[..., Any]] = field(default_factory=dict)
    _cache: dict[tuple[str, str], _CachedResource] = field(default_factory=dict)
    _lock: anyio.Lock = field(default_factory=anyio.Lock)

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
        from etlantic.runtime.invoke import maybe_await

        cache_key = (name, f"{scope}:{scope_key}")
        async with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key].value
            provider = self.providers.get(name)
            if provider is None:
                raise KeyError(f"No resource provider registered for {name!r}")
            ctx = context or {}
            if _provider_takes_context(provider):
                value = await maybe_await(provider, ctx)
            else:
                value = await maybe_await(provider)
            cleanup: Callable[[], Any] | None = None
            if hasattr(value, "__aenter__") and hasattr(value, "__aexit__"):
                cm: AbstractAsyncContextManager[Any] = value
                value = await cm.__aenter__()

                async def _cleanup_async() -> None:
                    await cm.__aexit__(None, None, None)

                cleanup = _cleanup_async
            elif hasattr(value, "__enter__") and hasattr(value, "__exit__"):
                sync_cm = value
                value = await anyio.to_thread.run_sync(sync_cm.__enter__)

                def _cleanup_sync() -> None:
                    sync_cm.__exit__(None, None, None)

                cleanup = _cleanup_sync
            self._cache[cache_key] = _CachedResource(
                value=value, cleanup=cleanup, scope=scope, scope_key=scope_key
            )
            return value

    async def cleanup_scope(self, scope: str, scope_key: str = "") -> None:
        from etlantic.runtime.invoke import maybe_await

        async with self._lock:
            keys = [
                key
                for key, entry in self._cache.items()
                if entry.scope == scope and entry.scope_key == scope_key
            ]
            entries = [self._cache.pop(key) for key in keys]
        errors: list[BaseException] = []
        for entry in entries:
            if entry.cleanup is None:
                continue
            try:
                await maybe_await(entry.cleanup)
            except BaseException as exc:
                # Attempt every cleanup; one failure must not leak the rest.
                errors.append(exc)
        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise ExceptionGroup("resource cleanup failures", errors)

    @asynccontextmanager
    async def scope(self, scope: str, scope_key: str = "") -> AsyncIterator[None]:
        try:
            yield
        finally:
            await self.cleanup_scope(scope, scope_key)
