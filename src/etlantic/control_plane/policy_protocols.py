"""Policy provider protocol (CP4)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.policy_models import (
    PolicyBundle,
    PolicyDecision,
    PolicyHook,
)


@runtime_checkable
class PolicyProvider(Protocol):
    """Evaluate versioned policy decisions for control-plane hooks."""

    def get_bundle(
        self, ctx: ControlPlaneContext, *, bundle_id: str | None = None
    ) -> PolicyBundle:
        """Return the active (or named) policy bundle for the scope."""

    def decide(
        self,
        ctx: ControlPlaneContext,
        *,
        hook: PolicyHook,
        plan_fingerprint: str | None = None,
        revision_id: str | None = None,
        resource: str | None = None,
        attributes: Mapping[str, Any] | None = None,
        bundle_id: str | None = None,
    ) -> PolicyDecision:
        """Produce an explicit decision for ``hook``."""

    def require_available(self, ctx: ControlPlaneContext) -> None:
        """Fail closed when the provider cannot serve protected operations."""


__all__ = ["PolicyProvider"]
