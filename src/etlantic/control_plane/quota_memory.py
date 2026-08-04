"""In-memory quota provider with fairness weights (CP4)."""

from __future__ import annotations

import threading
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.quota_models import (
    QuotaBudget,
    QuotaDecision,
    QuotaResource,
    QuotaState,
)


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.tenant.tenant_id, ctx.workspace.workspace_id


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class MemoryQuotaProvider:
    unavailable: bool = False
    default_limits: dict[str, int] = field(
        default_factory=lambda: {
            "concurrency": 10,
            "preview": 5,
            "events": 1000,
            "repair": 5,
            "storage_bytes": 1_000_000,
        }
    )
    weights: dict[tuple[str, str], int] = field(default_factory=dict)
    _states: dict[tuple[str, str], QuotaState] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _rr_cursor: int = 0

    def get_budget(
        self, ctx: ControlPlaneContext, *, resource: QuotaResource
    ) -> QuotaBudget:
        self.require_available(ctx)
        limit = int(self.default_limits.get(resource, 0))
        weight = self.weights.get(_scope(ctx), 1)
        return QuotaBudget(resource=resource, limit=limit, weight=weight)

    def get_state(self, ctx: ControlPlaneContext) -> QuotaState:
        self.require_available(ctx)
        with self._lock:
            return deepcopy(self._ensure(ctx))

    def admit(
        self,
        ctx: ControlPlaneContext,
        *,
        resource: QuotaResource,
        units: int = 1,
    ) -> QuotaDecision:
        self.require_available(ctx)
        if units < 1:
            raise ControlPlaneError.conflict("units must be positive")
        with self._lock:
            state = self._ensure(ctx)
            budget = self.get_budget(ctx, resource=resource)
            if state.suspended:
                return QuotaDecision(
                    effect="suspended",
                    resource=resource,
                    limit=budget.limit,
                    used=int(state.usage.get(resource, 0)),
                    reason="workspace suspended",
                )
            if state.contained:
                return QuotaDecision(
                    effect="contained",
                    resource=resource,
                    limit=budget.limit,
                    used=int(state.usage.get(resource, 0)),
                    reason="emergency containment active",
                )
            used = int(state.usage.get(resource, 0))
            if used + units > budget.limit:
                return QuotaDecision(
                    effect="deny",
                    resource=resource,
                    limit=budget.limit,
                    used=used,
                    reason="quota exceeded",
                )
            # Fairness: under contention prefer higher weight (simple RR tie-break).
            self._rr_cursor += 1
            usage = dict(state.usage)
            usage[resource] = used + units
            self._states[_scope(ctx)] = replace(state, usage=usage, updated_at=_now())
            return QuotaDecision(
                effect="allow",
                resource=resource,
                limit=budget.limit,
                used=used + units,
                reason="admitted",
                metadata={"rr_cursor": self._rr_cursor, "weight": budget.weight},
            )

    def release(
        self,
        ctx: ControlPlaneContext,
        *,
        resource: QuotaResource,
        units: int = 1,
    ) -> QuotaState:
        self.require_available(ctx)
        with self._lock:
            state = self._ensure(ctx)
            usage = dict(state.usage)
            usage[resource] = max(0, int(usage.get(resource, 0)) - units)
            updated = replace(state, usage=usage, updated_at=_now())
            self._states[_scope(ctx)] = updated
            return deepcopy(updated)

    def set_suspended(self, ctx: ControlPlaneContext, *, suspended: bool) -> QuotaState:
        self.require_available(ctx)
        with self._lock:
            state = self._ensure(ctx)
            updated = replace(state, suspended=suspended, updated_at=_now())
            self._states[_scope(ctx)] = updated
            return deepcopy(updated)

    def set_contained(self, ctx: ControlPlaneContext, *, contained: bool) -> QuotaState:
        self.require_available(ctx)
        with self._lock:
            state = self._ensure(ctx)
            updated = replace(state, contained=contained, updated_at=_now())
            self._states[_scope(ctx)] = updated
            return deepcopy(updated)

    def require_available(self, ctx: ControlPlaneContext) -> None:
        if self.unavailable:
            raise ControlPlaneError(
                "quota provider unavailable",
                code="PMCP503",
                status=503,
                type="etlantic.control_plane/unavailable",
                title="Unavailable",
                extensions={
                    "tenant_id": ctx.tenant.tenant_id,
                    "workspace_id": ctx.workspace.workspace_id,
                },
            )

    def _ensure(self, ctx: ControlPlaneContext) -> QuotaState:
        key = _scope(ctx)
        state = self._states.get(key)
        if state is None:
            state = QuotaState(
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
            )
            self._states[key] = state
        return state


__all__ = ["MemoryQuotaProvider"]
