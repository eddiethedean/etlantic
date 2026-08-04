"""Quota provider protocol (CP4)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.quota_models import (
    QuotaBudget,
    QuotaDecision,
    QuotaResource,
    QuotaState,
)


@runtime_checkable
class QuotaProvider(Protocol):
    """Tenant/workspace admission, fairness, suspension, and containment."""

    def get_budget(
        self, ctx: ControlPlaneContext, *, resource: QuotaResource
    ) -> QuotaBudget:
        """Return the configured budget for ``resource``."""

    def get_state(self, ctx: ControlPlaneContext) -> QuotaState:
        """Return current usage and suspension flags."""

    def admit(
        self,
        ctx: ControlPlaneContext,
        *,
        resource: QuotaResource,
        units: int = 1,
    ) -> QuotaDecision:
        """Admit or deny consumption; fail closed when unavailable."""

    def release(
        self,
        ctx: ControlPlaneContext,
        *,
        resource: QuotaResource,
        units: int = 1,
    ) -> QuotaState:
        """Release previously admitted units."""

    def set_suspended(
        self, ctx: ControlPlaneContext, *, suspended: bool
    ) -> QuotaState:
        """Toggle tenant/workspace suspension."""

    def set_contained(
        self, ctx: ControlPlaneContext, *, contained: bool
    ) -> QuotaState:
        """Toggle emergency containment."""

    def require_available(self, ctx: ControlPlaneContext) -> None:
        """Fail closed when the provider cannot serve protected ops."""


__all__ = ["QuotaProvider"]
