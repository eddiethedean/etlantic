"""Thread-safe CP3 reference store used for conformance and local development.

It models atomic acceptance plus outbox insert under one lock. Production
deployments should use a transactional provider with the same semantics.
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from etlantic.control_plane.durable_models import (
    AttemptRecord,
    CheckpointRecord,
    EffectRecord,
    LeaseRecord,
    OutboxRecord,
    PreviewWorkspace,
    ReplayRecord,
    SubmissionRecord,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.scope_key


class MemoryDurableWorkStore:
    """Fail-closed in-memory implementation of :class:`DurableWorkStore`."""

    def __init__(self) -> None:
        self._submissions: dict[tuple[str, str, str], SubmissionRecord] = {}
        self._idempotency: dict[tuple[str, str, str, str, str, str, str], str] = {}
        self._outbox: dict[tuple[str, str, str], OutboxRecord] = {}
        self._leases: dict[tuple[str, str, str], LeaseRecord] = {}
        self._attempts: dict[tuple[str, str, str], AttemptRecord] = {}
        self._checkpoints: dict[tuple[str, str, str], CheckpointRecord] = {}
        self._effects: dict[tuple[str, str, str], EffectRecord] = {}
        self._previews: dict[tuple[str, str, str], PreviewWorkspace] = {}
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
    ) -> tuple[SubmissionRecord, bool]:
        self._require_nonempty(
            idempotency_key,
            "idempotency_key",
            operation,
            "operation",
            plan_fingerprint,
            "plan_fingerprint",
        )
        idem = (
            *_scope(ctx),
            ctx.principal.issuer or "",
            ctx.principal.kind,
            ctx.principal.subject,
            operation,
            idempotency_key,
        )
        requested = (
            plan_fingerprint,
            revision_id,
            plugin_fingerprint,
            policy_fingerprint,
            input_snapshot,
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
                )
                if actual != requested:
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with different immutable inputs"
                    )
                return deepcopy(prior), False
            submission_id = f"sub-{uuid.uuid4().hex[:16]}"
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
                input_snapshot,
                ctx.principal.issuer,
                ctx.principal.kind,
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

    def pending_outbox(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ) -> list[OutboxRecord]:
        with self._lock:
            return [
                deepcopy(row)
                for (t, w, _), row in self._outbox.items()
                if (t, w) == _scope(ctx) and row.published_at is None
            ][: max(0, limit)]

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
                self._submissions[submission_key] = replace(
                    self._submissions[submission_key], status="dispatched"
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
            old = self._require_lease(key, owner_id, fencing_token)
            now = _now()
            lease = replace(
                old,
                heartbeat_at=_iso(now),
                expires_at=_iso(now + timedelta(seconds=ttl_seconds)),
            )
            self._leases[key] = lease
            return deepcopy(lease)

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
            if any(
                attempt.submission_id == submission_id and attempt.status == "running"
                for (tenant, workspace, _), attempt in self._attempts.items()
                if (tenant, workspace) == _scope(ctx)
            ):
                raise ControlPlaneError.conflict(
                    "Submission already has a running attempt"
                )
            record = AttemptRecord(
                f"att-{uuid.uuid4().hex[:16]}",
                submission_id,
                *_scope(ctx),
                owner_id,
                fencing_token,
                _iso(),
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
            self._require_lease(
                (*_scope(ctx), attempt.submission_id), owner_id, fencing_token
            )
            if attempt.status != "running":
                return deepcopy(attempt)
            result = replace(attempt, status=status, completed_at=_iso())
            self._attempts[key] = result
            submission_key = (*_scope(ctx), attempt.submission_id)
            submission = self._submissions[submission_key]
            terminal_status = "completed" if status == "completed" else "failed"
            if status == "cancelled" or submission.status == "cancel_requested":
                terminal_status = "cancelled"
            self._submissions[submission_key] = replace(
                submission, status=terminal_status
            )
            return deepcopy(result)

    def compare_and_swap_checkpoint(
        self,
        ctx: ControlPlaneContext,
        checkpoint_id: str,
        *,
        expected_version: int | None,
        value_fingerprint: str,
        attempt_id: str | None = None,
        fencing_token: int | None = None,
    ) -> CheckpointRecord:
        key = (*_scope(ctx), checkpoint_id)
        with self._lock:
            previous = self._checkpoints.get(key)
            version = previous.version if previous else None
            if version != expected_version:
                raise ControlPlaneError.conflict("Checkpoint compare-and-swap conflict")
            if attempt_id is not None:
                attempt = self._attempts.get((*_scope(ctx), attempt_id))
                if (
                    attempt is None
                    or attempt.status != "running"
                    or fencing_token is None
                ):
                    raise ControlPlaneError.conflict(
                        "Checkpoint requires a current running attempt and fencing token"
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
                submission_id=attempt.submission_id if attempt_id is not None else None,
                attempt_id=attempt_id,
            )
            self._checkpoints[key] = record
            return deepcopy(record)

    def record_effect(
        self, ctx: ControlPlaneContext, effect: EffectRecord
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
        )
        with self._lock:
            if (*_scope(ctx), safe_effect.submission_id) not in self._submissions:
                raise ControlPlaneError.not_found("Submission not found")
            existing = self._effects.get((*_scope(ctx), safe_effect.effect_id))
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
                    safe_effect.status in {"none", "pending", "not_committed"}
                    or (
                        safe_effect.status == "committed"
                        and not safe_effect.reconciliation_evidence
                    )
                )
            ):
                raise ControlPlaneError.conflict(
                    "Unknown external effect requires reconciliation evidence"
                )
            self._effects[(*_scope(ctx), safe_effect.effect_id)] = deepcopy(safe_effect)
            return deepcopy(safe_effect)

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
            if checkpoint_id and (*_scope(ctx), checkpoint_id) not in self._checkpoints:
                raise ControlPlaneError.not_found("Checkpoint not found")
            if checkpoint_id:
                checkpoint = self._checkpoints[(*_scope(ctx), checkpoint_id)]
                if checkpoint.submission_id not in {None, submission_id}:
                    raise ControlPlaneError.conflict(
                        "Checkpoint belongs to another submission"
                    )
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
            self._previews[(*_scope(ctx), preview.preview_id)] = deepcopy(preview)
            return deepcopy(preview)

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


__all__ = ["MemoryDurableWorkStore"]
