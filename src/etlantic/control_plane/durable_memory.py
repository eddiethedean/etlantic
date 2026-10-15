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
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from etlantic.control_plane.action_jobs import (
    MAX_PREVIEW_RESULT_TTL_SECONDS,
    MIN_PREVIEW_RESULT_TTL_SECONDS,
)
from etlantic.control_plane.durable_models import (
    ACTION_JOB_SCHEMA,
    STATE_NAMESPACES,
    ActionJobRecord,
    ActionJobStatus,
    AttemptRecord,
    BaselineAcknowledgement,
    CheckpointRecord,
    DiffRecord,
    DispatchReconciliation,
    DispatchRecord,
    EffectRecord,
    ExecutionRouteLifecycle,
    ExecutionRouteRecord,
    ExecutionRouteTransition,
    ExecutionRouteWorkload,
    ExecutionScopePage,
    LeaseRecord,
    OutboxRecord,
    PreviewWorkspace,
    RepairPlan,
    RepairPlanKind,
    ReplayRecord,
    ResultPublicationRecord,
    ShadowRunRecord,
    StateDiagnostic,
    StateDiagnosticKind,
    StateTransitionExplanation,
    SubmissionRecord,
    execution_context_from_submission,
    execution_route_backend,
    execution_route_binding,
    validate_execution_route,
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


def _select_remote_run_id(
    remote_run_id: object,
    legacy_prefect_run_id: object,
    *,
    required: bool = True,
) -> str | None:
    """Resolve generic and 0.58 Prefect identity inputs without ambiguity."""
    if remote_run_id is None:
        remote_run_id = legacy_prefect_run_id
    elif legacy_prefect_run_id is not None and remote_run_id != legacy_prefect_run_id:
        raise ValueError("remote_run_id conflicts with prefect_flow_run_id")
    if remote_run_id is None:
        if required:
            raise ValueError("remote_run_id is required")
        return None
    if (
        not isinstance(remote_run_id, str)
        or not remote_run_id.strip()
        or len(remote_run_id) > 256
    ):
        raise ValueError("remote_run_id must contain 1 to 256 characters")
    return remote_run_id


_NON_TERMINAL = {"accepted", "dispatched", "cancel_requested"}
_MAX_DISPATCH_GENERATIONS = 3
_PERSISTED_RECORD_SCHEMAS: dict[str, frozenset[str]] = {
    "SubmissionRecord": frozenset({"etlantic.control_plane.submission_record/1"}),
    "ExecutionRouteTransition": frozenset(
        {"etlantic.control_plane.execution_route_transition/2"}
    ),
    "ExecutionRouteRecord": frozenset({"etlantic.control_plane.execution_route/2"}),
    "OutboxRecord": frozenset({"etlantic.control_plane.outbox_record/1"}),
    "DispatchReconciliation": frozenset(
        {
            "etlantic.control_plane.dispatch_reconciliation/1",
            "etlantic.control_plane.dispatch_reconciliation/2",
            "etlantic.control_plane.dispatch_reconciliation/3",
        }
    ),
    "DispatchRecord": frozenset(
        {
            "etlantic.control_plane.dispatch_record/2",
            "etlantic.control_plane.dispatch_record/3",
            "etlantic.control_plane.dispatch_record/4",
            "etlantic.control_plane.dispatch_record/5",
        }
    ),
    "LeaseRecord": frozenset({"etlantic.control_plane.lease_record/1"}),
    "AttemptRecord": frozenset({"etlantic.control_plane.attempt_record/1"}),
    "ResultPublicationRecord": frozenset(
        {"etlantic.control_plane.result_publication/1"}
    ),
    "CheckpointRecord": frozenset({"etlantic.control_plane.checkpoint_record/1"}),
    "EffectRecord": frozenset({"etlantic.control_plane.effect_record/1"}),
    "PreviewWorkspace": frozenset({"etlantic.control_plane.preview_workspace/1"}),
    "DiffRecord": frozenset({"etlantic.control_plane.diff_record/1"}),
    "ShadowRunRecord": frozenset({"etlantic.control_plane.shadow_run_record/1"}),
    "BaselineAcknowledgement": frozenset(
        {"etlantic.control_plane.baseline_acknowledgement/1"}
    ),
    "ActionJobRecord": frozenset({"etlantic.control_plane.action_job/1"}),
    "StateDiagnostic": frozenset({"etlantic.control_plane.state_diagnostic/1"}),
}


def _snapshot_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("durable snapshot record must be an object")
    raw_fields = cast(Mapping[object, Any], value)
    fields: dict[str, Any] = {}
    for key, data in raw_fields.items():
        if not isinstance(key, str):
            raise ValueError("durable snapshot field names must be strings")
        fields[key] = data
    return fields


def _snapshot_record_fields(value: object, record_type: type[Any]) -> dict[str, Any]:
    fields = _snapshot_mapping(value)
    schema = fields.get("schema")
    known = _PERSISTED_RECORD_SCHEMAS.get(record_type.__name__)
    if schema is not None and (known is None or schema not in known):
        raise ValueError(f"unsupported {record_type.__name__} schema: {schema!r}")
    return {field: data for field, data in fields.items() if field != "schema"}


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

DURABLE_WORK_SNAPSHOT_SCHEMA = "etlantic.control_plane.durable_work_snapshot/1"
_SNAPSHOT_STATE_FIELDS = (
    "_submissions",
    "_idempotency",
    "_outbox",
    "_dispatches",
    "_leases",
    "_attempts",
    "_result_publications",
    "_checkpoints",
    "_effects",
    "_previews",
    "_diffs",
    "_shadows",
    "_baselines",
    "_action_jobs",
    "_action_idempotency",
    "_diagnostics",
    "_execution_route_states",
    "_execution_route_references",
)


def _dispatch_creation_key(
    key: tuple[str, str, str],
    binding_fingerprint: str,
    generation: int,
    backend_kind: str = "prefect",
) -> str:
    # Keep historical Prefect idempotency keys stable. New backend keys carry
    # their kind so equal opaque fingerprints cannot collide across providers.
    parts = [*key, binding_fingerprint, generation]
    if backend_kind != "prefect":
        parts.insert(-2, backend_kind)
    identity = json.dumps(parts, separators=(",", ":"))
    return "etlantic-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


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
        self._dispatches: dict[tuple[str, str, str], DispatchRecord] = {}
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
        self._execution_route_states: dict[str, ExecutionRouteRecord] = {}
        self._execution_route_references: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def iter_submission_records(
        self,
    ) -> tuple[tuple[tuple[str, str, str], SubmissionRecord], ...]:
        """Return a stable snapshot of submission rows for provider adapters."""
        with self._lock:
            return tuple(self._submissions.items())

    def iter_outbox_records(
        self,
    ) -> tuple[tuple[tuple[str, str, str], OutboxRecord], ...]:
        """Return a stable snapshot of outbox rows for provider adapters."""
        with self._lock:
            return tuple(self._outbox.items())

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
        execution_route: str = "local",
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
        validate_execution_route(execution_route)
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
            execution_route,
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
                    prior.execution_route,
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
            route_state = self._execution_route_states.get(
                execution_route, ExecutionRouteRecord(execution_route)
            )
            if route_state.status != "active":
                raise ControlPlaneError.conflict(
                    "Execution route is not accepting new submissions",
                    extensions={
                        "reason": f"execution_route_{route_state.status}",
                        "execution_route": execution_route,
                        "route_revision": route_state.revision,
                    },
                )
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
                execution_route=execution_route,
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

    def get_execution_route_state(
        self, ctx: ControlPlaneContext, execution_route: str
    ) -> ExecutionRouteRecord:
        """Read the store-wide lifecycle of a registered remote execution route."""
        validate_execution_route(execution_route)
        if execution_route == "local":
            raise ValueError("local execution has no remote route lifecycle")
        with self._lock:
            return deepcopy(
                self._execution_route_states.get(
                    execution_route, ExecutionRouteRecord(execution_route)
                )
            )

    def execution_route_workload(
        self, ctx: ControlPlaneContext, execution_route: str
    ) -> ExecutionRouteWorkload:
        """Count store-wide work and evidence that still depends on a route."""
        validate_execution_route(execution_route)
        if execution_route == "local":
            raise ValueError("local execution has no remote route lifecycle")
        with self._lock:
            return self._execution_route_workload_unlocked(execution_route)

    def execution_route_reference_counts(
        self, ctx: ControlPlaneContext, execution_route: str
    ) -> dict[str, int]:
        """Count all canonical history and active schedule reservations."""
        validate_execution_route(execution_route)
        if execution_route == "local":
            raise ValueError("local execution has no remote route lifecycle")
        with self._lock:
            return self._execution_route_reference_counts_unlocked(execution_route)

    def reserve_execution_route_reference(
        self,
        ctx: ControlPlaneContext,
        execution_route: str,
        reference_id: str,
    ) -> None:
        """Fence schedule admission against route cleanup with a durable hold."""
        validate_execution_route(execution_route)
        if execution_route == "local":
            raise ValueError("local execution cannot have remote route references")
        if not reference_id.strip():
            raise ValueError("reference_id must be a non-empty string")
        with self._lock:
            state = self._execution_route_states.get(
                execution_route, ExecutionRouteRecord(execution_route)
            )
            if state.status != "active":
                raise ControlPlaneError.conflict(
                    "Execution route is not accepting new schedule references",
                    extensions={
                        "reason": f"execution_route_{state.status}",
                        "execution_route": execution_route,
                        "route_revision": state.revision,
                    },
                )
            self._execution_route_references.setdefault(execution_route, set()).add(
                reference_id
            )

    def release_execution_route_reference(
        self,
        ctx: ControlPlaneContext,
        execution_route: str,
        reference_id: str,
    ) -> None:
        """Release an existing schedule hold after its record is deleted/moved."""
        validate_execution_route(execution_route)
        if execution_route == "local":
            raise ValueError("local execution cannot have remote route references")
        if not reference_id.strip():
            raise ValueError("reference_id must be a non-empty string")
        with self._lock:
            references = self._execution_route_references.get(execution_route)
            if references is not None:
                references.discard(reference_id)
                if not references:
                    self._execution_route_references.pop(execution_route, None)

    def release_execution_route_reference_id(
        self, ctx: ControlPlaneContext, reference_id: str
    ) -> None:
        """Release one scoped reference after its schedule is confirmed absent."""
        if not reference_id.strip():
            raise ValueError("reference_id must be a non-empty string")
        with self._lock:
            for route, references in tuple(self._execution_route_references.items()):
                references.discard(reference_id)
                if not references:
                    self._execution_route_references.pop(route, None)

    def transition_execution_route_state(
        self,
        ctx: ControlPlaneContext,
        execution_route: str,
        *,
        expected_revision: int,
        status: ExecutionRouteLifecycle,
        now: datetime | None = None,
    ) -> ExecutionRouteRecord:
        """CAS a route lifecycle and refuse retirement while durable work remains."""
        validate_execution_route(execution_route)
        if execution_route == "local":
            raise ValueError("local execution has no remote route lifecycle")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision must be a non-negative integer")
        if status not in {
            "active",
            "draining",
            "retired",
            "cleanup_pending",
            "cleaned",
        }:
            raise ValueError("unsupported execution route lifecycle state")
        with self._lock:
            prior = self._execution_route_states.get(
                execution_route, ExecutionRouteRecord(execution_route)
            )
            if prior.revision != expected_revision:
                raise ControlPlaneError.conflict(
                    "Execution route lifecycle revision is stale",
                    extensions={"reason": "stale_route_revision"},
                )
            allowed = {
                ("active", "draining"),
                ("draining", "active"),
                ("draining", "retired"),
                ("retired", "active"),
                ("retired", "cleanup_pending"),
                ("cleanup_pending", "cleaned"),
            }
            if status == prior.status:
                return deepcopy(prior)
            if (prior.status, status) not in allowed:
                raise ControlPlaneError.conflict(
                    "Execution route lifecycle transition is invalid",
                    extensions={"reason": "invalid_route_transition"},
                )
            if status == "retired":
                workload = self._execution_route_workload_unlocked(execution_route)
                if not workload.drained:
                    raise ControlPlaneError.conflict(
                        "Execution route still owns durable work or publication evidence",
                        extensions={
                            "reason": "execution_route_not_drained",
                            "workload": workload.to_dict(),
                        },
                    )
                references = self._execution_route_reference_counts_unlocked(
                    execution_route
                )
                if references["schedule_reservations"]:
                    raise ControlPlaneError.conflict(
                        "Execution route still has scheduled references",
                        extensions={
                            "reason": "execution_route_referenced",
                            "references": references,
                        },
                    )
            if status == "cleanup_pending":
                workload = self._execution_route_workload_unlocked(execution_route)
                references = self._execution_route_reference_counts_unlocked(
                    execution_route
                )
                if not workload.drained or any(references.values()):
                    raise ControlPlaneError.conflict(
                        "Execution route still has work or durable references",
                        extensions={
                            "reason": "execution_route_referenced",
                            "workload": workload.to_dict(),
                            "references": references,
                        },
                    )
            current = now or _now()
            updated = ExecutionRouteRecord(
                execution_route=execution_route,
                status=status,
                revision=prior.revision + 1,
                changed_at=_iso(current),
                history=(
                    *prior.history,
                    ExecutionRouteTransition(
                        revision=prior.revision + 1,
                        from_status=prior.status,
                        to_status=status,
                        changed_at=_iso(current),
                        principal_subject=ctx.principal.subject,
                        principal_issuer=ctx.principal.issuer,
                    ),
                )[-64:],
            )
            self._execution_route_states[execution_route] = updated
            return deepcopy(updated)

    def _execution_route_reference_counts_unlocked(
        self, execution_route: str
    ) -> dict[str, int]:
        return {
            "canonical_submissions": sum(
                row.execution_route == execution_route
                for row in self._submissions.values()
            ),
            "schedule_reservations": len(
                self._execution_route_references.get(execution_route, set())
            ),
        }

    def _execution_route_workload_unlocked(
        self, execution_route: str
    ) -> ExecutionRouteWorkload:
        submissions = {
            key: row
            for key, row in self._submissions.items()
            if row.execution_route == execution_route
        }
        keys = set(submissions)
        return ExecutionRouteWorkload(
            execution_route=execution_route,
            active_submissions=sum(
                row.status in {"accepted", "dispatched", "cancel_requested"}
                for row in submissions.values()
            ),
            active_attempts=sum(
                attempt.status == "running"
                for key, attempt in self._attempts.items()
                if (*key[:2], attempt.submission_id) in keys
            ),
            incomplete_dispatches=sum(
                dispatch.status not in {"dispatched", "cancelled"}
                for key, dispatch in self._dispatches.items()
                if key in keys
            ),
            unresolved_effects=sum(
                effect.status in {"pending", "unknown"}
                for key, effect in self._effects.items()
                if (*key[:2], effect.submission_id) in keys
            ),
            pending_publications=sum(
                record.published_at is None
                for key, record in self._result_publications.items()
                if (*key[:2], record.submission_id) in keys
            ),
            unpublished_outboxes=sum(
                outbox.published_at is None
                for key, outbox in self._outbox.items()
                if (*key[:2], outbox.submission_id) in keys
            ),
        )

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
        self,
        ctx: ControlPlaneContext,
        *,
        limit: int = 100,
        include_terminal: bool = False,
        terminal_only: bool = False,
        submission_id: str | None = None,
        execution_route: str | None = "local",
    ) -> list[OutboxRecord]:
        if execution_route is not None:
            validate_execution_route(execution_route)
        with self._lock:
            return [
                deepcopy(row)
                for (t, w, _), row in self._outbox.items()
                if (t, w) == _scope(ctx)
                and (submission_id is None or row.submission_id == submission_id)
                and row.published_at is None
                and self._submissions.get((t, w, row.submission_id)) is not None
                and (
                    execution_route is None
                    or self._submissions[(t, w, row.submission_id)].execution_route
                    == execution_route
                )
                and (
                    self._submissions[(t, w, row.submission_id)].status
                    in {"cancelled", "completed", "failed"}
                    if terminal_only
                    else include_terminal
                    or self._submissions[(t, w, row.submission_id)].status
                    not in {"cancelled", "completed", "failed"}
                )
            ][: max(0, limit)]

    def pending_dispatches(
        self,
        ctx: ControlPlaneContext,
        *,
        execution_route: str,
        limit: int = 100,
    ) -> list[OutboxRecord]:
        """List bounded accepted work needing remote delivery or recovery."""
        validate_execution_route(execution_route)
        backend_kind = execution_route_backend(execution_route)
        if backend_kind == "local":
            raise ValueError("dispatch polling requires a remote execution route")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        now = _now()
        with self._lock:
            candidates = sorted(
                (
                    row
                    for (tenant_id, workspace_id, _), row in self._outbox.items()
                    if (tenant_id, workspace_id) == _scope(ctx)
                    and row.published_at is None
                ),
                key=lambda row: (row.created_at, row.outbox_id),
            )
            ready: list[OutboxRecord] = []
            for row in candidates:
                submission = self._submissions.get((*_scope(ctx), row.submission_id))
                if (
                    submission is None
                    or submission.execution_route != execution_route
                    or submission.status in {"completed", "failed"}
                ):
                    continue
                dispatch = self._dispatches.get((*_scope(ctx), row.submission_id))
                cancellation_recovery = dispatch is not None and dispatch.status in {
                    "uncertain",
                    "leased",
                }
                if submission.status in {"cancel_requested", "cancelled"} and not (
                    cancellation_recovery
                ):
                    continue
                if dispatch is not None and dispatch.status in {
                    "dispatched",
                    "cancelled",
                    "reconciliation_required",
                }:
                    continue
                if (
                    dispatch is not None
                    and dispatch.retry_after_at is not None
                    and _parse(dispatch.retry_after_at) > now
                ):
                    continue
                if (
                    dispatch is not None
                    and dispatch.status == "leased"
                    and dispatch.lease_expires_at is not None
                    and _parse(dispatch.lease_expires_at) > now
                ):
                    continue
                ready.append(deepcopy(row))
                if len(ready) >= limit:
                    break
            return ready

    def dispatched_for_reconciliation(
        self,
        ctx: ControlPlaneContext,
        *,
        execution_route: str,
        limit: int = 100,
        after_submission_id: str | None = None,
    ) -> list[DispatchRecord]:
        """Return a bounded route-scoped page of linked dispatches."""
        validate_execution_route(execution_route)
        backend_kind = execution_route_backend(execution_route)
        if backend_kind == "local":
            raise ValueError("dispatch reconciliation requires a remote route")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        scope = _scope(ctx)
        with self._lock:
            rows = [
                record
                for key, record in self._dispatches.items()
                if key[:2] == scope
                and record.execution_route == execution_route
                and record.backend_kind == backend_kind
                and record.status == "dispatched"
                and record.remote_run_id is not None
                and (
                    after_submission_id is None
                    or record.submission_id > after_submission_id
                )
                and (submission := self._submissions.get(key)) is not None
                and submission.status in {"accepted", "cancel_requested"}
            ]
            rows.sort(key=lambda item: item.submission_id)
            return deepcopy(rows[:limit])

    def prepare_dispatch(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> DispatchRecord:
        """Persist the immutable dispatch identity before any remote create."""
        with self._lock:
            key = (*_scope(ctx), submission_id)
            submission = self._submissions.get(key)
            if submission is None:
                raise ControlPlaneError.not_found("Submission not found")
            route = validate_execution_route(submission.execution_route)
            backend_kind = execution_route_backend(route)
            if backend_kind == "local":
                raise ControlPlaneError.conflict(
                    "Submission is not assigned to a remote execution route"
                )
            if not submission.input_snapshot:
                raise ControlPlaneError.conflict(
                    "Remote dispatch requires an immutable execution envelope"
                )
            from etlantic.control_plane.execution_envelope import ExecutionEnvelope
            from etlantic.plan.model import PLAN_SCHEMA

            envelope = ExecutionEnvelope.from_json(submission.input_snapshot)
            if (
                envelope.plan_fingerprint != submission.plan_fingerprint
                or envelope.plan_document.get("schema") != PLAN_SCHEMA
            ):
                raise ControlPlaneError.conflict(
                    "Submission envelope is unsupported for managed dispatch"
                )
            binding = execution_route_binding(route)
            assert binding is not None
            digest = hashlib.sha256(
                submission.input_snapshot.encode("utf-8")
            ).hexdigest()
            existing = self._dispatches.get(key)
            generation = existing.generation if existing is not None else 1
            creation_key = _dispatch_creation_key(
                key, binding, generation, backend_kind
            )
            if existing is not None:
                if (
                    existing.execution_route != route
                    or existing.binding_fingerprint != binding
                    or existing.plan_fingerprint != submission.plan_fingerprint
                    or existing.envelope_sha256 != digest
                    or existing.generation != generation
                    or existing.creation_key != creation_key
                ):
                    raise ControlPlaneError.conflict(
                        "Accepted dispatch identity conflicts with its durable record"
                    )
                return deepcopy(existing)
            status = (
                "cancelled"
                if submission.status
                in {"cancel_requested", "cancelled", "completed", "failed"}
                else "pending"
            )
            now = _iso()
            record = DispatchRecord(
                submission_id=submission_id,
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                execution_route=route,
                binding_fingerprint=binding,
                plan_fingerprint=submission.plan_fingerprint,
                envelope_sha256=digest,
                generation=generation,
                creation_key=creation_key,
                created_at=now,
                updated_at=now,
                status=status,
                backend_kind=backend_kind,
            )
            self._dispatches[key] = record
            return deepcopy(record)

    def get_dispatch(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> DispatchRecord:
        with self._lock:
            record = self._dispatches.get((*_scope(ctx), submission_id))
            if record is None:
                raise ControlPlaneError.not_found("Dispatch record not found")
            return deepcopy(record)

    def claim_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        lease_seconds: int = 30,
        now: datetime | None = None,
    ) -> DispatchRecord | None:
        if not owner_id.strip() or len(owner_id) > 256:
            raise ValueError("owner_id must contain 1 to 256 characters")
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 600:
            raise ValueError("lease_seconds must be between 1 and 600")
        current = now or _now()
        key = (*_scope(ctx), submission_id)
        with self._lock:
            record = self._dispatches.get(key)
            submission = self._submissions.get(key)
            if record is None or submission is None:
                raise ControlPlaneError.not_found("Dispatch candidate not found")
            if record.status in {
                "dispatched",
                "cancelled",
                "reconciliation_required",
            }:
                return None
            if (
                record.retry_after_at is not None
                and _parse(record.retry_after_at) > current
            ):
                return None
            cancellation_recovery = record.status in {
                "uncertain",
                "leased",
            } and submission.status in {"cancel_requested", "cancelled"}
            if (
                submission.status
                in {
                    "cancel_requested",
                    "cancelled",
                    "completed",
                    "failed",
                }
                and not cancellation_recovery
            ):
                return None
            if (
                record.status == "leased"
                and record.lease_expires_at is not None
                and _parse(record.lease_expires_at) > current
            ):
                return None
            claimed = replace(
                record,
                status="leased",
                creation_started_at=(
                    record.creation_started_at
                    or (_iso(current) if record.backend_kind == "ecs" else None)
                ),
                dispatch_attempts=record.dispatch_attempts + 1,
                lease_owner_id=owner_id,
                lease_fencing_token=record.lease_fencing_token + 1,
                lease_expires_at=_iso(current + timedelta(seconds=lease_seconds)),
                updated_at=_iso(current),
            )
            self._dispatches[key] = claimed
            return deepcopy(claimed)

    def link_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        remote_run_id: str | None = None,
        prefect_flow_run_id: str | None = None,
        now: datetime | None = None,
    ) -> DispatchRecord:
        if prefect_flow_run_id is not None:
            with self._lock:
                candidate = self._dispatches.get((*_scope(ctx), submission_id))
            if candidate is not None and candidate.backend_kind != "prefect":
                raise ValueError("Prefect run ID alias is only valid for Prefect")
        selected_remote_run_id = _select_remote_run_id(
            remote_run_id, prefect_flow_run_id
        )
        assert selected_remote_run_id is not None
        current = now or _now()
        key = (*_scope(ctx), submission_id)
        with self._lock:
            record = self._dispatches.get(key)
            if record is None:
                raise ControlPlaneError.not_found("Dispatch record not found")
            if record.status == "dispatched":
                if record.remote_run_id == selected_remote_run_id:
                    return deepcopy(record)
                raise ControlPlaneError.conflict(
                    "Dispatch is already linked to a different remote run"
                )
            if (
                record.status != "leased"
                or record.lease_owner_id != owner_id
                or record.lease_fencing_token != fencing_token
                or record.lease_expires_at is None
                or _parse(record.lease_expires_at) <= current
            ):
                raise ControlPlaneError.conflict("Dispatch lease was lost")
            linked = replace(
                record,
                status="dispatched",
                remote_run_id=selected_remote_run_id,
                prefect_flow_run_id=(
                    selected_remote_run_id if record.backend_kind == "prefect" else None
                ),
                lease_owner_id=None,
                lease_expires_at=None,
                retry_after_at=None,
                last_error_code=None,
                updated_at=_iso(current),
            )
            self._dispatches[key] = linked
            return deepcopy(linked)

    def release_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        outcome_uncertain: bool,
        cancelled: bool = False,
        error_code: str | None = None,
        now: datetime | None = None,
    ) -> DispatchRecord:
        if error_code is not None and (
            len(error_code) > 64
            or not all(
                char.islower() or char.isdigit() or char == "_" for char in error_code
            )
        ):
            raise ValueError("error_code must be a bounded lowercase diagnostic token")
        current = now or _now()
        key = (*_scope(ctx), submission_id)
        with self._lock:
            record = self._dispatches.get(key)
            if record is None:
                raise ControlPlaneError.not_found("Dispatch record not found")
            if record.status == "dispatched":
                return deepcopy(record)
            if (
                record.status != "leased"
                or record.lease_owner_id != owner_id
                or record.lease_fencing_token != fencing_token
            ):
                raise ControlPlaneError.conflict("Dispatch lease was lost")
            released = replace(
                record,
                status=(
                    "cancelled"
                    if cancelled
                    else "uncertain"
                    if outcome_uncertain
                    else "pending"
                ),
                lease_owner_id=None,
                lease_expires_at=None,
                retry_after_at=(
                    None
                    if cancelled
                    else _iso(
                        current
                        + timedelta(
                            seconds=min(
                                300,
                                2 ** min(record.dispatch_attempts, 9),
                            )
                        )
                    )
                ),
                last_error_code=error_code,
                updated_at=_iso(current),
            )
            self._dispatches[key] = released
            return deepcopy(released)

    def quarantine_expired_ecs_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_generation: int,
        expected_creation_started_at: str | None,
        safe_retry_deadline: datetime,
        now: datetime | None = None,
    ) -> DispatchRecord:
        """Stop automatic ECS retries after the idempotency safety window."""
        current = now or _now()
        key = (*_scope(ctx), submission_id)
        with self._lock:
            record = self._dispatches.get(key)
            submission = self._submissions.get(key)
            if record is None or submission is None:
                raise ControlPlaneError.not_found("Dispatch record not found")
            if (
                record.backend_kind != "ecs"
                or record.generation != expected_generation
                or record.creation_started_at != expected_creation_started_at
                or record.status not in {"uncertain", "leased"}
                or record.remote_run_id is not None
                or submission.status != "accepted"
            ):
                raise ControlPlaneError.conflict(
                    "ECS dispatch changed before its retry window expired"
                )
            if (
                record.lease_expires_at is not None
                and _parse(record.lease_expires_at) > current
            ):
                raise ControlPlaneError.conflict("ECS dispatch lease is still active")
            if current < safe_retry_deadline:
                raise ControlPlaneError.conflict(
                    "ECS dispatch retry window has not expired"
                )
            quarantined = replace(
                record,
                status="reconciliation_required",
                lease_owner_id=None,
                lease_expires_at=None,
                retry_after_at=None,
                last_error_code="ecs_token_window_expired",
                updated_at=_iso(current),
            )
            self._dispatches[key] = quarantined
            return deepcopy(quarantined)

    def confirm_dispatch_cancelled(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_generation: int,
        expected_remote_run_id: str,
        now: datetime | None = None,
    ) -> DispatchRecord:
        """Mark a linked remote task cancelled after its stopped state is observed."""
        current = now or _now()
        key = (*_scope(ctx), submission_id)
        with self._lock:
            record = self._dispatches.get(key)
            submission = self._submissions.get(key)
            if record is None or submission is None:
                raise ControlPlaneError.not_found("Dispatch record not found")
            if (
                record.status != "dispatched"
                or record.generation != expected_generation
                or record.remote_run_id != expected_remote_run_id
                or submission.status != "cancel_requested"
            ):
                raise ControlPlaneError.conflict(
                    "Dispatch changed before remote cancellation was confirmed"
                )
            cancelled = replace(
                record,
                status="cancelled",
                retry_after_at=None,
                last_error_code="remote_task_stopped_after_cancel",
                updated_at=_iso(current),
            )
            self._dispatches[key] = cancelled
            return deepcopy(cancelled)

    def rearm_dispatch_after_remote_failure(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_remote_run_id: str | None = None,
        expected_flow_run_id: str | None = None,
        now: datetime | None = None,
    ) -> DispatchRecord | None:
        """Retry only a terminal remote failure proven to predate ETL execution."""
        selected_remote_run_id = _select_remote_run_id(
            expected_remote_run_id, expected_flow_run_id
        )
        assert selected_remote_run_id is not None
        return self._rearm_dispatch_if_unclaimed(
            ctx,
            submission_id,
            expected_remote_run_id=selected_remote_run_id,
            reason_code="remote_failed_before_claim",
            now=now,
        )

    def rearm_dispatch_after_remote_missing(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_remote_run_id: str | None = None,
        expected_flow_run_id: str | None = None,
        minimum_age_seconds: int = 300,
        now: datetime | None = None,
    ) -> DispatchRecord | None:
        """Rearm an aged missing run only if ETL execution never acquired work."""
        if (
            type(minimum_age_seconds) is not int
            or not 30 <= minimum_age_seconds <= 86_400
        ):
            raise ValueError("minimum_age_seconds must be between 30 and 86400")
        selected_remote_run_id = _select_remote_run_id(
            expected_remote_run_id, expected_flow_run_id
        )
        assert selected_remote_run_id is not None
        return self._rearm_dispatch_if_unclaimed(
            ctx,
            submission_id,
            expected_remote_run_id=selected_remote_run_id,
            reason_code="remote_missing_before_claim",
            minimum_age_seconds=minimum_age_seconds,
            now=now,
        )

    def _rearm_dispatch_if_unclaimed(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_remote_run_id: str,
        reason_code: str,
        minimum_age_seconds: int = 0,
        now: datetime | None = None,
    ) -> DispatchRecord | None:
        """Create a bounded generation only while no ETL effect could exist."""
        expected_remote_run_id = cast(
            str,
            _select_remote_run_id(expected_remote_run_id, None),
        )
        current = now or _now()
        wall_now = _now()
        key = (*_scope(ctx), submission_id)
        with self._lock:
            record = self._dispatches.get(key)
            submission = self._submissions.get(key)
            lease = self._leases.get(key)
            if (
                record is None
                or submission is None
                or record.status != "dispatched"
                or record.remote_run_id != expected_remote_run_id
                or submission.status != "accepted"
                or (
                    minimum_age_seconds > 0
                    and _parse(record.updated_at)
                    > current - timedelta(seconds=minimum_age_seconds)
                )
                or (lease is not None and _parse(lease.expires_at) > wall_now)
                or any(
                    attempt.submission_id == submission_id
                    and (attempt.tenant_id, attempt.workspace_id) == _scope(ctx)
                    for attempt in self._attempts.values()
                )
                or any(
                    effect.submission_id == submission_id
                    and (effect.tenant_id, effect.workspace_id) == _scope(ctx)
                    for effect in self._effects.values()
                )
                or any(
                    publication.submission_id == submission_id
                    and (publication.tenant_id, publication.workspace_id) == _scope(ctx)
                    for publication in self._result_publications.values()
                )
            ):
                return None
            if record.generation >= _MAX_DISPATCH_GENERATIONS:
                reconciliation_required = replace(
                    record,
                    status="reconciliation_required",
                    retry_after_at=None,
                    last_error_code="dispatch_generation_exhausted",
                    updated_at=_iso(current),
                )
                self._dispatches[key] = reconciliation_required
                return deepcopy(reconciliation_required)
            generation = record.generation + 1
            rearmed = replace(
                record,
                generation=generation,
                creation_key=_dispatch_creation_key(
                    key,
                    record.binding_fingerprint,
                    generation,
                    record.backend_kind,
                ),
                status="pending",
                creation_started_at=None,
                prefect_flow_run_id=None,
                remote_run_id=None,
                retry_after_at=None,
                last_error_code=reason_code,
                updated_at=_iso(current),
            )
            self._dispatches[key] = rearmed
            return deepcopy(rearmed)

    def rearm_reconciliation_required_dispatch(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        expected_generation: int,
        expected_remote_run_id: str | None = None,
        expected_flow_run_id: str | None = None,
        evidence_sha256: str,
        now: datetime | None = None,
    ) -> DispatchRecord:
        """Record explicit operator approval for one exhausted pre-claim retry."""
        if type(expected_generation) is not int or expected_generation < 1:
            raise ValueError("expected_generation must be a positive integer")
        if (
            expected_remote_run_id is not None
            and expected_flow_run_id is not None
            and expected_remote_run_id != expected_flow_run_id
        ):
            raise ValueError("remote run identity inputs do not match")
        selected_remote_run_id = expected_remote_run_id or expected_flow_run_id
        if len(evidence_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in evidence_sha256
        ):
            raise ValueError("evidence_sha256 must be a lowercase SHA-256 digest")
        current = now or _now()
        key = (*_scope(ctx), submission_id)
        with self._lock:
            record = self._dispatches.get(key)
            submission = self._submissions.get(key)
            if record is None or submission is None:
                raise ControlPlaneError.not_found("Dispatch record not found")
            if (
                record.status != "reconciliation_required"
                or record.generation != expected_generation
                or record.remote_run_id != selected_remote_run_id
                or (
                    selected_remote_run_id is None
                    and (
                        record.backend_kind != "ecs" or record.remote_run_id is not None
                    )
                )
                or submission.status != "accepted"
            ):
                raise ControlPlaneError.conflict(
                    "Dispatch no longer matches the reconciled generation",
                    extensions={"reason": "stale_dispatch_reconciliation"},
                )
            route_state = self._execution_route_states.get(
                record.execution_route, ExecutionRouteRecord(record.execution_route)
            )
            if route_state.status != "active":
                raise ControlPlaneError.conflict(
                    "Execution route must be active before dispatch reconciliation",
                    extensions={"reason": "execution_route_not_active"},
                )
            lease = self._leases.get(key)
            if lease is not None and _parse(lease.expires_at) > current:
                raise ControlPlaneError.conflict(
                    "Dispatch cannot be reconciled while an execution lease is active",
                    extensions={"reason": "execution_lease_active"},
                )
            if (
                any(
                    attempt.submission_id == submission_id
                    and (attempt.tenant_id, attempt.workspace_id) == _scope(ctx)
                    for attempt in self._attempts.values()
                )
                or any(
                    effect.submission_id == submission_id
                    and (effect.tenant_id, effect.workspace_id) == _scope(ctx)
                    for effect in self._effects.values()
                )
                or any(
                    publication.submission_id == submission_id
                    and (publication.tenant_id, publication.workspace_id) == _scope(ctx)
                    for publication in self._result_publications.values()
                )
            ):
                raise ControlPlaneError.conflict(
                    "Dispatch cannot be reconciled after canonical execution began",
                    extensions={"reason": "canonical_execution_started"},
                )
            generation = record.generation + 1
            audit = DispatchReconciliation(
                from_generation=record.generation,
                to_generation=generation,
                prefect_flow_run_id=(
                    selected_remote_run_id if record.backend_kind == "prefect" else None
                ),
                backend_kind=record.backend_kind,
                remote_run_id=selected_remote_run_id,
                authorized_at=_iso(current),
                principal_subject=ctx.principal.subject,
                principal_issuer=ctx.principal.issuer,
                evidence_sha256=evidence_sha256,
            )
            rearmed = replace(
                record,
                generation=generation,
                creation_key=_dispatch_creation_key(
                    key,
                    record.binding_fingerprint,
                    generation,
                    record.backend_kind,
                ),
                status="pending",
                creation_started_at=None,
                prefect_flow_run_id=None,
                remote_run_id=None,
                retry_after_at=None,
                last_error_code="operator_reconciled_preclaim",
                updated_at=_iso(current),
                reconciliation_history=(*record.reconciliation_history, audit)[-64:],
            )
            self._dispatches[key] = rearmed
            return deepcopy(rearmed)

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
        self,
        ctx: ControlPlaneContext,
        *,
        limit: int = 100,
        acknowledge_outbox: bool = True,
        submission_id: str | None = None,
        execution_route: str | None = None,
    ) -> list[SubmissionRecord]:
        """Finalize cancellation requests after their worker lease expires."""
        if submission_id is not None and not submission_id.strip():
            raise ValueError("submission_id must be a non-empty identifier")
        if execution_route is not None:
            validate_execution_route(execution_route)
        reconciled: list[SubmissionRecord] = []
        now = _now()
        with self._lock:
            candidates = sorted(
                (
                    (key, row)
                    for key, row in self._submissions.items()
                    if key[:2] == _scope(ctx)
                    and row.status == "cancel_requested"
                    and (submission_id is None or row.submission_id == submission_id)
                    and (
                        execution_route is None
                        or row.execution_route == execution_route
                    )
                ),
                key=lambda item: (item[1].created_at, item[1].submission_id),
            )
            for key, submission in candidates:
                if len(reconciled) >= max(0, limit):
                    break
                lease = self._leases.get(key)
                if lease is not None and _parse(lease.expires_at) > now:
                    continue
                dispatch = self._dispatches.get(key)
                if (
                    dispatch is not None
                    and dispatch.status == "uncertain"
                    and dispatch.prefect_flow_run_id is None
                ):
                    # A remote create may have succeeded even though its
                    # response was lost. Keep the canonical cancellation
                    # discoverable until the dispatcher resolves that identity.
                    continue
                if (
                    dispatch is not None
                    and dispatch.status == "dispatched"
                    and dispatch.backend_kind == "ecs"
                ):
                    # ECS cancellation is final only after the dispatcher has
                    # observed STOPPED and fenced the linked dispatch.
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
                if dispatch is not None and dispatch.status in {
                    "pending",
                    "reconciliation_required",
                }:
                    self._dispatches[key] = replace(
                        dispatch,
                        status="cancelled",
                        retry_after_at=None,
                        last_error_code=(
                            "cancelled_before_dispatch"
                            if dispatch.status == "pending"
                            else "cancelled_after_dispatch_exhaustion"
                        ),
                        updated_at=_iso(now),
                    )
                if acknowledge_outbox:
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
        owner_id = ctx.resource_owner_id or ctx.principal.identity_key
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
        owner_id = ctx.resource_owner_id or ctx.principal.identity_key
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
        owner_id = ctx.resource_owner_id or ctx.principal.identity_key
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
        owner_id = ctx.resource_owner_id or ctx.principal.identity_key
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
        owner_id = ctx.resource_owner_id or ctx.principal.identity_key
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
            if previous is not None and previous.submission_id not in {
                None,
                attempt.submission_id,
            }:
                raise ControlPlaneError.conflict(
                    "Checkpoint belongs to another submission"
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
        kind: StateDiagnosticKind = "corruption",
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
                kind,
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
        kind: RepairPlanKind,
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
                kind,
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
                "dispatches": {
                    json.dumps(list(key)): row.to_dict()
                    for key, row in self._dispatches.items()
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
                "execution_route_states": {
                    route: row.to_dict()
                    for route, row in self._execution_route_states.items()
                },
                "execution_route_references": {
                    route: sorted(references)
                    for route, references in self._execution_route_references.items()
                },
            }

    def _load_legacy_unchecked(self, payload: Mapping[str, Any]) -> None:
        def _typed_records(raw: Sequence[Any], cls: type) -> tuple[Any, ...]:
            records: list[Any] = []
            for item in raw or ():
                if isinstance(item, cls):
                    records.append(item)
                elif cls is DispatchReconciliation and isinstance(item, Mapping):
                    records.append(
                        DispatchReconciliation.from_dict(
                            _snapshot_mapping(cast(object, item))
                        )
                    )
                else:
                    records.append(
                        cls(**_snapshot_record_fields(cast(object, item), cls))
                    )
            return tuple(records)

        def _rows(raw: Mapping[str, Any], cls: type) -> dict[tuple[Any, ...], Any]:
            loaded: dict[tuple[Any, ...], Any] = {}
            for key, value in dict(raw or {}).items():
                fields = _snapshot_record_fields(cast(object, value), cls)
                if cls is DispatchRecord:
                    record = DispatchRecord.from_dict(value)
                elif cls is ExecutionRouteRecord:
                    fields["history"] = _typed_records(
                        fields.get("history", ()), ExecutionRouteTransition
                    )
                    record = cls(**fields)
                else:
                    record = cls(**fields)
                loaded[tuple(json.loads(key))] = record
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
            self._dispatches = _rows(payload.get("dispatches") or {}, DispatchRecord)
            self._leases = _rows(payload.get("leases") or {}, LeaseRecord)
            self._attempts = _rows(payload.get("attempts") or {}, AttemptRecord)
            self._effects = _rows(payload.get("effects") or {}, EffectRecord)
            route_states: dict[str, ExecutionRouteRecord] = {}
            for route, value in dict(
                payload.get("execution_route_states") or {}
            ).items():
                validate_execution_route(route)
                fields = _snapshot_record_fields(
                    cast(object, value), ExecutionRouteRecord
                )
                if fields.get("execution_route") != route:
                    raise ValueError(
                        "execution route snapshot key does not match its record"
                    )
                fields["history"] = _typed_records(
                    fields.get("history", ()), ExecutionRouteTransition
                )
                route_states[route] = ExecutionRouteRecord(**fields)
            self._execution_route_states = route_states

            route_references: dict[str, set[str]] = {}
            for route, raw_references in dict(
                payload.get("execution_route_references") or {}
            ).items():
                validate_execution_route(route)
                if not isinstance(raw_references, Sequence) or isinstance(
                    raw_references, (str, bytes)
                ):
                    raise ValueError("execution route references must be a sequence")
                references: set[str] = set()
                for reference in cast(Sequence[object], raw_references):
                    if not isinstance(reference, str) or not reference.strip():
                        raise ValueError(
                            "execution route references must be non-empty strings"
                        )
                    references.add(reference)
                if references:
                    route_references[route] = references
            self._execution_route_references = route_references

    def to_snapshot(self) -> dict[str, Any]:
        """Export the complete durable-work state in a versioned data format.

        This is the public codec boundary for persistence adapters. The older
        ``dump`` shape remains available for compatibility with local tooling.
        """
        with self._lock:
            data = self.dump()
            data["admission_limit"] = self.admission_limit
            data["action_jobs"] = {
                json.dumps(list(key)): {
                    "schema": ACTION_JOB_SCHEMA,
                    **asdict(record),
                }
                for key, record in self._action_jobs.items()
            }
            data["action_idempotency"] = {
                json.dumps(list(key)): value
                for key, value in self._action_idempotency.items()
            }
            data["result_publications"] = {
                json.dumps(list(key)): record.to_dict()
                for key, record in self._result_publications.items()
            }
            data["checkpoints"] = {
                json.dumps(list(key)): record.to_dict()
                for key, record in self._checkpoints.items()
            }
            data["previews"] = {
                json.dumps(list(key)): record.to_dict()
                for key, record in self._previews.items()
            }
            data["diffs"] = {
                json.dumps(list(key)): record.to_dict()
                for key, record in self._diffs.items()
            }
            data["shadows"] = {
                json.dumps(list(key)): record.to_dict()
                for key, record in self._shadows.items()
            }
            data["baselines"] = {
                json.dumps(list(key)): record.to_dict()
                for key, record in self._baselines.items()
            }
            data["diagnostics"] = [record.to_dict() for record in self._diagnostics]

            # Preserve the pre-0.59 SQLModel body at top level so a rollback
            # reader can recover accepted Prefect work. New generic dispatch
            # fields stay inside the versioned envelope until old binaries are
            # outside the declared rollback window. Remove schema tags only
            # from known persisted record objects; nested user metadata and
            # provider receipts may legitimately contain their own schema keys.
            def legacy_record(value: object) -> dict[str, Any]:
                record = _snapshot_mapping(value)
                record.pop("schema", None)
                return record

            legacy_data = dict(data)
            for family in (
                "submissions",
                "outbox",
                "dispatches",
                "leases",
                "attempts",
                "result_publications",
                "checkpoints",
                "effects",
                "previews",
                "diffs",
                "shadows",
                "baselines",
                "action_jobs",
            ):
                raw_family = data[family]
                if not isinstance(raw_family, Mapping):
                    raise ValueError(f"durable snapshot {family} must be an object")
                legacy_data[family] = {
                    key: legacy_record(value)
                    for key, value in cast(Mapping[str, object], raw_family).items()
                }

            legacy_dispatches = cast(
                dict[str, dict[str, Any]], legacy_data["dispatches"]
            )
            for record in legacy_dispatches.values():
                raw_history = record.get("reconciliation_history", ())
                if not isinstance(raw_history, (list, tuple)):
                    raise ValueError(
                        "durable snapshot reconciliation history must be an array"
                    )
                record["reconciliation_history"] = [
                    legacy_record(item) for item in cast(Sequence[object], raw_history)
                ]

            raw_route_states = data["execution_route_states"]
            if not isinstance(raw_route_states, Mapping):
                raise ValueError(
                    "durable snapshot execution route states must be an object"
                )
            legacy_route_states: dict[str, dict[str, Any]] = {}
            for route, value in cast(Mapping[str, object], raw_route_states).items():
                record = legacy_record(value)
                raw_history = record.get("history", ())
                if not isinstance(raw_history, (list, tuple)):
                    raise ValueError(
                        "durable snapshot execution route history must be an array"
                    )
                record["history"] = [
                    legacy_record(item) for item in cast(Sequence[object], raw_history)
                ]
                legacy_route_states[route] = record
            legacy_data["execution_route_states"] = legacy_route_states

            legacy_data["diagnostics"] = [
                legacy_record(item) for item in data["diagnostics"]
            ]

            raw_legacy_dispatches: object = legacy_data.get("dispatches", {})
            if not isinstance(raw_legacy_dispatches, Mapping):
                raise ValueError("durable snapshot dispatches must be an object")
            legacy_dispatches: dict[str, Any] = {}
            for key, value in cast(
                Mapping[object, object], raw_legacy_dispatches
            ).items():
                if not isinstance(key, str):
                    raise ValueError("durable snapshot dispatch keys must be strings")
                legacy_dispatches[key] = value
            for record in legacy_dispatches.values():
                if isinstance(record, dict):
                    record_fields = cast(dict[str, Any], record)
                    record_fields.pop("backend_kind", None)
                    record_fields.pop("remote_run_id", None)
                    raw_history: object = record_fields.get(
                        "reconciliation_history", ()
                    )
                    if not isinstance(raw_history, (list, tuple)):
                        raise ValueError(
                            "durable snapshot reconciliation history must be an array"
                        )
                    history = cast(Sequence[Any], raw_history)
                    for reconciliation in history:
                        if isinstance(reconciliation, dict):
                            reconciliation_fields = cast(dict[str, Any], reconciliation)
                            reconciliation_fields.pop("backend_kind", None)
                            reconciliation_fields.pop("remote_run_id", None)
            return {
                "schema": DURABLE_WORK_SNAPSHOT_SCHEMA,
                "data": data,
                **legacy_data,
            }

    @classmethod
    def from_snapshot(cls, payload: object) -> MemoryDurableWorkStore:
        """Decode a versioned snapshot or a supported legacy SQL/memory payload."""
        if not isinstance(payload, Mapping):
            raise TypeError("durable work snapshot must be an object")
        payload = cast(Mapping[str, Any], payload)
        if "schema" in payload:
            if payload.get("schema") != DURABLE_WORK_SNAPSHOT_SCHEMA:
                raise ValueError("unsupported durable work snapshot schema")
            raw_data_value: object = payload.get("data")
            if not isinstance(raw_data_value, Mapping):
                raise ValueError("durable work snapshot data must be an object")
            data = cast(Mapping[str, Any], raw_data_value)
            expected_fields = {
                "admission_limit",
                "submissions",
                "idempotency",
                "outbox",
                "dispatches",
                "leases",
                "attempts",
                "effects",
                "execution_route_states",
                "execution_route_references",
                "action_jobs",
                "action_idempotency",
                "result_publications",
                "checkpoints",
                "previews",
                "diffs",
                "shadows",
                "baselines",
                "diagnostics",
            }
            if set(data) != expected_fields:
                raise ValueError("durable work snapshot has unsupported data fields")
            mapping_families = expected_fields - {"admission_limit", "diagnostics"}
            for family in mapping_families:
                if not isinstance(data[family], Mapping):
                    raise ValueError(
                        f"durable work snapshot {family} must be an object"
                    )
            if not isinstance(data["diagnostics"], (list, tuple)):
                raise ValueError("durable work snapshot diagnostics must be an array")
        else:
            # The 0.58 memory and SQLModel codecs persisted their body without
            # an envelope. Continue reading those records during migration.
            data = payload

        store = cls(admission_limit=data.get("admission_limit"))
        store._load_legacy_unchecked(data)

        def rows(
            raw: object,
            record_type: type[Any],
            identity_fields: tuple[str, ...],
        ) -> dict[tuple[Any, ...], Any]:
            if raw is None:
                return {}
            if not isinstance(raw, Mapping):
                raise ValueError("durable snapshot record family must be an object")
            records = cast(Mapping[object, object], raw)
            result: dict[tuple[Any, ...], Any] = {}
            for encoded_key, value in records.items():
                if not isinstance(encoded_key, str) or not isinstance(value, Mapping):
                    raise ValueError("durable snapshot record is malformed")
                key_value: object = cast(object, json.loads(encoded_key))
                if not isinstance(key_value, list):
                    raise ValueError("durable snapshot key must be a JSON array")
                key = cast(list[object], key_value)
                if not all(isinstance(part, str) for part in key):
                    raise ValueError("durable snapshot key must contain strings")
                fields = _snapshot_record_fields(cast(object, value), record_type)
                if any(
                    not isinstance(fields.get(name), str) for name in identity_fields
                ):
                    raise ValueError("durable snapshot record identity is malformed")
                expected_key = tuple(fields[name] for name in identity_fields)
                if tuple(key) != expected_key:
                    raise ValueError(
                        "durable snapshot key does not match its record identity"
                    )
                if record_type is ShadowRunRecord and isinstance(
                    fields.get("effect_ids"), list
                ):
                    fields["effect_ids"] = tuple(fields["effect_ids"])
                record = (
                    DispatchRecord.from_dict(cast(Mapping[str, Any], value))
                    if record_type is DispatchRecord
                    else record_type(**fields)
                )
                result[expected_key] = record
            return result

        store._submissions = rows(
            data.get("submissions"),
            SubmissionRecord,
            ("tenant_id", "workspace_id", "submission_id"),
        )
        store._outbox = rows(
            data.get("outbox"),
            OutboxRecord,
            ("tenant_id", "workspace_id", "outbox_id"),
        )
        store._dispatches = rows(
            data.get("dispatches"),
            DispatchRecord,
            ("tenant_id", "workspace_id", "submission_id"),
        )
        store._leases = rows(
            data.get("leases"),
            LeaseRecord,
            ("tenant_id", "workspace_id", "submission_id"),
        )
        store._attempts = rows(
            data.get("attempts"),
            AttemptRecord,
            ("tenant_id", "workspace_id", "attempt_id"),
        )
        store._effects = rows(
            data.get("effects"),
            EffectRecord,
            ("tenant_id", "workspace_id", "effect_id"),
        )
        store._action_jobs = rows(
            data.get("action_jobs"),
            ActionJobRecord,
            ("tenant_id", "workspace_id", "action_id"),
        )
        raw_action_idempotency: object = data.get("action_idempotency") or {}
        if not isinstance(raw_action_idempotency, Mapping):
            raise ValueError("durable action idempotency must be an object")
        action_entries = cast(Mapping[object, object], raw_action_idempotency)
        action_idempotency: dict[tuple[Any, ...], str] = {}
        for key, value in action_entries.items():
            if not isinstance(key, str) or not isinstance(value, str) or not value:
                raise ValueError("durable action idempotency entry is malformed")
            decoded_key_value: object = cast(object, json.loads(key))
            if not isinstance(decoded_key_value, list):
                raise ValueError("durable action idempotency key is malformed")
            decoded_key = cast(list[object], decoded_key_value)
            if not all(isinstance(part, str) for part in decoded_key):
                raise ValueError("durable action idempotency key is malformed")
            action_idempotency[tuple(decoded_key)] = value
        store._action_idempotency = action_idempotency
        store._result_publications = rows(
            data.get("result_publications"),
            ResultPublicationRecord,
            ("tenant_id", "workspace_id", "submission_id", "attempt_id"),
        )
        store._checkpoints = rows(
            data.get("checkpoints"),
            CheckpointRecord,
            ("tenant_id", "workspace_id", "checkpoint_id"),
        )
        store._previews = rows(
            data.get("previews"),
            PreviewWorkspace,
            ("tenant_id", "workspace_id", "preview_id"),
        )
        store._diffs = rows(
            data.get("diffs"),
            DiffRecord,
            ("tenant_id", "workspace_id", "diff_id"),
        )
        store._shadows = rows(
            data.get("shadows"),
            ShadowRunRecord,
            ("tenant_id", "workspace_id", "shadow_run_id"),
        )
        store._baselines = rows(
            data.get("baselines"),
            BaselineAcknowledgement,
            ("tenant_id", "workspace_id", "schema_baseline_id"),
        )
        raw_diagnostics: object = data.get("diagnostics") or ()
        if not isinstance(raw_diagnostics, Sequence) or isinstance(
            raw_diagnostics, (str, bytes)
        ):
            raise ValueError("durable diagnostics must be an array")
        diagnostics: list[StateDiagnostic] = []
        diagnostic_rows = cast(Sequence[Any], raw_diagnostics)
        for item in diagnostic_rows:
            if isinstance(item, StateDiagnostic):
                diagnostics.append(item)
            elif isinstance(item, Mapping):
                diagnostics.append(
                    StateDiagnostic(
                        **_snapshot_record_fields(cast(object, item), StateDiagnostic)
                    )
                )
            else:
                raise ValueError("durable diagnostic record is malformed")
        store._diagnostics = diagnostics
        return store

    def load(self, payload: Mapping[str, Any]) -> None:
        """Atomically replace state after validating a complete snapshot."""
        replacement = self.from_snapshot(payload)
        with self._lock:
            self.admission_limit = replacement.admission_limit
            for name in _SNAPSHOT_STATE_FIELDS:
                setattr(self, name, getattr(replacement, name))


__all__ = ["DURABLE_WORK_SNAPSHOT_SCHEMA", "MemoryDurableWorkStore"]
