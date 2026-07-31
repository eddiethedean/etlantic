"""Sync-to-async bridge via AnyIO worker threads with cancellation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import anyio

T = TypeVar("T")


async def run_sync_in_worker(
    func: Callable[..., T],
    /,
    *args: Any,
    abandon_on_cancel: bool = True,
    deadline_seconds: float | None = None,
    **kwargs: Any,
) -> T:
    """Run a sync callable in an AnyIO worker thread.

    When *abandon_on_cancel* is True (default), cancelling the waiting task
    abandons the worker so the host task is not blocked. Optional
    *deadline_seconds* wraps the call in ``anyio.fail_after``.
    """

    def _call() -> T:
        return func(*args, **kwargs)

    async def _run() -> T:
        return await anyio.to_thread.run_sync(
            _call,
            abandon_on_cancel=abandon_on_cancel,
        )

    if deadline_seconds is None:
        return await _run()
    with anyio.fail_after(deadline_seconds):
        return await _run()


__all__ = ["run_sync_in_worker"]
