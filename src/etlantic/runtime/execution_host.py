"""Execution-host worker loop. Must not import FastAPI."""

from __future__ import annotations

import hashlib
import inspect
import logging
from collections import deque
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from threading import Event, Thread
from typing import Any, cast

from etlantic.control_plane.durable_models import (
    EffectRecord,
    ExecutionScopePage,
    ResultPublicationRecord,
)
from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.schedule_diagnostics import fed_diagnostic
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.managed_errors import ExecutionRejected, UnknownCommitError
from etlantic.runtime.state import RunStatus
from etlantic.secrets.provider import SecretAliasAuthorizer

_LOG = logging.getLogger(__name__)
_RETENTION_SCOPE_PAGE_SIZE = 20
_RETENTION_RETRY_CAPACITY = 100
_RETENTION_RETRY_BUDGET = 10


def _execution_scope_key(
    ctx: ControlPlaneContext,
) -> tuple[str | tuple[bool, str], ...]:
    """Identify the persisted authority dimensions used by managed providers."""
    return (
        ctx.tenant.tenant_id,
        ctx.workspace.workspace_id,
        (ctx.principal.issuer is not None, ctx.principal.issuer or ""),
        ctx.principal.kind,
        ctx.principal.subject,
        ctx.environment.name,
        ctx.security_domain.domain_id,
        (ctx.resource_owner_id is not None, ctx.resource_owner_id or ""),
    )


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
        secret_alias_authorizer: SecretAliasAuthorizer | None = None,
    ) -> None:
        if type(ttl_seconds) is not int or ttl_seconds < 1:
            raise ValueError("ttl_seconds must be a positive integer")
        if runner is None:
            from etlantic.runtime.managed_execution import ManagedExecutionAdapter

            runner = ManagedExecutionAdapter(
                secret_alias_authorizer=secret_alias_authorizer
            )
        self.durable = durable
        self.owner_id = owner_id
        self.ttl_seconds = ttl_seconds
        self.runner = runner
        self.cancel_check = cancel_check
        self.draining = False
        self._retention_scope_workspace: tuple[str, str] | None = None
        self._retention_scope_cursor: str | None = None
        self._retention_retry_keys: deque[object] = deque()
        self._retention_retry_contexts: dict[object, ControlPlaneContext] = {}
        self._retention_single_slot_turn = False

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
        if _accepts_keyword(runner, "result_publisher"):
            kwargs["result_publisher"] = self._result_publisher(
                ctx,
                submission_id=submission_id,
                attempt_id=attempt_id,
                owner_id=self.owner_id,
                fencing_token=fencing_token,
            )
        if _accepts_keyword(runner, "result_reader"):
            kwargs["result_reader"] = lambda: (
                self.durable.get_latest_result_publication(ctx, submission_id)
            )
        return runner(ctx, **kwargs)

    def _result_publisher(
        self,
        ctx: ControlPlaneContext,
        *,
        submission_id: str,
        attempt_id: str,
        owner_id: str,
        fencing_token: int,
    ) -> Callable[[PipelineRunReport], ResultPublicationRecord]:
        def publish(report: PipelineRunReport) -> ResultPublicationRecord:
            report_json = report.to_json(indent=None)
            return self.durable.record_result_publication(
                ctx,
                ResultPublicationRecord(
                    submission_id=submission_id,
                    attempt_id=attempt_id,
                    run_id=report.run_id,
                    tenant_id=ctx.tenant.tenant_id,
                    workspace_id=ctx.workspace.workspace_id,
                    report_json=report_json,
                    report_sha256=hashlib.sha256(
                        report_json.encode("utf-8")
                    ).hexdigest(),
                    created_at=datetime.now(UTC).isoformat(),
                ),
                owner_id=owner_id,
                fencing_token=fencing_token,
            )

        return publish

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
        cleanup_artifacts = getattr(self.runner, "cleanup_expired_run_artifacts", None)
        retention_enabled = getattr(
            self.runner, "run_artifact_retention_enabled", True
        )
        if callable(cleanup_artifacts) and retention_enabled is not False:
            workspace = (ctx.tenant.tenant_id, ctx.workspace.workspace_id)
            if workspace != self._retention_scope_workspace:
                self._retention_scope_workspace = workspace
                self._retention_scope_cursor = None
            attempted_keys = self._retry_retention_scopes(
                cleanup_artifacts, budget=_RETENTION_RETRY_BUDGET
            )
            pending_count = len(self._retention_retry_contexts)
            available_slots = _RETENTION_RETRY_CAPACITY - pending_count
            cleanup_budget = _RETENTION_SCOPE_PAGE_SIZE - len(attempted_keys)
            new_scope_budget = min(cleanup_budget, available_slots)
            if new_scope_budget > 0:
                # Keep one slot for the worker scope when possible. With only
                # one slot, alternate between the worker and accepted scopes
                # so neither can starve while the retry queue is nearly full.
                include_worker_scope = new_scope_budget > 1
                if new_scope_budget == 1:
                    include_worker_scope = self._retention_single_slot_turn
                    self._retention_single_slot_turn = not self._retention_single_slot_turn
                page_limit = min(
                    _RETENTION_SCOPE_PAGE_SIZE,
                    new_scope_budget - int(include_worker_scope),
                )
                cleanup_contexts: dict[object, ControlPlaneContext] = {}
                if page_limit > 0:
                    try:
                        page: ExecutionScopePage = self.durable.list_execution_scopes(
                            ctx,
                            after_submission_id=self._retention_scope_cursor,
                            limit=page_limit,
                        )
                        self._retention_scope_cursor = page.next_cursor
                        for accepted_ctx in page.scopes:
                            if (
                                accepted_ctx.tenant.tenant_id,
                                accepted_ctx.workspace.workspace_id,
                            ) != (
                                ctx.tenant.tenant_id,
                                ctx.workspace.workspace_id,
                            ):
                                _LOG.warning(
                                    "Skipping accepted execution scope outside the worker workspace"
                                )
                                continue
                            key = self._retention_scope_key(accepted_ctx)
                            if key not in attempted_keys:
                                cleanup_contexts.setdefault(key, accepted_ctx)
                    except Exception:
                        _LOG.warning(
                            "Could not list accepted scopes for artifact retention"
                        )
                if include_worker_scope:
                    worker_key = self._retention_scope_key(ctx)
                    if worker_key not in attempted_keys:
                        cleanup_contexts.setdefault(worker_key, ctx)
                for key, cleanup_ctx in cleanup_contexts.items():
                    if self._cleanup_retention_scope(cleanup_artifacts, cleanup_ctx):
                        self._queue_retention_retry(key, cleanup_ctx)
        self.durable.reconcile_cancelled_submissions(ctx, limit=limit)
        self.durable.reconcile_terminal_outbox(ctx, limit=limit)
        self._reconcile_result_publications(ctx, limit=limit)
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
                self._record_unknown_effect(
                    ctx,
                    item.submission_id,
                    attempt_id=attempt.attempt_id,
                    fencing_token=lease.fencing_token,
                )
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
                self._record_unknown_effect(
                    ctx,
                    item.submission_id,
                    attempt_id=attempt.attempt_id,
                    fencing_token=lease.fencing_token,
                )
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
                self._record_unknown_effect(
                    ctx,
                    item.submission_id,
                    attempt_id=attempt.attempt_id,
                    fencing_token=lease.fencing_token,
                )
                terminal_status = "lost"
            elif outcome.status is RunStatus.SUCCEEDED:
                self._record_report_effect(
                    ctx,
                    item.submission_id,
                    outcome,
                    attempt_id=attempt.attempt_id,
                    fencing_token=lease.fencing_token,
                )
                terminal_status = "completed"
            elif outcome.status is RunStatus.CANCELLED:
                self._record_unknown_effect(
                    ctx,
                    item.submission_id,
                    attempt_id=attempt.attempt_id,
                    fencing_token=lease.fencing_token,
                )
                terminal_status = "cancelled"
            else:
                self._record_unknown_effect(
                    ctx,
                    item.submission_id,
                    attempt_id=attempt.attempt_id,
                    fencing_token=lease.fencing_token,
                )
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

    def _retry_retention_scopes(
        self, cleanup_artifacts: Callable[[ControlPlaneContext], Any], *, budget: int
    ) -> set[object]:
        """Retry a bounded number of scopes, rotating unresolved work fairly."""
        attempted: set[object] = set()
        retry_count = min(budget, len(self._retention_retry_keys))
        for _ in range(retry_count):
            key = self._retention_retry_keys.popleft()
            cleanup_ctx = self._retention_retry_contexts.pop(key)
            attempted.add(key)
            if self._cleanup_retention_scope(cleanup_artifacts, cleanup_ctx):
                self._queue_retention_retry(key, cleanup_ctx)
        return attempted

    @staticmethod
    def _cleanup_retention_scope(
        cleanup_artifacts: Callable[[ControlPlaneContext], Any],
        ctx: ControlPlaneContext,
    ) -> bool:
        """Return whether this store still needs a later cleanup pass."""
        try:
            outcome = cleanup_artifacts(ctx)
        except Exception:
            # Retention has its own durable state and must not block ETL
            # admission when a report store or artifact filesystem is down.
            _LOG.warning(
                "Run artifact retention pass failed; execution polling continues"
            )
            return True
        return getattr(outcome, "remaining_candidates", False) is True

    def _queue_retention_retry(
        self, key: object, ctx: ControlPlaneContext
    ) -> None:
        """Remember unresolved cleanup while keeping retry state bounded."""
        if key in self._retention_retry_contexts:
            return
        if len(self._retention_retry_contexts) >= _RETENTION_RETRY_CAPACITY:
            # Scope discovery reserves queue slots before advancing its cursor.
            # This guard keeps a custom runner from growing state without bound.
            _LOG.warning("Artifact-retention retry queue is full")
            return
        self._retention_retry_contexts[key] = ctx
        self._retention_retry_keys.append(key)

    def _retention_scope_key(self, ctx: ControlPlaneContext) -> object:
        key_builder = getattr(self.runner, "artifact_retention_scope_key", None)
        if callable(key_builder):
            try:
                key = key_builder(ctx)
                hash(key)
                return key
            except Exception:
                _LOG.warning(
                    "Could not determine artifact retention storage scope; "
                    "using complete accepted authority"
                )
        return _execution_scope_key(ctx)

    def _reconcile_result_publications(
        self, ctx: ControlPlaneContext, *, limit: int
    ) -> None:
        publish = getattr(self.runner, "publish_result_publication", None)
        if not callable(publish):
            return
        from etlantic.runtime.managed_execution import accepted_execution_context

        try:
            records = self.durable.pending_result_publications(ctx, limit=limit)
        except Exception:
            _LOG.warning("Could not inspect pending run-result publications")
            return
        for record in records:
            try:
                submission = self.durable.get_submission(ctx, record.submission_id)
                accepted_ctx = accepted_execution_context(ctx, submission)
                publish(accepted_ctx, record)
                self.durable.mark_result_publication_published(
                    ctx,
                    record.submission_id,
                    record.attempt_id,
                    report_sha256=record.report_sha256,
                )
            except Exception:
                _LOG.warning(
                    "Could not publish a durable run result; it remains recoverable"
                )

    def _record_unknown_effect(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        attempt_id: str,
        fencing_token: int,
    ) -> None:
        self.durable.record_attempt_effect(
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
            attempt_id=attempt_id,
            owner_id=self.owner_id,
            fencing_token=fencing_token,
        )

    def _record_report_effect(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        report: PipelineRunReport,
        *,
        attempt_id: str,
        fencing_token: int,
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
        self.durable.record_attempt_effect(
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
            attempt_id=attempt_id,
            owner_id=self.owner_id,
            fencing_token=fencing_token,
        )


def unknown_commit_message() -> str:
    return fed_diagnostic(
        "unknown_commit_retry",
        "Unknown commits must not auto-retry; mark the attempt lost.",
    ).code


def _accepts_keyword(callable_object: Any, name: str) -> bool:
    try:
        parameters = inspect.signature(callable_object).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        parameter.name == name or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


__all__ = ["ExecutionHost", "UnknownCommitError", "unknown_commit_message"]
