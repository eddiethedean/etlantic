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
        ...

    def get_state(self, ctx: ControlPlaneContext) -> QuotaState:
        """Return current usage and suspension flags."""
        ...

    def admit(
        self,
        ctx: ControlPlaneContext,
        *,
        resource: QuotaResource,
        units: int = 1,
        idempotency_key: str | None = None,
        claim_id: str | None = None,
    ) -> QuotaDecision:
        """Admit or deny consumption; keyed retries share an active reservation.

        An allowed keyed decision includes a ``reservation_key`` in metadata.
        After its keyed release, admission may charge a fresh reservation with
        a new identity, subject to the current budget and suspension policy.
        An optional ``claim_id`` atomically registers a submission attempt as
        an owner of that reservation, including on a cached allowed decision.
        """
        ...

    def release(
        self,
        ctx: ControlPlaneContext,
        *,
        resource: QuotaResource,
        units: int = 1,
        idempotency_key: str | None = None,
        claim_id: str | None = None,
    ) -> QuotaState:
        """Release units once using ``<reservation_key>:release`` as the key.

        With ``claim_id``, abandon only that attempt's claim and release units
        only when no owners remain. Without it, terminal execution cleanup
        releases the whole reservation. Duplicate abandonment is a no-op.
        """
        ...

    def set_suspended(self, ctx: ControlPlaneContext, *, suspended: bool) -> QuotaState:
        """Toggle tenant/workspace suspension."""
        ...

    def set_contained(self, ctx: ControlPlaneContext, *, contained: bool) -> QuotaState:
        """Toggle emergency containment."""
        ...

    def require_available(self, ctx: ControlPlaneContext) -> None:
        """Fail closed when the provider cannot serve protected ops."""


__all__ = ["QuotaProvider"]
