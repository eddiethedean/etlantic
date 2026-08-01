"""CP3 durable-work records.

These provider-neutral records deliberately carry only opaque identities,
fingerprints, and redacted metadata.  They are the stable interchange between
the API, dispatcher, execution host, and optional persistence adapters.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)

SUBMISSION_RECORD_SCHEMA = "etlantic.control_plane.submission_record/1"
OUTBOX_RECORD_SCHEMA = "etlantic.control_plane.outbox_record/1"
LEASE_RECORD_SCHEMA = "etlantic.control_plane.lease_record/1"
ATTEMPT_RECORD_SCHEMA = "etlantic.control_plane.attempt_record/1"
CHECKPOINT_RECORD_SCHEMA = "etlantic.control_plane.checkpoint_record/1"
EFFECT_RECORD_SCHEMA = "etlantic.control_plane.effect_record/1"
REPLAY_RECORD_SCHEMA = "etlantic.control_plane.replay_record/1"
PREVIEW_WORKSPACE_SCHEMA = "etlantic.control_plane.preview_workspace/1"
REPAIR_PLAN_SCHEMA = "etlantic.control_plane.repair_plan/1"
DIFF_RECORD_SCHEMA = "etlantic.control_plane.diff_record/1"
SHADOW_RUN_RECORD_SCHEMA = "etlantic.control_plane.shadow_run_record/1"
STATE_TRANSITION_EXPLANATION_SCHEMA = (
    "etlantic.control_plane.state_transition_explanation/1"
)
STATE_DIAGNOSTIC_SCHEMA = "etlantic.control_plane.state_diagnostic/1"
BASELINE_ACK_SCHEMA = "etlantic.control_plane.baseline_acknowledgement/1"

STATE_NAMESPACES = ("cursor:", "watermark:", "partition:", "snapshot:", "checkpoint:")

SubmissionStatus = Literal[
    "accepted", "dispatched", "cancel_requested", "cancelled", "completed", "failed"
]
AttemptStatus = Literal["running", "cancelled", "completed", "failed", "lost"]
EffectStatus = Literal[
    "none", "pending", "committed", "not_committed", "failed", "unknown"
]
RepairPlanKind = Literal["resume", "repair", "backfill"]


def _metadata(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    result = redact_control_plane_payload(dict(value or {}))
    return dict(result) if isinstance(result, dict) else {}


def namespaced_checkpoint_id(kind: str, identity: str) -> str:
    """Build a namespaced checkpoint id (`cursor:…`, `watermark:…`, …)."""
    prefix = kind if kind.endswith(":") else f"{kind}:"
    if prefix not in STATE_NAMESPACES:
        raise ValueError(f"unsupported state namespace: {kind}")
    text = identity.strip()
    if not text:
        raise ValueError("state identity must not be empty")
    return f"{prefix}{text}"


@dataclass(frozen=True, slots=True)
class SubmissionRecord:
    submission_id: str
    tenant_id: str
    workspace_id: str
    principal_subject: str
    operation: str
    idempotency_key: str
    created_at: str
    plan_fingerprint: str
    revision_id: str | None = None
    plugin_fingerprint: str | None = None
    policy_fingerprint: str | None = None
    input_snapshot: str | None = None
    principal_issuer: str | None = None
    principal_kind: str = "human"
    status: SubmissionStatus = "accepted"
    schema_observation_fingerprint: str | None = None
    schema_baseline_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["input_snapshot"] = (
            redact_control_plane_text(self.input_snapshot)
            if self.input_snapshot is not None
            else None
        )
        return {
            "schema": SUBMISSION_RECORD_SCHEMA,
            **payload,
            "metadata": _metadata(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    outbox_id: str
    submission_id: str
    tenant_id: str
    workspace_id: str
    created_at: str
    payload_fingerprint: str
    published_at: str | None = None
    delivery_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": OUTBOX_RECORD_SCHEMA,
            **asdict(self),
            "metadata": _metadata(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class LeaseRecord:
    submission_id: str
    tenant_id: str
    workspace_id: str
    owner_id: str
    fencing_token: int
    acquired_at: str
    expires_at: str
    heartbeat_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"schema": LEASE_RECORD_SCHEMA, **asdict(self)}


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    attempt_id: str
    submission_id: str
    tenant_id: str
    workspace_id: str
    owner_id: str
    fencing_token: int
    started_at: str
    status: AttemptStatus = "running"
    completed_at: str | None = None
    context: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ATTEMPT_RECORD_SCHEMA,
            **asdict(self),
            "context": _metadata(self.context),
        }


@dataclass(frozen=True, slots=True)
class CheckpointRecord:
    checkpoint_id: str
    tenant_id: str
    workspace_id: str
    version: int
    value_fingerprint: str
    updated_at: str
    submission_id: str | None = None
    attempt_id: str | None = None
    schema_baseline_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CHECKPOINT_RECORD_SCHEMA,
            **asdict(self),
            "metadata": _metadata(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class EffectRecord:
    effect_id: str
    submission_id: str
    tenant_id: str
    workspace_id: str
    status: EffectStatus
    recorded_at: str
    idempotency_evidence: str | None = None
    reconciliation_evidence: str | None = None
    publication_evidence: str | None = None
    compensation_evidence: str | None = None
    authoritative: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": EFFECT_RECORD_SCHEMA,
            **asdict(self),
            "idempotency_evidence": (
                redact_control_plane_text(self.idempotency_evidence)
                if self.idempotency_evidence is not None
                else None
            ),
            "reconciliation_evidence": (
                redact_control_plane_text(self.reconciliation_evidence)
                if self.reconciliation_evidence is not None
                else None
            ),
            "publication_evidence": (
                redact_control_plane_text(self.publication_evidence)
                if self.publication_evidence is not None
                else None
            ),
            "compensation_evidence": (
                redact_control_plane_text(self.compensation_evidence)
                if self.compensation_evidence is not None
                else None
            ),
            "metadata": _metadata(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ReplayRecord:
    replay_id: str
    submission_id: str
    tenant_id: str
    workspace_id: str
    plan_fingerprint: str
    revision_id: str | None
    plugin_fingerprint: str | None
    policy_fingerprint: str | None
    input_snapshot: str | None
    checkpoint_id: str | None
    created_at: str
    differences: tuple[str, ...] = ()
    schema_observation_fingerprint: str | None = None
    schema_baseline_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["input_snapshot"] = (
            redact_control_plane_text(self.input_snapshot)
            if self.input_snapshot is not None
            else None
        )
        return {
            "schema": REPLAY_RECORD_SCHEMA,
            **payload,
            "differences": [
                redact_control_plane_text(item) or "" for item in self.differences
            ],
        }


@dataclass(frozen=True, slots=True)
class PreviewWorkspace:
    preview_id: str
    tenant_id: str
    workspace_id: str
    base_revision_id: str
    candidate_revision_id: str
    created_at: str
    expires_at: str
    quota: int
    code_fingerprint: str
    plan_fingerprint: str
    policy_fingerprint: str | None = None
    environment_fingerprint: str | None = None
    commit_ref: str | None = None
    pull_request_ref: str | None = None
    cleaned_at: str | None = None
    stale: bool = False
    stale_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stale_reason"] = (
            redact_control_plane_text(self.stale_reason)
            if self.stale_reason is not None
            else None
        )
        return {"schema": PREVIEW_WORKSPACE_SCHEMA, **payload}


@dataclass(frozen=True, slots=True)
class RepairPlan:
    plan_id: str
    kind: RepairPlanKind
    submission_id: str
    tenant_id: str
    workspace_id: str
    created_at: str
    source_plan_fingerprint: str
    checkpoint_id: str | None = None
    partition_ids: tuple[str, ...] = ()
    reusable_artifact_ids: tuple[str, ...] = ()
    invalidated_partition_ids: tuple[str, ...] = ()
    minimum_safe_closure: tuple[str, ...] = ()
    schema_baseline_id: str | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REPAIR_PLAN_SCHEMA,
            **asdict(self),
            "partition_ids": list(self.partition_ids),
            "reusable_artifact_ids": list(self.reusable_artifact_ids),
            "invalidated_partition_ids": list(self.invalidated_partition_ids),
            "minimum_safe_closure": list(self.minimum_safe_closure),
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class DiffRecord:
    diff_id: str
    preview_id: str
    tenant_id: str
    workspace_id: str
    created_at: str
    contract_diff_fingerprint: str | None = None
    graph_diff_fingerprint: str | None = None
    plan_diff_fingerprint: str | None = None
    schema_diff_fingerprint: str | None = None
    policy_diff_fingerprint: str | None = None
    cost_diff_fingerprint: str | None = None
    environment_diff_fingerprint: str | None = None
    impacted_subgraph_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"schema": DIFF_RECORD_SCHEMA, **asdict(self)}


@dataclass(frozen=True, slots=True)
class ShadowRunRecord:
    shadow_run_id: str
    preview_id: str
    submission_id: str
    tenant_id: str
    workspace_id: str
    authorized_by: str
    created_at: str
    effect_ids: tuple[str, ...] = ()
    production_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SHADOW_RUN_RECORD_SCHEMA,
            **asdict(self),
            "effect_ids": list(self.effect_ids),
        }


@dataclass(frozen=True, slots=True)
class StateTransitionExplanation:
    explanation_id: str
    tenant_id: str
    workspace_id: str
    checkpoint_id: str
    expected_version: int | None
    proposed_fingerprint: str
    current_version: int | None
    current_fingerprint: str | None
    would_succeed: bool
    reason: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"schema": STATE_TRANSITION_EXPLANATION_SCHEMA, **asdict(self)}


@dataclass(frozen=True, slots=True)
class StateDiagnostic:
    diagnostic_id: str
    tenant_id: str
    workspace_id: str
    checkpoint_id: str
    kind: Literal["corruption", "migration", "conflict"]
    detail: str
    created_at: str
    recoverable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": STATE_DIAGNOSTIC_SCHEMA,
            **asdict(self),
            "detail": redact_control_plane_text(self.detail) or "",
        }


@dataclass(frozen=True, slots=True)
class BaselineAcknowledgement:
    acknowledgement_id: str
    tenant_id: str
    workspace_id: str
    schema_baseline_id: str
    observation_fingerprint: str
    version: int
    created_at: str
    submission_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"schema": BASELINE_ACK_SCHEMA, **asdict(self)}


__all__ = [
    "ATTEMPT_RECORD_SCHEMA",
    "BASELINE_ACK_SCHEMA",
    "CHECKPOINT_RECORD_SCHEMA",
    "DIFF_RECORD_SCHEMA",
    "EFFECT_RECORD_SCHEMA",
    "LEASE_RECORD_SCHEMA",
    "OUTBOX_RECORD_SCHEMA",
    "PREVIEW_WORKSPACE_SCHEMA",
    "REPAIR_PLAN_SCHEMA",
    "REPLAY_RECORD_SCHEMA",
    "SHADOW_RUN_RECORD_SCHEMA",
    "STATE_DIAGNOSTIC_SCHEMA",
    "STATE_NAMESPACES",
    "STATE_TRANSITION_EXPLANATION_SCHEMA",
    "SUBMISSION_RECORD_SCHEMA",
    "AttemptRecord",
    "AttemptStatus",
    "BaselineAcknowledgement",
    "CheckpointRecord",
    "DiffRecord",
    "EffectRecord",
    "EffectStatus",
    "LeaseRecord",
    "OutboxRecord",
    "PreviewWorkspace",
    "RepairPlan",
    "RepairPlanKind",
    "ReplayRecord",
    "ShadowRunRecord",
    "StateDiagnostic",
    "StateTransitionExplanation",
    "SubmissionRecord",
    "SubmissionStatus",
    "namespaced_checkpoint_id",
]
