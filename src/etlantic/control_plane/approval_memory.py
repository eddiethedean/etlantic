"""In-memory approval store with separation-of-duties (CP4)."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime

from etlantic.control_plane.approval_models import (
    ApprovalDecisionRecord,
    ApprovalRequest,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.tenant.tenant_id, ctx.workspace.workspace_id


def _now() -> datetime:
    return datetime.now(UTC)


class MemoryApprovalStore:
    def __init__(self) -> None:
        self._approvals: dict[tuple[str, str, str], ApprovalRequest] = {}
        self._lock = threading.RLock()

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
        aid = approval_id or str(uuid.uuid4())
        key = (*_scope(ctx), aid)
        record = ApprovalRequest(
            approval_id=aid,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            hook=hook,
            plan_fingerprint=plan_fingerprint,
            policy_fingerprint=policy_fingerprint,
            revision_id=revision_id,
            requester_subject=ctx.principal.subject,
            requester_issuer=ctx.principal.issuer,
            expires_at=expires_at,
        )
        with self._lock:
            self._approvals[key] = record
            return deepcopy(record)

    def get(self, ctx: ControlPlaneContext, *, approval_id: str) -> ApprovalRequest:
        with self._lock:
            key = (*_scope(ctx), approval_id)
            record = self._approvals.get(key)
            if record is None:
                raise ControlPlaneError.not_found("approval not found")
            return deepcopy(self._refresh(record))

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
        with self._lock:
            key = (*_scope(ctx), approval_id)
            record = self._approvals.get(key)
            if record is None:
                raise ControlPlaneError.not_found("approval not found")
            record = self._refresh(record)
            if record.status != "pending":
                raise ControlPlaneError.conflict(
                    f"approval is {record.status}",
                    extensions={"approval_id": approval_id},
                )
            # Separation of duties: requester subject cannot decide (issuer-agnostic).
            if record.requester_subject == ctx.principal.subject:
                raise ControlPlaneError.forbidden(
                    "separation of duties: requester cannot decide",
                    extensions={"approval_id": approval_id},
                )
            if (
                plan_fingerprint is not None
                and plan_fingerprint != record.plan_fingerprint
            ) or (
                policy_fingerprint is not None
                and policy_fingerprint != record.policy_fingerprint
            ):
                stale = replace(record, status="stale", decided_at=_now())
                self._approvals[key] = stale
                raise ControlPlaneError.conflict(
                    "approval is stale relative to plan or policy fingerprint",
                    extensions={"approval_id": approval_id, "status": "stale"},
                )
            decision = ApprovalDecisionRecord(
                decision_id=str(uuid.uuid4()),
                approval_id=approval_id,
                effect="approved" if approve else "denied",
                actor_subject=ctx.principal.subject,
                actor_issuer=ctx.principal.issuer,
                reason=reason,
            )
            updated = replace(
                record,
                status="approved" if approve else "denied",
                decided_at=_now(),
                decisions=(*record.decisions, decision),
            )
            self._approvals[key] = updated
            return deepcopy(updated)

    def revoke(
        self, ctx: ControlPlaneContext, *, approval_id: str, reason: str | None = None
    ) -> ApprovalRequest:
        with self._lock:
            key = (*_scope(ctx), approval_id)
            record = self._approvals.get(key)
            if record is None:
                raise ControlPlaneError.not_found("approval not found")
            if record.status not in ("pending", "approved"):
                raise ControlPlaneError.conflict(
                    f"cannot revoke approval in status {record.status}"
                )
            updated = replace(
                record,
                status="revoked",
                decided_at=_now(),
                metadata={**dict(record.metadata), "revoke_reason": reason or ""},
            )
            self._approvals[key] = updated
            return deepcopy(updated)

    def list_pending(
        self, ctx: ControlPlaneContext, *, limit: int = 100
    ) -> Sequence[ApprovalRequest]:
        tenant, workspace = _scope(ctx)
        with self._lock:
            items = []
            for (t, w, _), record in self._approvals.items():
                if t != tenant or w != workspace:
                    continue
                refreshed = self._refresh(record)
                self._approvals[(t, w, refreshed.approval_id)] = refreshed
                if refreshed.status == "pending":
                    items.append(deepcopy(refreshed))
                if len(items) >= limit:
                    break
            return items

    def is_satisfied(
        self,
        ctx: ControlPlaneContext,
        *,
        plan_fingerprint: str,
        policy_fingerprint: str,
        revision_id: str | None = None,
        hook: str = "pre_promote",
    ) -> bool:
        tenant, workspace = _scope(ctx)
        with self._lock:
            for (t, w, _), record in self._approvals.items():
                if t != tenant or w != workspace:
                    continue
                refreshed = self._refresh(record)
                self._approvals[(t, w, refreshed.approval_id)] = refreshed
                if refreshed.status != "approved":
                    continue
                if refreshed.hook != hook:
                    continue
                if refreshed.plan_fingerprint != plan_fingerprint:
                    continue
                if refreshed.policy_fingerprint != policy_fingerprint:
                    continue
                if revision_id is not None and refreshed.revision_id != revision_id:
                    continue
                return True
            return False

    def _refresh(self, record: ApprovalRequest) -> ApprovalRequest:
        if (
            record.status == "pending"
            and record.expires_at is not None
            and record.expires_at <= _now()
        ):
            expired = replace(record, status="expired", decided_at=_now())
            key = (record.tenant_id, record.workspace_id, record.approval_id)
            self._approvals[key] = expired
            return expired
        return record


__all__ = ["MemoryApprovalStore"]
