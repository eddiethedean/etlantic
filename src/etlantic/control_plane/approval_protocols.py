"""Approval store protocol (CP4)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from etlantic.control_plane.approval_models import ApprovalRequest
from etlantic.control_plane.models import ControlPlaneContext


@runtime_checkable
class ApprovalStore(Protocol):
    """Durable approval requests with separation-of-duties enforcement."""

    def create(
        self,
        ctx: ControlPlaneContext,
        *,
        hook: str,
        plan_fingerprint: str,
        policy_fingerprint: str,
        revision_id: str | None = None,
        expires_at: datetime | None = None,
        approval_id: str | None = None,
    ) -> ApprovalRequest:
        """Create a pending approval request for the caller principal."""

    def get(self, ctx: ControlPlaneContext, *, approval_id: str) -> ApprovalRequest:
        """Fetch a scoped approval or raise not_found."""

    def decide(
        self,
        ctx: ControlPlaneContext,
        *,
        approval_id: str,
        approve: bool,
        reason: str | None = None,
        plan_fingerprint: str | None = None,
        policy_fingerprint: str | None = None,
    ) -> ApprovalRequest:
        """Approve or deny with SoD; mark stale on fingerprint drift."""

    def revoke(
        self, ctx: ControlPlaneContext, *, approval_id: str, reason: str | None = None
    ) -> ApprovalRequest:
        """Revoke a pending or approved request."""

    def list_pending(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ) -> Sequence[ApprovalRequest]:
        """List pending approvals in scope."""

    def is_satisfied(
        self,
        ctx: ControlPlaneContext,
        *,
        plan_fingerprint: str,
        policy_fingerprint: str,
        revision_id: str | None = None,
        hook: str = "pre_promote",
    ) -> bool:
        """Return True when a non-stale approval covers the fingerprints."""


__all__ = ["ApprovalStore"]
