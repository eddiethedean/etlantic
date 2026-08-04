"""In-memory quota provider with weighted RR under shared pressure (CP4)."""

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
    shared_pressure: bool = False
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

    def set_shared_pressure(self, enabled: bool) -> None:
        """Host mark that shared capacity is contended (enables weighted RR)."""
        with self._lock:
            self.shared_pressure = bool(enabled)

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
            scope = _scope(ctx)
            if self.shared_pressure and not self._wrr_allows(
                scope, resource=resource, units=units
            ):
                return QuotaDecision(
                    effect="deny",
                    resource=resource,
                    limit=budget.limit,
                    used=used,
                    reason="fairness deferred",
                    metadata={
                        "rr_cursor": self._rr_cursor,
                        "weight": budget.weight,
                        "shared_pressure": True,
                    },
                )
            usage = dict(state.usage)
            usage[resource] = used + units
            self._states[scope] = replace(state, usage=usage, updated_at=_now())
            return QuotaDecision(
                effect="allow",
                resource=resource,
                limit=budget.limit,
                used=used + units,
                reason="admitted",
                metadata={
                    "rr_cursor": self._rr_cursor,
                    "weight": budget.weight,
                    "shared_pressure": self.shared_pressure,
                },
            )

    def _wrr_allows(
        self,
        scope: tuple[str, str],
        *,
        resource: QuotaResource,
        units: int,
    ) -> bool:
        """Weighted round-robin among eligible tenants under shared pressure.

        Builds a ring expanded by each scope's weight and advances ``_rr_cursor``
        to the next eligible scope. Only the scope that owns the current turn
        may admit; others receive ``fairness deferred``.
        """
        limit = int(self.default_limits.get(resource, 0))
        # Active competitors: requesting scope plus any scope already using the
        # resource (idle tenants with unused headroom are not in the ring so they
        # cannot starve requesters when shared_pressure is on).
        eligible: list[tuple[str, str]] = []
        for key, state in sorted(self._states.items()):
            if state.suspended or state.contained:
                continue
            used = int(state.usage.get(resource, 0))
            need = units if key == scope else 1
            if used + need > limit:
                continue
            if key == scope or used > 0:
                eligible.append(key)
        if not eligible:
            return False
        if len(eligible) == 1:
            return eligible[0] == scope
        ring: list[tuple[str, str]] = []
        for key in eligible:
            weight = max(1, int(self.weights.get(key, 1)))
            ring.extend([key] * weight)
        n = len(ring)
        idx = self._rr_cursor % n
        if ring[idx] != scope:
            return False
        self._rr_cursor = (idx + 1) % n
        return True

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
