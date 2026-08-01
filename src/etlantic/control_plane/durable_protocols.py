"""CP3 provider contracts for durable work coordination."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from etlantic.control_plane.durable_models import (
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
from etlantic.control_plane.models import ControlPlaneContext


@runtime_checkable
class DurableWorkStore(Protocol):
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
    ) -> tuple[SubmissionRecord, bool]: ...
    def pending_outbox(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ) -> Sequence[OutboxRecord]: ...
    def mark_published(
        self, ctx: ControlPlaneContext, outbox_id: str
    ) -> OutboxRecord: ...
    def cancel_submission(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> SubmissionRecord: ...
    def acquire_lease(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        ttl_seconds: int,
    ) -> LeaseRecord: ...
    def heartbeat(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        ttl_seconds: int,
    ) -> LeaseRecord: ...
    def release_lease(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
    ) -> None: ...
    def start_attempt(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        context: Mapping[str, Any] | None = None,
    ) -> AttemptRecord: ...
    def finish_attempt(
        self,
        ctx: ControlPlaneContext,
        attempt_id: str,
        *,
        owner_id: str,
        fencing_token: int,
        status: str,
    ) -> AttemptRecord: ...
    def compare_and_swap_checkpoint(
        self,
        ctx: ControlPlaneContext,
        checkpoint_id: str,
        *,
        expected_version: int | None,
        value_fingerprint: str,
        attempt_id: str | None = None,
        fencing_token: int | None = None,
        schema_baseline_id: str | None = None,
    ) -> CheckpointRecord: ...
    def explain_transition(
        self,
        ctx: ControlPlaneContext,
        checkpoint_id: str,
        *,
        expected_version: int | None,
        value_fingerprint: str,
    ) -> StateTransitionExplanation: ...
    def diagnose_checkpoint(
        self,
        ctx: ControlPlaneContext,
        checkpoint_id: str,
        *,
        kind: str = "corruption",
        detail: str = "",
    ) -> StateDiagnostic: ...
    def acknowledge_baseline(
        self,
        ctx: ControlPlaneContext,
        *,
        schema_baseline_id: str,
        observation_fingerprint: str,
        expected_version: int | None = None,
        submission_id: str | None = None,
    ) -> BaselineAcknowledgement: ...
    def record_effect(
        self, ctx: ControlPlaneContext, effect: EffectRecord
    ) -> EffectRecord: ...
    def replay(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> ReplayRecord: ...
    def plan_resume(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> RepairPlan: ...
    def plan_repair(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        checkpoint_id: str | None = None,
        invalidated_partition_ids: Sequence[str] = (),
        reusable_artifact_ids: Sequence[str] = (),
    ) -> RepairPlan: ...
    def plan_backfill(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        partition_ids: Sequence[str],
        checkpoint_id: str | None = None,
    ) -> RepairPlan: ...
    def create_preview(
        self, ctx: ControlPlaneContext, preview: PreviewWorkspace
    ) -> PreviewWorkspace: ...
    def mark_preview_stale(
        self,
        ctx: ControlPlaneContext,
        preview_id: str,
        *,
        code_fingerprint: str | None = None,
        plan_fingerprint: str | None = None,
        policy_fingerprint: str | None = None,
        environment_fingerprint: str | None = None,
    ) -> PreviewWorkspace: ...
    def record_preview_diff(
        self, ctx: ControlPlaneContext, diff: DiffRecord
    ) -> DiffRecord: ...
    def authorize_shadow_run(
        self, ctx: ControlPlaneContext, shadow: ShadowRunRecord
    ) -> ShadowRunRecord: ...
    def cleanup_expired_previews(
        self, ctx: ControlPlaneContext
    ) -> Sequence[PreviewWorkspace]: ...


__all__ = ["DurableWorkStore"]
