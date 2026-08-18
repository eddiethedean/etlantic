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
from typing import Any

from etlantic.control_plane.durable_models import (
    STATE_NAMESPACES,
    AttemptRecord,
    BaselineAcknowledgement,
    CheckpointRecord,
    DiffRecord,
    EffectRecord,
    LeaseRecord,
    OutboxRecord,
    PreviewWorkspace,
    RepairPlan,
    ReplayRecord,
    ShadowRunRecord,
    StateDiagnostic,
    StateTransitionExplanation,
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


_NON_TERMINAL = {"accepted", "dispatched", "cancel_requested"}


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
        self._checkpoints: dict[tuple[str, str, str], CheckpointRecord] = {}
        self._effects: dict[tuple[str, str, str], EffectRecord] = {}
        self._previews: dict[tuple[str, str, str], PreviewWorkspace] = {}
        self._diffs: dict[tuple[str, str, str], DiffRecord] = {}
        self._shadows: dict[tuple[str, str, str], ShadowRunRecord] = {}
        self._baselines: dict[tuple[str, str, str], BaselineAcknowledgement] = {}
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
        idem = (
            *_scope(ctx),
            ctx.principal.issuer or "",
            ctx.principal.kind,
            ctx.principal.subject,
            operation,
            idempotency_key,
        )
        safe_input_snapshot = (
            redact_control_plane_text(input_snapshot)
            if input_snapshot is not None
            else None
        )
        requested = (
            plan_fingerprint,
            revision_id,
            plugin_fingerprint,
            policy_fingerprint,
            safe_input_snapshot,
            schema_observation_fingerprint,
            schema_baseline_id,
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
                )
                if actual != requested:
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with different immutable inputs"
                    )
                if submission_id is not None and submission_id != existing_id:
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with different submission_id"
                    )
                return deepcopy(prior), False
            if self.admission_limit is not None:
                in_flight = sum(
                    1
                    for (t, w, _), row in self._submissions.items()
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
            # Expire any live lease so holders cannot heartbeat forever and
            # block takeover after cancel.
            lease = self._leases.get(key)
            if lease is not None and _parse(lease.expires_at) > _now():
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
            if any(
                attempt.submission_id == submission_id and attempt.status == "running"
                for (tenant, workspace, _), attempt in self._attempts.items()
                if (tenant, workspace) == _scope(ctx)
            ):
                raise ControlPlaneError.conflict(
                    "Submission already has a running attempt"
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
                        and not (
                            safe_effect.reconciliation_evidence
                            or safe_effect.idempotency_evidence
                        )
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
            if checkpoint_id and (*_scope(ctx), checkpoint_id) not in self._checkpoints:
                raise ControlPlaneError.not_found("Checkpoint not found")
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
                notes=notes,
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
            self._submissions = _rows(payload.get("submissions") or {}, SubmissionRecord)
            self._idempotency = {
                tuple(json.loads(key)): str(value)
                for key, value in dict(payload.get("idempotency") or {}).items()
            }
            self._outbox = _rows(payload.get("outbox") or {}, OutboxRecord)
            self._leases = _rows(payload.get("leases") or {}, LeaseRecord)
            self._attempts = _rows(payload.get("attempts") or {}, AttemptRecord)


__all__ = ["MemoryDurableWorkStore"]
