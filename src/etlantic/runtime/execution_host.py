"""Execution-host worker loop. Must not import FastAPI."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.schedule_diagnostics import fed_diagnostic


class UnknownCommitError(Exception):
    """Commit outcome cannot be classified; never auto-retry."""


class ExecutionHost:
    """Polls CP3 outbox, leases work, and runs a caller-supplied runner."""

    def __init__(
        self,
        durable: DurableWorkStore,
        *,
        owner_id: str = "worker-1",
        ttl_seconds: int = 30,
        runner: Callable[..., Any] | None = None,
        cancel_check: Callable[[ControlPlaneContext, str], bool] | None = None,
    ) -> None:
        self.durable = durable
        self.owner_id = owner_id
        self.ttl_seconds = ttl_seconds
        self.runner = runner or _default_runner
        self.cancel_check = cancel_check
        self.draining = False

    def drain(self) -> None:
        self.draining = True

    def tick(self, ctx: ControlPlaneContext, *, limit: int = 20) -> int:
        if self.draining:
            return 0
        processed = 0
        for item in self.durable.pending_outbox(ctx, limit=limit):
            try:
                lease = self.durable.acquire_lease(
                    ctx,
                    item.submission_id,
                    owner_id=self.owner_id,
                    ttl_seconds=self.ttl_seconds,
                )
            except ControlPlaneError:
                continue
            self.durable.mark_published(ctx, item.outbox_id)
            attempt = self.durable.start_attempt(
                ctx,
                item.submission_id,
                owner_id=self.owner_id,
                fencing_token=lease.fencing_token,
            )
            if self.cancel_check is not None and self.cancel_check(
                ctx, item.submission_id
            ):
                self.durable.finish_attempt(
                    ctx,
                    attempt.attempt_id,
                    owner_id=self.owner_id,
                    fencing_token=lease.fencing_token,
                    status="cancelled",
                )
                processed += 1
                continue
            try:
                self.runner(
                    ctx,
                    submission_id=item.submission_id,
                    attempt_id=attempt.attempt_id,
                    fencing_token=lease.fencing_token,
                )
            except UnknownCommitError:
                self.durable.finish_attempt(
                    ctx,
                    attempt.attempt_id,
                    owner_id=self.owner_id,
                    fencing_token=lease.fencing_token,
                    status="lost",
                )
                processed += 1
                continue
            except Exception:
                self.durable.finish_attempt(
                    ctx,
                    attempt.attempt_id,
                    owner_id=self.owner_id,
                    fencing_token=lease.fencing_token,
                    status="failed",
                )
                processed += 1
                continue
            self.durable.finish_attempt(
                ctx,
                attempt.attempt_id,
                owner_id=self.owner_id,
                fencing_token=lease.fencing_token,
                status="completed",
            )
            processed += 1
        return processed


def _default_runner(**_: Any) -> None:
    return None


def unknown_commit_message() -> str:
    return fed_diagnostic(
        "unknown_commit_retry",
        "Unknown commits must not auto-retry; mark the attempt lost.",
    ).code


__all__ = ["ExecutionHost", "UnknownCommitError", "unknown_commit_message"]
