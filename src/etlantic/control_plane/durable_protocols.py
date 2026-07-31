"""CP3 provider contracts for durable work coordination."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

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
    ) -> tuple[SubmissionRecord, bool]: ...
    def pending_outbox(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ) -> Sequence[OutboxRecord]: ...
    def mark_published(
        self, ctx: ControlPlaneContext, outbox_id: str
    ) -> OutboxRecord: ...
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
    def start_attempt(
        self,
        ctx: ControlPlaneContext,
        submission_id: str,
        *,
        owner_id: str,
        fencing_token: int,
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
    ) -> CheckpointRecord: ...
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
    def create_preview(
        self, ctx: ControlPlaneContext, preview: PreviewWorkspace
    ) -> PreviewWorkspace: ...
    def cleanup_expired_previews(
        self, ctx: ControlPlaneContext
    ) -> Sequence[PreviewWorkspace]: ...


__all__ = ["DurableWorkStore"]
