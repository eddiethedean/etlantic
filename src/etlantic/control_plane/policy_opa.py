"""Optional OPA adapter skeleton behind PolicyProvider (lazy import)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.policy_memory import MemoryPolicyProvider
from etlantic.control_plane.policy_models import (
    PolicyBundle,
    PolicyDecision,
    PolicyHook,
)


class OpaPolicyProvider:
    """Thin optional adapter.

    When the ``opa`` package is not installed, construction fails closed.
    Hosts that need OPA should inject a fully configured adapter; this class
    documents the seam and delegates to ``MemoryPolicyProvider`` only when an
    explicit ``fallback`` is provided for tests.
    """

    def __init__(
        self,
        *,
        policy_path: str | None = None,
        fallback: MemoryPolicyProvider | None = None,
        require_opa: bool = True,
    ) -> None:
        self.policy_path = policy_path
        self._fallback = fallback
        self._opa = None
        if require_opa:
            try:
                import opa  # type: ignore[import-not-found]  # noqa: F401
            except ImportError as exc:
                if fallback is None:
                    raise ControlPlaneError(
                        "OPA adapter unavailable; install opa or provide fallback",
                        code="PMCP503",
                        status=503,
                        type="etlantic.control_plane/unavailable",
                        title="Unavailable",
                    ) from exc
                self._opa = None
            else:
                self._opa = True

    def get_bundle(
        self, ctx: ControlPlaneContext, *, bundle_id: str | None = None
    ) -> PolicyBundle:
        if self._fallback is not None:
            return self._fallback.get_bundle(ctx, bundle_id=bundle_id)
        raise ControlPlaneError(
            "OPA evaluation not configured",
            code="PMCP503",
            status=503,
            type="etlantic.control_plane/unavailable",
            title="Unavailable",
        )

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
        if self._fallback is not None:
            return self._fallback.decide(
                ctx,
                hook=hook,
                plan_fingerprint=plan_fingerprint,
                revision_id=revision_id,
                resource=resource,
                attributes=attributes,
                bundle_id=bundle_id,
            )
        raise ControlPlaneError(
            "OPA evaluation not configured",
            code="PMCP503",
            status=503,
            type="etlantic.control_plane/unavailable",
            title="Unavailable",
        )

    def require_available(self, ctx: ControlPlaneContext) -> None:
        if self._fallback is not None:
            self._fallback.require_available(ctx)
            return
        raise ControlPlaneError(
            "OPA evaluation not configured",
            code="PMCP503",
            status=503,
            type="etlantic.control_plane/unavailable",
            title="Unavailable",
        )


__all__ = ["OpaPolicyProvider"]
