# pyright: reportUnknownArgumentType=false
"""Thread-safe CP3 reference store used for conformance and local development.

It models atomic acceptance plus outbox insert under one lock. Production
deployments should use a transactional provider with the same semantics.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from etlantic.control_plane.action_jobs import (
    MAX_PREVIEW_RESULT_TTL_SECONDS,
    MIN_PREVIEW_RESULT_TTL_SECONDS,
)
from etlantic.control_plane.durable_models import (
    STATE_NAMESPACES,
    ActionJobRecord,
    ActionJobStatus,
    AttemptRecord,
    BaselineAcknowledgement,
    CheckpointRecord,
    DiffRecord,
    EffectRecord,
    ExecutionScopePage,
    LeaseRecord,
    OutboxRecord,
    PreviewWorkspace,
    RepairPlan,
    ReplayRecord,
    ResultPublicationRecord,
    ShadowRunRecord,
    StateDiagnostic,
    StateTransitionExplanation,
    SubmissionRecord,
    execution_context_from_submission,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import (
    ControlPlaneContext,
)
from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
    redact_or_preserve_execution_envelope,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.scope_key


_NON_TERMINAL = {"accepted", "dispatched", "cancel_requested"}
_ACTION_ERROR_CODES = frozenset(
    {
        "action_failed",
        "authorization_denied",
        "deadline_exceeded",
        "handler_unavailable",
        "invalid_action_request",
        "invalid_effect_receipt",
        "provider_timeout",
        "provision_parent_unavailable",
        "result_limit_exceeded",
    }
)


def _require_namespaced_checkpoint_id(checkpoint_id: str) -> None:
    if not any(checkpoint_id.startswith(prefix) for prefix in STATE_NAMESPACES):
        raise ValueError(
            "checkpoint_id must use a namespaced prefix "
            f"({', '.join(STATE_NAMESPACES)})"
        )


class MemoryDurableWorkStore:
    """Fail-closed in-memory implementation of :class:`DurableWorkStore`."""

    def __init__(self, *, admission_limit: int | None = None) -> None:
        self.admission_limit = admission_limit
        self._submissions: dict[tuple[str, str, str], SubmissionRecord] = {}
        self._idempotency: dict[tuple[str, str, str, str, str, str, str], str] = {}
        self._outbox: dict[tuple[str, str, str], OutboxRecord] = {}
        self._leases: dict[tuple[str, str, str], LeaseRecord] = {}
        self._attempts: dict[tuple[str, str, str], AttemptRecord] = {}
        self._result_publications: dict[
            tuple[str, str, str, str], ResultPublicationRecord
        ] = {}
        self._checkpoints: dict[tuple[str, str, str], CheckpointRecord] = {}
        self._effects: dict[tuple[str, str, str], EffectRecord] = {}
        self._previews: dict[tuple[str, str, str], PreviewWorkspace] = {}
        self._diffs: dict[tuple[str, str, str], DiffRecord] = {}
        self._shadows: dict[tuple[str, str, str], ShadowRunRecord] = {}
        self._baselines: dict[tuple[str, str, str], BaselineAcknowledgement] = {}
        self._action_jobs: dict[tuple[str, str, str], ActionJobRecord] = {}
        self._action_idempotency: dict[tuple[str, ...], str] = {}
        self._diagnostics: list[StateDiagnostic] = []
        self._lock = threading.RLock()

    def accept(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        operation: str,
        plan_fingerprint: str,
        revision_id: str | None = None,
        plugin_fingerprint: str | None = None,
        policy_fingerprint: str | None = None,
        input_snapshot: str | None = None,
        schema_observation_fingerprint: str | None = None,
        schema_baseline_id: str | None = None,
        submission_id: str | None = None,
        run_id: str | None = None,
    ) -> tuple[SubmissionRecord, bool]:
        self._require_nonempty(
            idempotency_key,
            "idempotency_key",
            operation,
            "operation",
            plan_fingerprint,
            "plan_fingerprint",
        )
        if submission_id is not None:
            self._require_nonempty(submission_id, "submission_id")
        if run_id is not None:
            self._require_nonempty(run_id, "run_id")
        idem = (
            *_scope(ctx),
            ctx.principal.issuer or "",
            ctx.principal.kind,
            ctx.principal.subject,
            operation,
            idempotency_key,
        )
        safe_input_snapshot = redact_or_preserve_execution_envelope(input_snapshot)
        requested = (
            plan_fingerprint,
            revision_id,
            plugin_fingerprint,
            policy_fingerprint,
            safe_input_snapshot,
            schema_observation_fingerprint,
            schema_baseline_id,
            ctx.environment.name,
            ctx.security_domain.domain_id,
            ctx.resource_owner_id,
        )
        with self._lock:
            existing_id = self._idempotency.get(idem)
            if existing_id is not None:
                prior = self._submissions[(*_scope(ctx), existing_id)]
                actual = (
                    prior.plan_fingerprint,
                    prior.revision_id,
                    prior.plugin_fingerprint,
                    prior.policy_fingerprint,
                    prior.input_snapshot,
                    prior.schema_observation_fingerprint,
                    prior.schema_baseline_id,
                    prior.environment,
                    prior.security_domain_id,
                    prior.resource_owner_id,
                )
                if actual != requested:
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with different immutable inputs"
                    )
                if submission_id is not None and submission_id != existing_id:
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with different submission_id"
                    )
                if (
                    run_id is not None
                    and prior.run_id is not None
                    and run_id != prior.run_id
                ):
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with different run_id"
                    )
                return deepcopy(prior), False
            if self.admission_limit is not None:
                in_flight = sum(
                    1
                    for (t, _workspace, _), row in self._submissions.items()
                    if t == ctx.tenant.tenant_id and row.status in _NON_TERMINAL
                )
                if in_flight >= self.admission_limit:
                    raise ControlPlaneError.conflict(
                        "Per-tenant admission limit exceeded"
                    )
            if submission_id is None:
                submission_id = f"sub-{uuid.uuid4().hex[:16]}"
            elif (*_scope(ctx), submission_id) in self._submissions:
                raise ControlPlaneError.conflict(
                    "submission_id already exists for a different accept"
                )
            record = SubmissionRecord(
                submission_id,
                *_scope(ctx),
                ctx.principal.subject,
                operation,
                idempotency_key,
                _iso(),
                plan_fingerprint,
                revision_id,
                plugin_fingerprint,
                policy_fingerprint,
                safe_input_snapshot,
                ctx.principal.issuer,
                ctx.principal.kind,
                schema_observation_fingerprint=schema_observation_fingerprint,
                schema_baseline_id=schema_baseline_id,
                environment=ctx.environment.name,
                security_domain_id=ctx.security_domain.domain_id,
                resource_owner_id=ctx.resource_owner_id,
                run_id=run_id,
            )
            payload = hashlib.sha256(
                "|".join(str(v or "") for v in requested).encode()
            ).hexdigest()
            outbox = OutboxRecord(
                f"out-{uuid.uuid4().hex[:16]}",
                submission_id,
                *_scope(ctx),
                _iso(),
                payload,
            )
            self._submissions[(*_scope(ctx), submission_id)] = record
            self._outbox[(*_scope(ctx), outbox.outbox_id)] = outbox
            self._idempotency[idem] = submission_id
            return deepcopy(record), True

    @staticmethod
    def _require_nonempty(*values: str) -> None:
        for value, name in zip(values[::2], values[1::2], strict=True):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")

    def list_execution_scopes(
        self,
        ctx: ControlPlaneContext,
        *,
        after_submission_id: str | None = None,
        through_submission_id: str | None = None,
        limit: int = 100,
    ) -> ExecutionScopePage:
        """Return a bounded page of complete accepted execution scopes."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._lock:
            scope = _scope(ctx)
            workspace_rows = [
                (key[2], row)
                for key, row in self._submissions.items()
                if key[:2] == scope
            ]
            high_watermark = through_submission_id
            if high_watermark is None and workspace_rows:
                high_watermark = workspace_rows[-1][0]
            watermark_index = next(
                (
                    index
                    for index, (submission_id, _row) in enumerate(workspace_rows)
                    if submission_id == high_watermark
                ),
                -1,
            )
            candidates = []
            if watermark_index >= 0:
                candidates = sorted(
                    (
                        item
                        for item in workspace_rows[: watermark_index + 1]
                        if after_submission_id is None or item[0] > after_submission_id
                    ),
                    key=lambda item: item[0],
                )
        has_more = len(candidates) > limit
        selected = candidates[:limit]
        scopes: list[ControlPlaneContext] = []
        seen: set[ControlPlaneContext] = set()
        for _submission_id, submission in selected:
            accepted_ctx = execution_context_from_submission(submission)
            if accepted_ctx is not None and accepted_ctx not in seen:
                seen.add(accepted_ctx)
                scopes.append(accepted_ctx)
        return ExecutionScopePage(
            scopes=tuple(scopes),
            next_cursor=selected[-1][0] if has_more and selected else None,
            high_watermark=high_watermark,
        )

    def pending_outbox(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ) -> list[OutboxRecord]:
        with self._lock:
            return [
                deepcopy(row)
                for (t, w, _), row in self._outbox.items()
                if (t, w) == _scope(ctx)
                and row.published_at is None
                and self._submissions.get((t, w, row.submission_id)) is not None
                and self._submissions[(t, w, row.submission_id)].status
                not in {"cancelled", "completed", "failed"}
            ][: max(0, limit)]

    def reconcile_terminal_outbox(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ) -> list[OutboxRecord]:
        """Acknowledge work whose terminal state committed before its outbox ack."""
        reconciled: list[OutboxRecord] = []
        with self._lock:
            candidates = sorted(
                (
                    (key, row)
                    for key, row in self._outbox.items()
                    if key[:2] == _scope(ctx) and row.published_at is None
                ),
                key=lambda item: (item[1].created_at, item[1].outbox_id),
            )
            for key, row in candidates:
                if len(reconciled) >= max(0, limit):
                    break
                submission = self._submissions.get((*_scope(ctx), row.submission_id))
                if submission is None or submission.status not in {
                    "cancelled",
                    "completed",
                    "failed",
                }:
                    continue
                acknowledged = replace(
                    row,
                    published_at=_iso(),
                    delivery_count=row.delivery_count + 1,
                )
                self._outbox[key] = acknowledged
                reconciled.append(deepcopy(acknowledged))
        return reconciled

    def reconcile_cancelled_submissions(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ) -> list[SubmissionRecord]:
        """Finalize cancellation requests after their worker lease expires."""
        reconciled: list[SubmissionRecord] = []
        now = _now()
        with self._lock:
            candidates = sorted(
                (
                    (key, row)
                    for key, row in self._submissions.items()
                    if key[:2] == _scope(ctx) and row.status == "cancel_requested"
                ),
                key=lambda item: (item[1].created_at, item[1].submission_id),
            )
            for key, submission in candidates:
                if len(reconciled) >= max(0, limit):
                    break
                lease = self._leases.get(key)
                if lease is not None and _parse(lease.expires_at) > now:
                    continue
                had_running_attempt = False
                for attempt_key, attempt in tuple(self._attempts.items()):
                    if (
                        attempt_key[:2] == _scope(ctx)
                        and attempt.submission_id == submission.submission_id
                        and attempt.status == "running"
                    ):
                        self._attempts[attempt_key] = replace(
                            attempt, status="lost", completed_at=_iso(now)
                        )
                        had_running_attempt = True
                if had_running_attempt:
                    self._record_unknown_effect_locked(ctx, submission.submission_id)
                cancelled = replace(submission, status="cancelled")
                self._submissions[key] = cancelled
                self._ack_submission_outbox_locked(ctx, submission.submission_id)
                reconciled.append(deepcopy(cancelled))
        return reconciled

    def _record_unknown_effect_locked(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> None:
        effect_id = f"{submission_id}:execution"
        key = (*_scope(ctx), effect_id)
        existing = self._effects.get(key)
        if existing is not None and existing.status == "committed":
            return
        self._effects[key] = EffectRecord(
            effect_id=effect_id,
            submission_id=submission_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            status="unknown",
            recorded_at=_iso(),
            authoritative=True,
        )

    def _ack_submission_outbox_locked(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> None:
        for key, row in tuple(self._outbox.items()):
            if (
                key[:2] == _scope(ctx)
                and row.submission_id == submission_id
                and row.published_at is None
            ):
                self._outbox[key] = replace(
                    row,
                    published_at=_iso(),
                    delivery_count=row.delivery_count + 1,
                )

    def get_submission(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> SubmissionRecord:
        """Return an accepted execution record inside the caller's scope."""
        with self._lock:
            row = self._submissions.get((*_scope(ctx), submission_id))
            if row is None:
                raise ControlPlaneError.not_found("Submission not found")
            return deepcopy(row)

    def get_submission_by_idempotency(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        operation: str = "run.submit",
    ) -> SubmissionRecord | None:
        """Resolve a prior accepted command in its complete principal scope."""
        idem = (
            *_scope(ctx),
            ctx.principal.issuer or "",
            ctx.principal.kind,
            ctx.principal.subject,
            operation,
            idempotency_key,
        )
        with self._lock:
            submission_id = self._idempotency.get(idem)
            if submission_id is None:
                return None
            row = self._submissions.get((*_scope(ctx), submission_id))
            return deepcopy(row) if row is not None else None

    def accept_action_job(
        self,
        ctx: ControlPlaneContext,
        *,
        action: str,
        idempotency_key: str,
        request: Mapping[str, Any],
        deadline_at: str,
    ) -> ActionJobRecord:
        """Durably accept one redacted, owner-scoped action intent."""
        if not action.strip() or not idempotency_key.strip():
            raise ValueError("action and idempotency_key must not be empty")
        try:
            deadline = datetime.fromisoformat(deadline_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "Action deadline must be an ISO timestamp with a timezone",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            ) from exc
        if deadline.tzinfo is None or deadline.utcoffset() is None:
            raise ControlPlaneError(
                "Action deadline must be an ISO timestamp with a timezone",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if deadline <= _now():
            raise ControlPlaneError.conflict("Action deadline has already elapsed")
        safe_request = redact_control_plane_payload(dict(request))
        if not isinstance(safe_request, dict):
            raise ValueError("action request must be a JSON object")
        request_json = json.dumps(
            safe_request, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        if len(request_json.encode("utf-8")) > 64 * 1024:
            raise ControlPlaneError(
                "Connector action request exceeds the configured byte limit",
                code="PMCP413",
                status=413,
                title="Payload Too Large",
                type="etlantic.control_plane/payload_too_large",
            )
        fingerprint = hashlib.sha256(
            json.dumps(
                {"action": action, "request": safe_request},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        owner_id = ctx.resource_owner_id or ctx.principal.subject
        legacy_idem = (
            *_scope(ctx),
            ctx.principal.issuer or "",
            ctx.principal.kind,
            ctx.principal.subject,
            action,
            idempotency_key,
        )
        idem = (
            *_scope(ctx),
            ctx.security_domain.domain_id,
            ctx.environment.name,
            owner_id,
            ctx.principal.issuer or "",
            ctx.principal.kind,
            ctx.principal.subject,
            action,
            idempotency_key,
        )
        with self._lock:
            prior_id = self._action_idempotency.get(idem)
            if prior_id is None:
                legacy_prior_id = self._action_idempotency.get(legacy_idem)
                legacy_prior = (
                    self._action_jobs.get((*_scope(ctx), legacy_prior_id))
                    if legacy_prior_id is not None
                    else None
                )
                if (
                    legacy_prior is not None
                    and legacy_prior.owner_id == owner_id
                    and legacy_prior.security_domain_id == ctx.security_domain.domain_id
                    and legacy_prior.environment == ctx.environment.name
                ):
                    prior_id = legacy_prior.action_id
            if prior_id is not None:
                prior = self._action_jobs[(*_scope(ctx), prior_id)]
                if prior.request_fingerprint != fingerprint:
                    raise ControlPlaneError.conflict(
                        "Action idempotency key reuse has different inputs"
                    )
                if (
                    prior.action
                    in {"connector.provision", "connector.provision.cleanup"}
                    and prior.result_json is None
                    and prior.status in {"timed_out", "failed"}
                    and prior.error_code
                    in {"deadline_exceeded", "action_failed", "provider_timeout"}
                ):
                    # Explicit same-key recovery keeps the provider action ID
                    # and immutable intent. The next claim obtains a new fence
                    # and recovers the registry before attempting create-only IO.
                    prior = replace(
                        prior,
                        status="queued",
                        phase="queued",
                        deadline_at=deadline_at,
                        completed_at=None,
                        error_code=None,
                    )
                    self._action_jobs[(*_scope(ctx), prior_id)] = prior
                return deepcopy(prior)
            record = ActionJobRecord(
                action_id=f"act-{uuid.uuid4().hex[:24]}",
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                owner_id=owner_id,
                principal_subject=ctx.principal.subject,
                principal_issuer=ctx.principal.issuer,
                principal_kind=ctx.principal.kind,
                environment=ctx.environment.name,
                security_domain_id=ctx.security_domain.domain_id,
                action=action,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                request_json=request_json,
                created_at=_iso(),
                deadline_at=deadline_at,
            )
            self._action_jobs[(*_scope(ctx), record.action_id)] = record
            self._action_idempotency[idem] = record.action_id
            return deepcopy(record)

    def get_action_job(
        self, ctx: ControlPlaneContext, action_id: str
    ) -> ActionJobRecord:
        """Read an action receipt within the caller's resource-owner scope."""
        owner_id = ctx.resource_owner_id or ctx.principal.subject
        with self._lock:
            record = self._action_jobs.get((*_scope(ctx), action_id))
            if (
                record is None
                or record.owner_id != owner_id
                or record.security_domain_id != ctx.security_domain.domain_id
                or record.environment != ctx.environment.name
            ):
                raise ControlPlaneError.not_found("Action job not found")
            return deepcopy(record)

    def get_action_job_by_idempotency(
        self,
        ctx: ControlPlaneContext,
        *,
        action: str,
        idempotency_key: str,
    ) -> ActionJobRecord | None:
        owner_id = ctx.resource_owner_id or ctx.principal.subject
        idem = (
            *_scope(ctx),
            ctx.security_domain.domain_id,
            ctx.environment.name,
            owner_id,
            ctx.principal.issuer or "",
            ctx.principal.kind,
            ctx.principal.subject,
            action,
            idempotency_key,
        )
        legacy_idem = (
            *_scope(ctx),
            ctx.principal.issuer or "",
            ctx.principal.kind,
            ctx.principal.subject,
            action,
            idempotency_key,
        )
        with self._lock:
            action_id = self._action_idempotency.get(idem)
            if action_id is None:
                action_id = self._action_idempotency.get(legacy_idem)
            if action_id is None:
                return None
            record = self._action_jobs.get((*_scope(ctx), action_id))
            if (
                record is None
                or record.owner_id != owner_id
                or record.security_domain_id != ctx.security_domain.domain_id
                or record.environment != ctx.environment.name
            ):
                return None
            return deepcopy(record)

    def cancel_action_job(
        self, ctx: ControlPlaneContext, action_id: str
    ) -> ActionJobRecord:
        owner_id = ctx.resource_owner_id or ctx.principal.subject
        key = (*_scope(ctx), action_id)
        with self._lock:
            row = self._action_jobs.get(key)
            if (
                row is None
                or row.owner_id != owner_id
                or row.security_domain_id != ctx.security_domain.domain_id
                or row.environment != ctx.environment.name
            ):
                raise ControlPlaneError.not_found("Preparation operation not found")
            if row.action != "run.prepare":
                raise ControlPlaneError.not_found("Preparation operation not found")
            if row.status == "queued":
                cancelled = replace(
                    row,
                    status="cancelled",
                    phase="cancelled",
                    completed_at=_iso(),
                    error_code=None,
                )
            elif row.status == "running" and row.phase != "accepting":
                cancelled = replace(row, status="cancel_requested")
            elif row.status == "cancel_requested":
                return deepcopy(row)
            else:
                raise ControlPlaneError.conflict(
                    "Preparation can no longer be cancelled",
                    code="PMCP409",
                    extensions={"reason": "acceptance_started"},
                )
            self._action_jobs[key] = cancelled
            return deepcopy(cancelled)

    def list_action_jobs(
        self,
        ctx: ControlPlaneContext,
        *,
        after: tuple[str, str] | None = None,
        limit: int = 100,
    ) -> list[ActionJobRecord]:
        """Return one bounded page of owner-scoped action receipts."""
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        owner_id = ctx.resource_owner_id or ctx.principal.subject
        with self._lock:
            records = sorted(
                (
                    row
                    for key, row in self._action_jobs.items()
                    if key[:2] == _scope(ctx)
                    and row.owner_id == owner_id
                    and row.security_domain_id == ctx.security_domain.domain_id
                    and row.environment == ctx.environment.name
                ),
                key=lambda row: (row.created_at, row.action_id),
            )
            if after is not None:
                records = [
                    row for row in records if (row.created_at, row.action_id) > after
                ]
            return [deepcopy(row) for row in records[:limit]]

    def claim_action_job(
        self,
        ctx: ControlPlaneContext,
        *,
        worker_id: str,
        lease_seconds: int = 30,
        now: datetime | None = None,
    ) -> ActionJobRecord | None:
        """Claim the earliest live action and fence stale workers."""
        if not worker_id.strip() or type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("worker_id and a positive lease_seconds are required")
        current = now or _now()
        current_iso = _iso(current)
        lease_expires = _iso(current + timedelta(seconds=lease_seconds))
        with self._lock:
            scoped = [
                (key, row)
                for key, row in self._action_jobs.items()
                if key[:2] == _scope(ctx)
                and row.status in {"queued", "running", "cancel_requested"}
            ]
            for key, row in scoped:
                if (
                    row.status == "cancel_requested"
                    and row.lease_expires_at is not None
                    and _parse(row.lease_expires_at) <= current
                ):
                    self._action_jobs[key] = replace(
                        row,
                        status="cancelled",
                        phase="cancelled",
                        completed_at=current_iso,
                        worker_id=None,
                        lease_expires_at=None,
                    )
                    continue
                if _parse(row.deadline_at) <= current:
                    self._action_jobs[key] = replace(
                        row,
                        status="timed_out",
                        completed_at=current_iso,
                        worker_id=None,
                        lease_expires_at=None,
                        error_code="deadline_exceeded",
                    )
            candidates = sorted(
                (
                    (key, row)
                    for key, row in self._action_jobs.items()
                    if key[:2] == _scope(ctx)
                    and row.status in {"queued", "running"}
                    and _parse(row.deadline_at) > current
                    and (
                        row.status == "queued"
                        or row.lease_expires_at is None
                        or _parse(row.lease_expires_at) <= current
                    )
                ),
                key=lambda item: (item[1].created_at, item[1].action_id),
            )
            if not candidates:
                return None
            key, row = candidates[0]
            claimed = replace(
                row,
                status="running",
                attempt=row.attempt + 1,
                fencing_token=row.fencing_token + 1,
                worker_id=worker_id,
                lease_expires_at=lease_expires,
                started_at=row.started_at or current_iso,
                phase="preparing" if row.phase == "queued" else row.phase,
            )
            self._action_jobs[key] = claimed
            return deepcopy(claimed)

    def heartbeat_action_job(
        self,
        ctx: ControlPlaneContext,
        action_id: str,
        *,
        worker_id: str,
        fencing_token: int,
        lease_seconds: int = 30,
        now: datetime | None = None,
    ) -> ActionJobRecord:
        if not worker_id.strip() or type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("worker_id and a positive lease_seconds are required")
        current = now or _now()
        key = (*_scope(ctx), action_id)
        with self._lock:
            row = self._action_jobs.get(key)
            if row is None:
                raise ControlPlaneError.not_found("Action job not found")
            if (
                row.status not in {"running", "cancel_requested"}
                or row.worker_id != worker_id
                or row.fencing_token != fencing_token
                or row.lease_expires_at is None
                or _parse(row.lease_expires_at) <= current
            ):
                raise ControlPlaneError.conflict("Action worker lease is stale")
            updated = replace(
                row,
                lease_expires_at=_iso(current + timedelta(seconds=lease_seconds)),
            )
            self._action_jobs[key] = updated
            return deepcopy(updated)

    def mark_action_job_accepting(
        self,
        ctx: ControlPlaneContext,
        action_id: str,
        *,
        worker_id: str,
        fencing_token: int,
        now: datetime | None = None,
    ) -> ActionJobRecord:
        current = now or _now()
        key = (*_scope(ctx), action_id)
        with self._lock:
            row = self._action_jobs.get(key)
            if row is None:
                raise ControlPlaneError.not_found("Action job not found")
            if row.status == "cancel_requested":
                raise ControlPlaneError.conflict(
                    "Preparation was cancelled before acceptance",
                    code="PMCP409",
                    extensions={"reason": "cancelled"},
                )
            if (
                row.action != "run.prepare"
                or row.status != "running"
                or row.worker_id != worker_id
                or row.fencing_token != fencing_token
                or row.lease_expires_at is None
                or _parse(row.lease_expires_at) <= current
            ):
                raise ControlPlaneError.conflict("Action worker lease is stale")
            if row.phase == "accepting":
                return deepcopy(row)
            updated = replace(row, phase="accepting")
            self._action_jobs[key] = updated
            return deepcopy(updated)

    def finish_action_job(
        self,
        ctx: ControlPlaneContext,
        action_id: str,
        *,
        worker_id: str,
        fencing_token: int,
        status: ActionJobStatus,
        result: Mapping[str, Any] | None = None,
        error_code: str | None = None,
        result_ttl_seconds: int | None = None,
        now: datetime | None = None,
    ) -> ActionJobRecord:
        """Finish a claimed action iff the worker still holds its fence."""
        if status not in {"succeeded", "failed", "timed_out", "cancelled"}:
            raise ValueError("action job completion status is invalid")
        if result_ttl_seconds is not None and (
            type(result_ttl_seconds) is not int or result_ttl_seconds < 1
        ):
            raise ValueError("result_ttl_seconds must be a positive integer")
        current = now or _now()
        key = (*_scope(ctx), action_id)
        with self._lock:
            row = self._action_jobs.get(key)
            if row is None:
                raise ControlPlaneError.not_found("Action job not found")
            retains_effect = (
                row.action
                in {"connector.provision", "connector.provision.cleanup", "run.prepare"}
                and status == "succeeded"
                and result is not None
                and result_ttl_seconds is None
            )
            effect_json = (
                json.dumps(
                    redact_control_plane_payload(dict(result or {})),
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                if retains_effect
                else None
            )
            if (
                row.status in {"timed_out", "cancelled"}
                and row.fencing_token == fencing_token
                and row.started_at is not None
                and retains_effect
            ):
                # A receipt describes a committed mutation, not a successful
                # deadline outcome. Preserve the terminal status while keeping
                # the exact fenced effect available for recovery.
                if row.result_json is not None and row.result_json != effect_json:
                    raise ControlPlaneError.conflict("Action effect receipt conflicts")
                finished = replace(row, result_json=effect_json)
                self._action_jobs[key] = finished
                return deepcopy(finished)
            if (
                row.status not in {"running", "cancel_requested"}
                or row.worker_id != worker_id
                or row.fencing_token != fencing_token
                or row.lease_expires_at is None
                or _parse(row.lease_expires_at) <= current
            ):
                raise ControlPlaneError.conflict("Action worker lease is stale")
            if row.status == "cancel_requested" or status == "cancelled":
                finished = replace(
                    row,
                    status="cancelled",
                    phase="cancelled",
                    completed_at=_iso(current),
                    worker_id=None,
                    lease_expires_at=None,
                    result_json=effect_json,
                    result_expires_at=None,
                    error_code=None,
                )
            elif status == "timed_out":
                if result_ttl_seconds is not None:
                    raise ValueError(
                        "timed-out action jobs cannot retain result payloads"
                    )
                if _parse(row.deadline_at) > current:
                    raise ControlPlaneError.conflict("Action deadline has not elapsed")
                finished = replace(
                    row,
                    status="timed_out",
                    completed_at=_iso(current),
                    worker_id=None,
                    lease_expires_at=None,
                    error_code="deadline_exceeded",
                )
            elif _parse(row.deadline_at) <= current:
                finished = replace(
                    row,
                    status="timed_out",
                    completed_at=_iso(current),
                    worker_id=None,
                    lease_expires_at=None,
                    error_code="deadline_exceeded",
                    result_json=effect_json,
                )
            else:
                if status == "succeeded":
                    if row.action == "connector.preview" and result_ttl_seconds is None:
                        raise ValueError(
                            "connector preview results require separate retention"
                        )
                    if (
                        row.action == "connector.preview"
                        and result_ttl_seconds is not None
                        and not (
                            MIN_PREVIEW_RESULT_TTL_SECONDS
                            <= result_ttl_seconds
                            <= MAX_PREVIEW_RESULT_TTL_SECONDS
                        )
                    ):
                        raise ValueError(
                            "connector preview result TTL must be between "
                            f"{MIN_PREVIEW_RESULT_TTL_SECONDS} and "
                            f"{MAX_PREVIEW_RESULT_TTL_SECONDS} seconds"
                        )
                    if (
                        row.action != "connector.preview"
                        and result_ttl_seconds is not None
                    ):
                        raise ValueError(
                            "result TTL applies only to connector preview actions"
                        )
                elif result_ttl_seconds is not None:
                    raise ValueError("failed action jobs cannot retain result payloads")
                safe_result = redact_control_plane_payload(dict(result or {}))
                result_json = json.dumps(
                    safe_result,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                finished = replace(
                    row,
                    status=status,
                    completed_at=_iso(current),
                    worker_id=None,
                    lease_expires_at=None,
                    result_json=result_json if status == "succeeded" else None,
                    result_expires_at=(
                        _iso(current + timedelta(seconds=result_ttl_seconds))
                        if status == "succeeded" and result_ttl_seconds is not None
                        else None
                    ),
                    error_code=(
                        error_code
                        if status == "failed" and error_code in _ACTION_ERROR_CODES
                        else "action_failed"
                        if status == "failed"
                        else None
                    ),
                )
            self._action_jobs[key] = finished
            return deepcopy(finished)

    def cleanup_expired_action_results(
        self,
        ctx: ControlPlaneContext,
        *,
        limit: int = 100,
        now: datetime | None = None,
    ) -> int:
        """Delete expired preview payloads while retaining action receipts."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        current = now or _now()
        with self._lock:
            expired = sorted(
                (
                    (key, row)
                    for key, row in self._action_jobs.items()
                    if key[:2] == _scope(ctx)
                    and row.result_json is not None
                    and row.result_expires_at is not None
                    and _parse(row.result_expires_at) <= current
                ),
                key=lambda item: (item[1].result_expires_at or "", item[1].action_id),
            )[:limit]
            for key, row in expired:
                self._action_jobs[key] = replace(row, result_json=None)
            return len(expired)

    def list_attempts(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> list[AttemptRecord]:
        """Return a scoped attempt history in stable start order."""
        with self._lock:
            if (*_scope(ctx), submission_id) not in self._submissions:
                raise ControlPlaneError.not_found("Submission not found")
            attempts = [
                deepcopy(row)
                for (tenant, workspace, _), row in self._attempts.items()
                if (tenant, workspace) == _scope(ctx)
                and row.submission_id == submission_id
            ]
            return sorted(attempts, key=lambda row: (row.started_at, row.attempt_id))

    def mark_published(self, ctx: ControlPlaneContext, outbox_id: str) -> OutboxRecord:
        key = (*_scope(ctx), outbox_id)
        with self._lock:
            row = self._outbox.get(key)
            if row is None:
                raise ControlPlaneError.not_found("Outbox record not found")
            if row.published_at is None:
                row = replace(
                    row, published_at=_iso(), delivery_count=row.delivery_count + 1
                )
                self._outbox[key] = row
                submission_key = (*_scope(ctx), row.submission_id)
                submission = self._submissions[submission_key]
                # Never revive cancel_requested / terminal work via publish.
                if submission.status == "accepted":
                    self._submissions[submission_key] = replace(
                        submission, status="dispatched"
                    )
            return deepcopy(row)

    def cancel_submission(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> SubmissionRecord:
        key = (*_scope(ctx), submission_id)
        with self._lock:
            submission = self._submissions.get(key)
            if submission is None:
                raise ControlPlaneError.not_found("Submission not found")
            if submission.status in {"cancelled", "completed", "failed"}:
                raise ControlPlaneError.conflict(
                    "Terminal submission cannot be cancelled"
                )
            if submission.status != "cancel_requested":
                submission = replace(submission, status="cancel_requested")
                self._submissions[key] = submission
            lease = self._leases.get(key)
            lease_active = lease is not None and _parse(lease.expires_at) > _now()
            running_attempts = [
                (attempt_key, attempt)
                for attempt_key, attempt in self._attempts.items()
                if attempt_key[:2] == _scope(ctx)
                and attempt.submission_id == submission_id
                and attempt.status == "running"
            ]
            # Let a live attempt retain its lease briefly so it can acknowledge
            # cooperative cancellation. Queued work has no owner to wake, so
            # expire its lease tombstone and let a host reconcile it at once.
            if lease is not None and lease_active and not running_attempts:
                self._leases[key] = replace(
                    lease,
                    expires_at=_iso(_now() - timedelta(seconds=1)),
                    heartbeat_at=_iso(),
                )
            return deepcopy(submission)

    def acquire_lease(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        ttl_seconds: int,
    ) -> LeaseRecord:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        key = (*_scope(ctx), submission_id)
        with self._lock:
            submission = self._submissions.get(key)
            if submission is None:
                raise ControlPlaneError.not_found("Submission not found")
            if submission.status in {
                "cancel_requested",
                "cancelled",
                "completed",
                "failed",
            }:
                raise ControlPlaneError.conflict(
                    "Submission is not eligible for execution"
                )
            old = self._leases.get(key)
            now = _now()
            if (
                old is not None
                and _parse(old.expires_at) > now
                and old.owner_id != owner_id
            ):
                raise ControlPlaneError.conflict(
                    "Submission is leased by another execution host"
                )
            token = (
                old.fencing_token
                if old and old.owner_id == owner_id and _parse(old.expires_at) > now
                else (old.fencing_token if old else 0) + 1
            )
            lease = LeaseRecord(
                submission_id,
                *_scope(ctx),
                owner_id,
                token,
                _iso(now),
                _iso(now + timedelta(seconds=ttl_seconds)),
                _iso(now),
            )
            self._leases[key] = lease
            return deepcopy(lease)

    def heartbeat(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        ttl_seconds: int,
    ) -> LeaseRecord:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        key = (*_scope(ctx), submission_id)
        with self._lock:
            submission = self._submissions.get(key)
            if submission is None:
                raise ControlPlaneError.not_found("Submission not found")
            if submission.status in {
                "cancel_requested",
                "cancelled",
                "completed",
                "failed",
            }:
                raise ControlPlaneError.conflict(
                    "Submission is not eligible for heartbeat"
                )
            old = self._require_lease(key, owner_id, fencing_token)
            now = _now()
            lease = replace(
                old,
                heartbeat_at=_iso(now),
                expires_at=_iso(now + timedelta(seconds=ttl_seconds)),
            )
            self._leases[key] = lease
            return deepcopy(lease)

    def release_lease(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
    ) -> None:
        key = (*_scope(ctx), submission_id)
        with self._lock:
            old = self._require_lease(key, owner_id, fencing_token)
            # Keep an expired tombstone so the next acquire increments fencing.
            self._leases[key] = replace(
                old,
                expires_at=_iso(_now() - timedelta(seconds=1)),
                heartbeat_at=_iso(),
            )

    def _require_lease(
        self, key: tuple[str, str, str], owner_id: str, token: int
    ) -> LeaseRecord:
        lease = self._leases.get(key)
        if (
            lease is None
            or lease.owner_id != owner_id
            or lease.fencing_token != token
            or _parse(lease.expires_at) <= _now()
        ):
            raise ControlPlaneError.conflict("Stale or invalid execution lease")
        return lease

    def start_attempt(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        context: Mapping[str, Any] | None = None,
    ) -> AttemptRecord:
        key = (*_scope(ctx), submission_id)
        with self._lock:
            self._require_lease(key, owner_id, fencing_token)
            submission = self._submissions[key]
            if submission.status == "cancel_requested":
                raise ControlPlaneError.conflict(
                    "Cancelled submission cannot start an attempt"
                )
            if submission.status in {"cancelled", "completed", "failed"}:
                raise ControlPlaneError.conflict(
                    "Terminal submission cannot start an attempt"
                )
            for attempt_key, attempt in list(self._attempts.items()):
                if (
                    attempt_key[:2] == _scope(ctx)
                    and attempt.submission_id == submission_id
                    and attempt.status == "running"
                ):
                    if attempt.fencing_token >= fencing_token:
                        raise ControlPlaneError.conflict(
                            "Submission already has a running attempt with the current fencing token"
                        )
                    # A new fencing token proves that the previous lease
                    # expired or was replaced. Preserve its outcome as lost;
                    # the worker must consult the stable result/effect before
                    # deciding whether execution can safely resume.
                    self._attempts[attempt_key] = replace(
                        attempt, status="lost", completed_at=_iso()
                    )
            # Caller context first, then authoritative submission fields last.
            merged = dict(context or {})
            merged.update(
                {
                    "plan_fingerprint": submission.plan_fingerprint,
                    "revision_id": submission.revision_id,
                    "schema_baseline_id": submission.schema_baseline_id,
                    "schema_observation_fingerprint": (
                        submission.schema_observation_fingerprint
                    ),
                }
            )
            safe_context = redact_control_plane_payload(merged)
            record = AttemptRecord(
                f"att-{uuid.uuid4().hex[:16]}",
                submission_id,
                *_scope(ctx),
                owner_id,
                fencing_token,
                _iso(),
                context=dict(safe_context) if isinstance(safe_context, dict) else {},
            )
            self._attempts[(*_scope(ctx), record.attempt_id)] = record
            return deepcopy(record)

    def finish_attempt(
        self,
        ctx: ControlPlaneContext,
        attempt_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        status: str,
    ) -> AttemptRecord:
        if status not in {"cancelled", "completed", "failed", "lost"}:
            raise ValueError("attempt status must be terminal")
        key = (*_scope(ctx), attempt_id)
        with self._lock:
            attempt = self._attempts.get(key)
            if attempt is None:
                raise ControlPlaneError.not_found("Attempt not found")
            submission_key = (*_scope(ctx), attempt.submission_id)
            submission = self._submissions[submission_key]
            # After cancel expires the lease, still allow the holder to
            # acknowledge cancel with the matching fencing token.
            if submission.status == "cancel_requested":
                lease = self._leases.get(submission_key)
                if (
                    lease is None
                    or lease.owner_id != owner_id
                    or lease.fencing_token != fencing_token
                ):
                    raise ControlPlaneError.conflict("Stale or invalid execution lease")
            else:
                self._require_lease(submission_key, owner_id, fencing_token)
            if attempt.status != "running":
                return deepcopy(attempt)
            attempt_status = status
            terminal_status = "completed" if status == "completed" else "failed"
            if status == "cancelled" or submission.status == "cancel_requested":
                attempt_status = "cancelled"
                terminal_status = "cancelled"
            result = replace(attempt, status=attempt_status, completed_at=_iso())
            self._attempts[key] = result
            self._submissions[submission_key] = replace(
                submission, status=terminal_status
            )
            return deepcopy(result)

    def record_result_publication(
        self,
        ctx: ControlPlaneContext,
        record: ResultPublicationRecord,
        *,
        owner_id: str,
        fencing_token: int,
    ) -> ResultPublicationRecord:
        """Persist a secret-free report under the active execution fence."""
        if (record.tenant_id, record.workspace_id) != _scope(ctx):
            raise ControlPlaneError.forbidden(
                "Result publication must match the trusted scope"
            )
        if not record.submission_id or not record.attempt_id or not record.run_id:
            raise ValueError("result publication identities must be non-empty")
        if len(record.report_json.encode("utf-8")) > 4 * 1024 * 1024:
            raise ControlPlaneError.conflict(
                "Run report exceeds the durable recovery size limit",
                extensions={"reason": "result_too_large"},
            )
        if hashlib.sha256(record.report_json.encode("utf-8")).hexdigest() != (
            record.report_sha256
        ):
            raise ValueError("result publication fingerprint does not match report")
        try:
            report = json.loads(record.report_json)
        except (TypeError, ValueError) as exc:
            raise ValueError("result publication report is invalid JSON") from exc
        if not isinstance(report, dict):
            raise ValueError("result publication report identity is invalid")
        report_data = cast(dict[str, Any], report)
        if (
            report_data.get("schema") != "etlantic.run_report/1"
            or report_data.get("run_id") != record.run_id
        ):
            raise ValueError("result publication report identity is invalid")
        key = (*_scope(ctx), record.submission_id, record.attempt_id)
        with self._lock:
            submission_key = (*_scope(ctx), record.submission_id)
            self._require_lease(submission_key, owner_id, fencing_token)
            attempt = self._attempts.get((*_scope(ctx), record.attempt_id))
            if (
                attempt is None
                or attempt.submission_id != record.submission_id
                or attempt.owner_id != owner_id
                or attempt.fencing_token != fencing_token
            ):
                raise ControlPlaneError.conflict(
                    "Result publication does not match the current attempt fence"
                )
            prior = self._result_publications.get(key)
            if prior is not None:
                if prior.run_id != record.run_id:
                    raise ControlPlaneError.conflict(
                        "Result publication run identity changed"
                    )
                if prior.report_sha256 != record.report_sha256:
                    if prior.published_at is not None:
                        raise ControlPlaneError.conflict(
                            "Published run result is immutable"
                        )
                    record = replace(record, created_at=prior.created_at)
                elif prior.published_at is not None:
                    record = replace(record, published_at=prior.published_at)
            self._result_publications[key] = deepcopy(record)
            return deepcopy(record)

    def get_latest_result_publication(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> ResultPublicationRecord | None:
        with self._lock:
            rows = [
                record
                for key, record in self._result_publications.items()
                if key[:3] == (*_scope(ctx), submission_id)
            ]
            if not rows:
                return None
            return deepcopy(max(rows, key=lambda record: _parse(record.created_at)))

    def pending_result_publications(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ) -> Sequence[ResultPublicationRecord]:
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        with self._lock:
            rows = [
                record
                for key, record in self._result_publications.items()
                if key[:2] == _scope(ctx) and record.published_at is None
            ]
            rows.sort(key=lambda record: record.created_at)
            return tuple(deepcopy(rows[:limit]))

    def mark_result_publication_published(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        attempt_id: str,
        *,
        report_sha256: str,
    ) -> ResultPublicationRecord:
        key = (*_scope(ctx), submission_id, attempt_id)
        with self._lock:
            record = self._result_publications.get(key)
            if record is None:
                raise ControlPlaneError.not_found("Result publication not found")
            if record.report_sha256 != report_sha256:
                raise ControlPlaneError.conflict(
                    "Result publication fingerprint changed"
                )
            if record.published_at is None:
                record = replace(record, published_at=_iso())
                self._result_publications[key] = record
            return deepcopy(record)

    def compare_and_swap_checkpoint(
        self,
        ctx: ControlPlaneContext,
        checkpoint_id: str,
        *,
        expected_version: int | None,
        value_fingerprint: str,
        attempt_id: str,
        fencing_token: int,
        schema_baseline_id: str | None = None,
    ) -> CheckpointRecord:
        _require_namespaced_checkpoint_id(checkpoint_id)
        key = (*_scope(ctx), checkpoint_id)
        with self._lock:
            previous = self._checkpoints.get(key)
            version = previous.version if previous else None
            if version != expected_version:
                raise ControlPlaneError.conflict("Checkpoint compare-and-swap conflict")
            attempt = self._attempts.get((*_scope(ctx), attempt_id))
            if attempt is None or attempt.status != "running":
                raise ControlPlaneError.conflict(
                    "Checkpoint requires a current running attempt and fencing token"
                )
            submission = self._submissions.get((*_scope(ctx), attempt.submission_id))
            if submission is None or submission.status in {
                "cancel_requested",
                "cancelled",
                "completed",
                "failed",
            }:
                raise ControlPlaneError.conflict(
                    "Checkpoint CAS refused for cancelled or terminal submission"
                )
            self._require_lease(
                (*_scope(ctx), attempt.submission_id),
                attempt.owner_id,
                fencing_token,
            )
            record = CheckpointRecord(
                checkpoint_id,
                *_scope(ctx),
                (version or 0) + 1,
                value_fingerprint,
                _iso(),
                submission_id=attempt.submission_id,
                attempt_id=attempt_id,
                schema_baseline_id=schema_baseline_id
                or (previous.schema_baseline_id if previous else None),
            )
            self._checkpoints[key] = record
            return deepcopy(record)

    def explain_transition(
        self,
        ctx: ControlPlaneContext,
        checkpoint_id: str,
        *,
        expected_version: int | None,
        value_fingerprint: str,
    ) -> StateTransitionExplanation:
        _require_namespaced_checkpoint_id(checkpoint_id)
        with self._lock:
            previous = self._checkpoints.get((*_scope(ctx), checkpoint_id))
            current_version = previous.version if previous else None
            would = current_version == expected_version
            reason = (
                "compare-and-swap would succeed"
                if would
                else "expected version does not match current checkpoint"
            )
            return StateTransitionExplanation(
                f"xpl-{uuid.uuid4().hex[:16]}",
                *_scope(ctx),
                checkpoint_id,
                expected_version,
                value_fingerprint,
                current_version,
                previous.value_fingerprint if previous else None,
                would,
                reason,
                _iso(),
            )

    def diagnose_checkpoint(
        self,
        ctx: ControlPlaneContext,
        checkpoint_id: str,
        *,
        kind: str = "corruption",
        detail: str = "",
    ) -> StateDiagnostic:
        if kind not in {"corruption", "migration", "conflict"}:
            raise ValueError("unsupported diagnostic kind")
        _require_namespaced_checkpoint_id(checkpoint_id)
        with self._lock:
            previous = self._checkpoints.get((*_scope(ctx), checkpoint_id))
            if previous is None and kind != "migration":
                raise ControlPlaneError.not_found("Checkpoint not found")
            diagnostic = StateDiagnostic(
                f"diag-{uuid.uuid4().hex[:16]}",
                *_scope(ctx),
                checkpoint_id,
                kind,  # type: ignore[arg-type]
                redact_control_plane_text(detail) or kind,
                _iso(),
                recoverable=kind == "migration",
            )
            self._diagnostics.append(diagnostic)
            return deepcopy(diagnostic)

    def acknowledge_baseline(
        self,
        ctx: ControlPlaneContext,
        *,
        schema_baseline_id: str,
        observation_fingerprint: str,
        expected_version: int | None = None,
        submission_id: str | None = None,
    ) -> BaselineAcknowledgement:
        self._require_nonempty(
            schema_baseline_id,
            "schema_baseline_id",
            observation_fingerprint,
            "observation_fingerprint",
        )
        key = (*_scope(ctx), schema_baseline_id)
        with self._lock:
            prior = self._baselines.get(key)
            version = prior.version if prior else None
            if version != expected_version:
                raise ControlPlaneError.conflict(
                    "Baseline acknowledgement compare-and-swap conflict"
                )
            if submission_id and (*_scope(ctx), submission_id) not in self._submissions:
                raise ControlPlaneError.not_found("Submission not found")
            record = BaselineAcknowledgement(
                f"ack-{uuid.uuid4().hex[:16]}",
                *_scope(ctx),
                schema_baseline_id,
                observation_fingerprint,
                (version or 0) + 1,
                _iso(),
                submission_id=submission_id,
            )
            self._baselines[key] = record
            return deepcopy(record)

    def record_effect(
        self, ctx: ControlPlaneContext, effect: EffectRecord
    ) -> EffectRecord:
        return self._record_effect(ctx, effect)

    def record_attempt_effect(
        self,
        ctx: ControlPlaneContext,
        effect: EffectRecord,
        *,
        attempt_id: str,
        owner_id: str,
        fencing_token: int,
    ) -> EffectRecord:
        """Record worker outcome only while its exact attempt still owns a lease."""
        return self._record_effect(
            ctx,
            effect,
            lease_claim=(attempt_id, owner_id, fencing_token),
        )

    def _record_effect(
        self,
        ctx: ControlPlaneContext,
        effect: EffectRecord,
        *,
        lease_claim: tuple[str, str, int] | None = None,
    ) -> EffectRecord:
        if effect.status not in {
            "none",
            "pending",
            "committed",
            "not_committed",
            "failed",
            "unknown",
        }:
            raise ValueError("unsupported external effect status")
        self._require_nonempty(
            effect.effect_id,
            "effect_id",
            effect.submission_id,
            "submission_id",
        )
        if (effect.tenant_id, effect.workspace_id) != _scope(ctx):
            raise ControlPlaneError.not_found("Effect not found")
        metadata = redact_control_plane_payload(deepcopy(dict(effect.metadata)))
        safe_effect = replace(
            effect,
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
            idempotency_evidence=(
                redact_control_plane_text(effect.idempotency_evidence)
                if effect.idempotency_evidence is not None
                else None
            ),
            reconciliation_evidence=(
                redact_control_plane_text(effect.reconciliation_evidence)
                if effect.reconciliation_evidence is not None
                else None
            ),
            publication_evidence=(
                redact_control_plane_text(effect.publication_evidence)
                if effect.publication_evidence is not None
                else None
            ),
            compensation_evidence=(
                redact_control_plane_text(effect.compensation_evidence)
                if effect.compensation_evidence is not None
                else None
            ),
        )
        reconciliation_proven = bool(
            (safe_effect.reconciliation_evidence or "").strip()
        )
        idempotency_proven = bool((safe_effect.idempotency_evidence or "").strip())
        with self._lock:
            submission_key = (*_scope(ctx), safe_effect.submission_id)
            submission = self._submissions.get(submission_key)
            if submission is None:
                raise ControlPlaneError.not_found("Submission not found")
            if lease_claim is not None:
                attempt_id, owner_id, fencing_token = lease_claim
                attempt = self._attempts.get((*_scope(ctx), attempt_id))
                if (
                    attempt is None
                    or attempt.submission_id != safe_effect.submission_id
                    or attempt.status != "running"
                    or attempt.owner_id != owner_id
                    or attempt.fencing_token != fencing_token
                    or submission.status in {"cancelled", "completed", "failed"}
                ):
                    raise ControlPlaneError.conflict(
                        "Execution effect requires the current running attempt"
                    )
                self._require_lease(submission_key, owner_id, fencing_token)
            existing = self._effects.get((*_scope(ctx), safe_effect.effect_id))
            if existing is not None and (
                existing.submission_id != safe_effect.submission_id
            ):
                raise ControlPlaneError.conflict(
                    "External effect submission identity cannot be changed"
                )
            if existing is not None and (
                existing.authoritative != safe_effect.authoritative
            ):
                raise ControlPlaneError.conflict(
                    "External effect authority cannot be changed"
                )
            if (
                existing is not None
                and existing.status == "committed"
                and safe_effect.status != "committed"
            ):
                raise ControlPlaneError.conflict(
                    "Committed external effect cannot be downgraded"
                )
            if (
                existing is not None
                and existing.status == "unknown"
                and (
                    safe_effect.status == "pending"
                    or (
                        safe_effect.status in {"none", "not_committed", "failed"}
                        and not reconciliation_proven
                    )
                    or (
                        safe_effect.status == "committed"
                        and not (reconciliation_proven or idempotency_proven)
                    )
                )
            ):
                raise ControlPlaneError.conflict(
                    "Unknown external effect requires reconciliation evidence"
                )
            self._effects[(*_scope(ctx), safe_effect.effect_id)] = deepcopy(safe_effect)
            return deepcopy(safe_effect)

    def get_effect(self, ctx: ControlPlaneContext, effect_id: str) -> EffectRecord:
        """Read one effect receipt inside the caller's tenant/workspace scope."""
        with self._lock:
            row = self._effects.get((*_scope(ctx), effect_id))
            if row is None:
                raise ControlPlaneError.not_found("Effect not found")
            return deepcopy(row)

    def replay(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> ReplayRecord:
        with self._lock:
            source = self._submissions.get((*_scope(ctx), submission_id))
            if source is None:
                raise ControlPlaneError.not_found("Submission not found")
            differences: list[str] = []
            if checkpoint_id and (*_scope(ctx), checkpoint_id) not in self._checkpoints:
                raise ControlPlaneError.not_found("Checkpoint not found")
            if checkpoint_id:
                checkpoint = self._checkpoints[(*_scope(ctx), checkpoint_id)]
                if checkpoint.submission_id not in {None, submission_id}:
                    raise ControlPlaneError.conflict(
                        "Checkpoint belongs to another submission"
                    )
                if (
                    checkpoint.schema_baseline_id
                    and source.schema_baseline_id
                    and checkpoint.schema_baseline_id != source.schema_baseline_id
                ):
                    differences.append("schema_baseline_id")
            return ReplayRecord(
                f"rep-{uuid.uuid4().hex[:16]}",
                submission_id,
                *_scope(ctx),
                source.plan_fingerprint,
                source.revision_id,
                source.plugin_fingerprint,
                source.policy_fingerprint,
                source.input_snapshot,
                checkpoint_id,
                _iso(),
                differences=tuple(differences),
                schema_observation_fingerprint=source.schema_observation_fingerprint,
                schema_baseline_id=source.schema_baseline_id,
            )

    def plan_resume(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> RepairPlan:
        return self._repair_plan(
            ctx,
            submission_id,
            kind="resume",
            checkpoint_id=checkpoint_id,
            notes=("resume from selected checkpoint",),
        )

    def plan_repair(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        checkpoint_id: str | None = None,
        invalidated_partition_ids: Sequence[str] = (),
        reusable_artifact_ids: Sequence[str] = (),
    ) -> RepairPlan:
        invalidated = tuple(invalidated_partition_ids)
        reusable = tuple(reusable_artifact_ids)
        return self._repair_plan(
            ctx,
            submission_id,
            kind="repair",
            checkpoint_id=checkpoint_id,
            partition_ids=invalidated,
            reusable_artifact_ids=reusable,
            invalidated_partition_ids=invalidated,
            minimum_safe_closure=invalidated,
            notes=("minimum-safe repair closure over invalidated partitions",),
        )

    def plan_backfill(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        partition_ids: Sequence[str],
        checkpoint_id: str | None = None,
    ) -> RepairPlan:
        parts = tuple(partition_ids)
        if not parts:
            raise ValueError("backfill requires partition_ids")
        return self._repair_plan(
            ctx,
            submission_id,
            kind="backfill",
            checkpoint_id=checkpoint_id,
            partition_ids=parts,
            minimum_safe_closure=parts,
            notes=("bounded partition backfill",),
        )

    def _repair_plan(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        kind: str,
        checkpoint_id: str | None,
        partition_ids: tuple[str, ...] = (),
        reusable_artifact_ids: tuple[str, ...] = (),
        invalidated_partition_ids: tuple[str, ...] = (),
        minimum_safe_closure: tuple[str, ...] = (),
        notes: tuple[str, ...] = (),
    ) -> RepairPlan:
        with self._lock:
            source = self._submissions.get((*_scope(ctx), submission_id))
            if source is None:
                raise ControlPlaneError.not_found("Submission not found")
            plan_notes = notes
            if checkpoint_id:
                checkpoint = self._checkpoints.get((*_scope(ctx), checkpoint_id))
                if checkpoint is None:
                    raise ControlPlaneError.not_found("Checkpoint not found")
                if checkpoint.submission_id not in {None, submission_id}:
                    raise ControlPlaneError.conflict(
                        "Checkpoint belongs to another submission",
                        extensions={"reason": "checkpoint_submission_mismatch"},
                    )
                if (
                    checkpoint.schema_baseline_id
                    and source.schema_baseline_id
                    and checkpoint.schema_baseline_id != source.schema_baseline_id
                ):
                    plan_notes = (
                        *notes,
                        "checkpoint schema baseline differs from source submission",
                    )
            return RepairPlan(
                f"rpl-{uuid.uuid4().hex[:16]}",
                kind,  # type: ignore[arg-type]
                submission_id,
                *_scope(ctx),
                _iso(),
                source.plan_fingerprint,
                checkpoint_id=checkpoint_id,
                partition_ids=partition_ids,
                reusable_artifact_ids=reusable_artifact_ids,
                invalidated_partition_ids=invalidated_partition_ids,
                minimum_safe_closure=minimum_safe_closure,
                schema_baseline_id=source.schema_baseline_id,
                notes=plan_notes,
            )

    def create_preview(
        self, ctx: ControlPlaneContext, preview: PreviewWorkspace
    ) -> PreviewWorkspace:
        if (preview.tenant_id, preview.workspace_id) != _scope(
            ctx
        ) or preview.quota < 1:
            raise ControlPlaneError.forbidden(
                "Preview must be scoped and have a positive quota"
            )
        if preview.base_revision_id == preview.candidate_revision_id:
            raise ValueError("Preview candidate must differ from base revision")
        if _parse(preview.expires_at) <= _now():
            raise ValueError("Preview expiry must be in the future")
        with self._lock:
            key = (*_scope(ctx), preview.preview_id)
            existing = self._previews.get(key)
            if existing is not None:
                if existing == preview:
                    return deepcopy(existing)
                raise ControlPlaneError.conflict(
                    "Preview id already exists with different inputs"
                )
            active = sum(
                1
                for (t, w, _), row in self._previews.items()
                if (t, w) == _scope(ctx) and row.cleaned_at is None
            )
            if active >= preview.quota:
                raise ControlPlaneError.conflict("Preview workspace quota exceeded")
            self._previews[key] = deepcopy(preview)
            return deepcopy(preview)

    def mark_preview_stale(
        self,
        ctx: ControlPlaneContext,
        preview_id: str,
        *,
        code_fingerprint: str | None = None,
        plan_fingerprint: str | None = None,
        policy_fingerprint: str | None = None,
        environment_fingerprint: str | None = None,
    ) -> PreviewWorkspace:
        key = (*_scope(ctx), preview_id)
        with self._lock:
            preview = self._previews.get(key)
            if preview is None:
                raise ControlPlaneError.not_found("Preview not found")
            reasons: list[str] = []
            if (
                code_fingerprint is not None
                and code_fingerprint != preview.code_fingerprint
            ):
                reasons.append("code_fingerprint")
            if (
                plan_fingerprint is not None
                and plan_fingerprint != preview.plan_fingerprint
            ):
                reasons.append("plan_fingerprint")
            if (
                policy_fingerprint is not None
                and policy_fingerprint != preview.policy_fingerprint
            ):
                reasons.append("policy_fingerprint")
            if (
                environment_fingerprint is not None
                and environment_fingerprint != preview.environment_fingerprint
            ):
                reasons.append("environment_fingerprint")
            if not reasons:
                return deepcopy(preview)
            updated = replace(preview, stale=True, stale_reason=",".join(reasons))
            self._previews[key] = updated
            return deepcopy(updated)

    def record_preview_diff(
        self, ctx: ControlPlaneContext, diff: DiffRecord
    ) -> DiffRecord:
        if (diff.tenant_id, diff.workspace_id) != _scope(ctx):
            raise ControlPlaneError.not_found("Diff not found")
        with self._lock:
            if (*_scope(ctx), diff.preview_id) not in self._previews:
                raise ControlPlaneError.not_found("Preview not found")
            self._diffs[(*_scope(ctx), diff.diff_id)] = deepcopy(diff)
            return deepcopy(diff)

    def authorize_shadow_run(
        self, ctx: ControlPlaneContext, shadow: ShadowRunRecord
    ) -> ShadowRunRecord:
        if (shadow.tenant_id, shadow.workspace_id) != _scope(ctx):
            raise ControlPlaneError.not_found("Shadow run not found")
        if shadow.production_authority:
            raise ControlPlaneError.forbidden(
                "Shadow runs cannot claim production authority"
            )
        if not shadow.authorized_by.strip():
            raise ValueError("shadow run requires authorized_by")
        with self._lock:
            preview = self._previews.get((*_scope(ctx), shadow.preview_id))
            if preview is None:
                raise ControlPlaneError.not_found("Preview not found")
            if preview.stale:
                raise ControlPlaneError.conflict(
                    "Stale preview cannot authorize shadow"
                )
            if (*_scope(ctx), shadow.submission_id) not in self._submissions:
                raise ControlPlaneError.not_found("Submission not found")
            for effect_id in shadow.effect_ids:
                effect = self._effects.get((*_scope(ctx), effect_id))
                if effect is None:
                    raise ControlPlaneError.not_found("Effect not found")
                if effect.authoritative:
                    raise ControlPlaneError.forbidden(
                        "Shadow effects must be non-authoritative"
                    )
            self._shadows[(*_scope(ctx), shadow.shadow_run_id)] = deepcopy(shadow)
            return deepcopy(shadow)

    def cleanup_expired_previews(
        self, ctx: ControlPlaneContext
    ) -> list[PreviewWorkspace]:
        now = _now()
        cleaned: list[PreviewWorkspace] = []
        with self._lock:
            for key, preview in tuple(self._previews.items()):
                if (
                    key[:2] == _scope(ctx)
                    and preview.cleaned_at is None
                    and _parse(preview.expires_at) <= now
                ):
                    done = replace(preview, cleaned_at=_iso(now))
                    self._previews[key] = done
                    cleaned.append(deepcopy(done))
        return cleaned

    def submission_status(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> str | None:
        """Return the durable submission status, if present."""
        with self._lock:
            row = self._submissions.get((*_scope(ctx), submission_id))
            return row.status if row is not None else None

    def dump(self) -> dict[str, Any]:
        with self._lock:
            return {
                "submissions": {
                    json.dumps(list(key)): row.to_dict()
                    for key, row in self._submissions.items()
                },
                "idempotency": {
                    json.dumps(list(key)): value
                    for key, value in self._idempotency.items()
                },
                "outbox": {
                    json.dumps(list(key)): row.to_dict()
                    for key, row in self._outbox.items()
                },
                "leases": {
                    json.dumps(list(key)): row.to_dict()
                    for key, row in self._leases.items()
                },
                "attempts": {
                    json.dumps(list(key)): row.to_dict()
                    for key, row in self._attempts.items()
                },
                "effects": {
                    json.dumps(list(key)): row.to_dict()
                    for key, row in self._effects.items()
                },
            }

    def load(self, payload: Mapping[str, Any]) -> None:
        def _rows(raw: Mapping[str, Any], cls: type) -> dict[tuple[Any, ...], Any]:
            loaded: dict[tuple[Any, ...], Any] = {}
            for key, value in dict(raw or {}).items():
                fields = {
                    field: data
                    for field, data in dict(value).items()
                    if field != "schema"
                }
                loaded[tuple(json.loads(key))] = cls(**fields)
            return loaded

        with self._lock:
            self._submissions = _rows(
                payload.get("submissions") or {}, SubmissionRecord
            )
            self._idempotency = {
                tuple(json.loads(key)): str(value)
                for key, value in dict(payload.get("idempotency") or {}).items()
            }
            self._outbox = _rows(payload.get("outbox") or {}, OutboxRecord)
            self._leases = _rows(payload.get("leases") or {}, LeaseRecord)
            self._attempts = _rows(payload.get("attempts") or {}, AttemptRecord)
            self._effects = _rows(payload.get("effects") or {}, EffectRecord)


__all__ = ["MemoryDurableWorkStore"]
