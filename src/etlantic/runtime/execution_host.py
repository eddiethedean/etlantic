"""Execution-host worker loop. Must not import FastAPI."""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from threading import Event, Thread
from typing import Any, cast

from etlantic.control_plane.durable_models import EffectRecord
from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.schedule_diagnostics import fed_diagnostic
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.managed_errors import ExecutionRejected, UnknownCommitError
from etlantic.runtime.state import RunStatus


class ExecutionHost:
    """Poll CP3 work and run its accepted plan through ETLantic runtime."""

    def __init__(
        self,
        durable: DurableWorkStore,
        *,
        owner_id: str = "worker-1",
        ttl_seconds: int = 30,
        runner: Callable[..., Any] | None = None,
        cancel_check: Callable[[ControlPlaneContext, str], bool] | None = None,
    ) -> None:
        if runner is None:
            from etlantic.runtime.managed_execution import ManagedExecutionAdapter

            runner = ManagedExecutionAdapter()
        self.durable = durable
        self.owner_id = owner_id
        self.ttl_seconds = ttl_seconds
        self.runner = runner
        self.cancel_check = cancel_check
        self.draining = False

    def _start_lease_monitor(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        fencing_token: int,
    ) -> tuple[Event, Event, Event, Thread]:
        """Renew a running lease and signal cancellation or fencing loss."""
        stop = Event()
        cancel = Event()
        lease_lost = Event()
        interval = max(0.01, min(1.0, self.ttl_seconds / 3))

        def watch() -> None:
            while not stop.wait(interval):
                try:
                    submission = self.durable.get_submission(ctx, submission_id)
                    if submission.status == "cancel_requested":
                        cancel.set()
                        return
                    if self.cancel_check is not None and self.cancel_check(
                        ctx, submission_id
                    ):
                        with suppress(ControlPlaneError):
                            self.durable.cancel_submission(ctx, submission_id)
                        cancel.set()
                        return
                    self.durable.heartbeat(
                        ctx,
                        submission_id,
                        owner_id=self.owner_id,
                        fencing_token=fencing_token,
                        ttl_seconds=self.ttl_seconds,
                    )
                except Exception:
                    # A worker that cannot prove it still owns the lease must
                    # stop mutating output. The outbox remains recoverable.
                    lease_lost.set()
                    cancel.set()
                    return

        thread = Thread(
            target=watch,
            name=f"etlantic-lease-{submission_id[:12]}",
            daemon=True,
        )
        thread.start()
        return stop, cancel, lease_lost, thread

    def _invoke_runner(
        self,
        ctx: ControlPlaneContext,
        *,
        submission: Any,
        submission_id: str,
        attempt_id: str,
        fencing_token: int,
        recovered_attempt: bool,
        cancel_event: Event,
    ) -> Any:
        runner = self.runner
        if runner is None:
            raise RuntimeError("Execution runner is unavailable")
        kwargs: dict[str, Any] = {
            "submission": submission,
            "submission_id": submission_id,
            "attempt_id": attempt_id,
            "fencing_token": fencing_token,
            "recovered_attempt": recovered_attempt,
        }
        try:
            parameters = inspect.signature(runner).parameters.values()
            accepts_cancel = any(
                parameter.name == "cancel_event"
                or parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in parameters
            )
        except (TypeError, ValueError):
            accepts_cancel = False
        if accepts_cancel:
            kwargs["cancel_event"] = cancel_event
        return runner(ctx, **kwargs)

    def drain(self) -> None:
        self.draining = True

    def _release_lease(
        self, ctx: ControlPlaneContext, submission_id: str, fencing_token: int
    ) -> None:
        # Cancellation deliberately expires the lease to wake its owner;
        # terminal acknowledgement remains valid for that matching token.
        with suppress(ControlPlaneError):
            self.durable.release_lease(
                ctx,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=fencing_token,
            )

    def tick(self, ctx: ControlPlaneContext, *, limit: int = 20) -> int:
        if self.draining:
            return 0
        self.durable.reconcile_cancelled_submissions(ctx, limit=limit)
        self.durable.reconcile_terminal_outbox(ctx, limit=limit)
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
            try:
                submission = self.durable.get_submission(ctx, item.submission_id)
                previous_attempts = self.durable.list_attempts(ctx, item.submission_id)
            except ControlPlaneError:
                self._release_lease(ctx, item.submission_id, lease.fencing_token)
                raise
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
                self.durable.mark_published(ctx, item.outbox_id)
                self._release_lease(ctx, item.submission_id, lease.fencing_token)
                processed += 1
                continue
            stop_monitor, cancel_event, lease_lost, monitor_thread = (
                self._start_lease_monitor(ctx, item.submission_id, lease.fencing_token)
            )
            outcome: Any = None
            runner_error: Exception | None = None
            try:
                outcome = self._invoke_runner(
                    ctx,
                    submission=submission,
                    submission_id=item.submission_id,
                    attempt_id=attempt.attempt_id,
                    fencing_token=lease.fencing_token,
                    recovered_attempt=bool(previous_attempts),
                    cancel_event=cancel_event,
                )
            except Exception as exc:
                runner_error = exc
            finally:
                stop_monitor.set()
                monitor_thread.join(timeout=max(1.0, self.ttl_seconds / 2))

            if lease_lost.is_set():
                # The new lease holder owns recovery. Leave its outbox item
                # unpublished and never let this stale worker finalize it.
                processed += 1
                continue

            if isinstance(runner_error, ExecutionRejected):
                self.durable.finish_attempt(
                    ctx,
                    attempt.attempt_id,
                    owner_id=self.owner_id,
                    fencing_token=lease.fencing_token,
                    status="failed",
                )
                self.durable.mark_published(ctx, item.outbox_id)
                self._release_lease(ctx, item.submission_id, lease.fencing_token)
                processed += 1
                continue
            if runner_error is not None:
                self._record_unknown_effect(ctx, item.submission_id)
                self.durable.finish_attempt(
                    ctx,
                    attempt.attempt_id,
                    owner_id=self.owner_id,
                    fencing_token=lease.fencing_token,
                    status="lost",
                )
                self.durable.mark_published(ctx, item.outbox_id)
                self._release_lease(ctx, item.submission_id, lease.fencing_token)
                processed += 1
                continue

            if not isinstance(outcome, PipelineRunReport):
                self._record_unknown_effect(ctx, item.submission_id)
                self.durable.finish_attempt(
                    ctx,
                    attempt.attempt_id,
                    owner_id=self.owner_id,
                    fencing_token=lease.fencing_token,
                    status="lost",
                )
                self.durable.mark_published(ctx, item.outbox_id)
                self._release_lease(ctx, item.submission_id, lease.fencing_token)
                processed += 1
                continue

            if (
                cancel_event.is_set() and outcome.status is not RunStatus.CANCELLED
            ) or outcome.plan_fingerprint != submission.plan_fingerprint:
                self._record_unknown_effect(ctx, item.submission_id)
                terminal_status = "lost"
            elif outcome.status is RunStatus.SUCCEEDED:
                self._record_report_effect(ctx, item.submission_id, outcome)
                terminal_status = "completed"
            elif outcome.status is RunStatus.CANCELLED:
                self._record_unknown_effect(ctx, item.submission_id)
                terminal_status = "cancelled"
            else:
                self._record_unknown_effect(ctx, item.submission_id)
                terminal_status = "lost"
            self.durable.finish_attempt(
                ctx,
                attempt.attempt_id,
                owner_id=self.owner_id,
                fencing_token=lease.fencing_token,
                status=terminal_status,
            )
            self.durable.mark_published(ctx, item.outbox_id)
            self._release_lease(ctx, item.submission_id, lease.fencing_token)
            processed += 1
        return processed

    def _record_unknown_effect(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> None:
        self.durable.record_effect(
            ctx,
            EffectRecord(
                effect_id=f"{submission_id}:execution",
                submission_id=submission_id,
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                status="unknown",
                recorded_at=datetime.now(UTC).isoformat(),
                authoritative=True,
            ),
        )

    def _record_report_effect(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        report: PipelineRunReport,
    ) -> None:
        evidence = hashlib.sha256(
            report.to_json(indent=None).encode("utf-8")
        ).hexdigest()
        execution_raw: object = report.metadata.get("etlantic.control_plane.execution")
        execution: Mapping[str, object] = {}
        if isinstance(execution_raw, Mapping):
            execution = cast(Mapping[str, object], execution_raw)
        no_write = report.intent.value == "validate" or (
            execution.get("no_write") is True
        )
        self.durable.record_effect(
            ctx,
            EffectRecord(
                effect_id=f"{submission_id}:execution",
                submission_id=submission_id,
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                status="none" if no_write else "committed",
                recorded_at=report.ended_at.isoformat()
                if report.ended_at is not None
                else report.started_at.isoformat(),
                idempotency_evidence=None if no_write else evidence,
                publication_evidence=None if no_write else evidence,
                authoritative=True,
                metadata={
                    "run_id": report.run_id,
                    "plan_fingerprint": report.plan_fingerprint,
                },
            ),
        )


def unknown_commit_message() -> str:
    return fed_diagnostic(
        "unknown_commit_retry",
        "Unknown commits must not auto-retry; mark the attempt lost.",
    ).code


__all__ = ["ExecutionHost", "UnknownCommitError", "unknown_commit_message"]
