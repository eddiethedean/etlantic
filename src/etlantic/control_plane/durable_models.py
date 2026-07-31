"""CP3 durable-work records.

These provider-neutral records deliberately carry only opaque identities,
fingerprints, and redacted metadata.  They are the stable interchange between
the API, dispatcher, execution host, and optional persistence adapters.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from etlantic.control_plane.redaction import redact_control_plane_payload

SUBMISSION_RECORD_SCHEMA = "etlantic.control_plane.submission_record/1"
OUTBOX_RECORD_SCHEMA = "etlantic.control_plane.outbox_record/1"
LEASE_RECORD_SCHEMA = "etlantic.control_plane.lease_record/1"
ATTEMPT_RECORD_SCHEMA = "etlantic.control_plane.attempt_record/1"
CHECKPOINT_RECORD_SCHEMA = "etlantic.control_plane.checkpoint_record/1"
EFFECT_RECORD_SCHEMA = "etlantic.control_plane.effect_record/1"
REPLAY_RECORD_SCHEMA = "etlantic.control_plane.replay_record/1"
PREVIEW_WORKSPACE_SCHEMA = "etlantic.control_plane.preview_workspace/1"

SubmissionStatus = Literal[
    "accepted", "dispatched", "cancel_requested", "completed", "failed"
]
AttemptStatus = Literal["running", "cancelled", "completed", "failed", "lost"]
EffectStatus = Literal[
    "none", "pending", "committed", "not_committed", "failed", "unknown"
]


def _metadata(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    result = redact_control_plane_payload(dict(value or {}))
    return dict(result) if isinstance(result, dict) else {}


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
    status: SubmissionStatus = "accepted"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SUBMISSION_RECORD_SCHEMA,
            **asdict(self),
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
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": EFFECT_RECORD_SCHEMA,
            **asdict(self),
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REPLAY_RECORD_SCHEMA,
            **asdict(self),
            "differences": list(self.differences),
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
    cleaned_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"schema": PREVIEW_WORKSPACE_SCHEMA, **asdict(self)}


__all__ = [
    name
    for name in globals()
    if name.endswith(("_SCHEMA", "Record", "Workspace", "Status"))
]
