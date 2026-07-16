"""Sync/async callable invocation helpers."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

import anyio


async def maybe_await(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Invoke ``func``, awaiting if it returns an awaitable / is async."""
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    result = await anyio.to_thread.run_sync(lambda: func(*args, **kwargs))
    if inspect.isawaitable(result):
        return await result
    return result


def is_async_callable(func: Callable[..., Any]) -> bool:
    return inspect.iscoroutinefunction(func)
