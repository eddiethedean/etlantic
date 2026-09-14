"""Per-invocation ownership of admitted adaptive native work."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import anyio
from anyio.to_thread import run_sync


@dataclass(frozen=True, slots=True)
class NativeExecution:
    """Drain a cancelled worker, or retain its unresolved owner in the run.

    This scope is supplied only by the adaptive host. The worker closure keeps
    its compiler and input buffers alive until it finishes; cancellation never
    returns its late result to the caller for artifact registration.
    """

    unit_id: str
    member: str
    attempt: int
    abandon_after_seconds: float | None
    obligations: list[dict[str, Any]]

    async def run(self, operation: Callable[[], Any]) -> Any:
        completed = threading.Event()
        gate = threading.Lock()
        started = False
        cancelled = False

        def run_operation() -> Any:
            nonlocal started
            with gate:
                if cancelled:
                    # Cancellation may win while waiting for worker capacity.
                    # A queued invocation must never start effects afterward.
                    return None
                started = True
            try:
                return operation()
            finally:
                completed.set()

        try:
            return await run_sync(run_operation, abandon_on_cancel=True)
        except anyio.get_cancelled_exc_class():
            with gate:
                cancelled = True
                if not started:
                    completed.set()
            # Handle cancellation at the owned native await, before either a
            # member deadline or the outer run cancellation constructs a report.
            # Without an abandonment bound, cooperative native work drains fully.
            with anyio.move_on_after(self.abandon_after_seconds, shield=True):
                while not completed.is_set():
                    await anyio.sleep(0.01)
            if not completed.is_set():
                self.obligations.append(
                    {
                        "unit_id": self.unit_id,
                        "member": self.member,
                        "attempt": self.attempt,
                        "owner": "etlantic.runtime.native-worker",
                        "operation": "native_execution",
                        "code": "PMADP523",
                    }
                )
            raise
