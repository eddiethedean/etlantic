"""In-memory deterministic policy provider (CP4 conformance reference)."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.governance_models import GovernanceConstraints
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.policy_models import (
    PolicyBundle,
    PolicyDecision,
    PolicyEffect,
    PolicyHook,
    compute_policy_fingerprint,
)


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.tenant.tenant_id, ctx.workspace.workspace_id


@dataclass
class MemoryPolicyProvider:
    """Deterministic allow/deny/require_approval rules keyed by hook."""

    default_bundle_id: str = "default"
    default_version: str = "1"
    unavailable: bool = False
    # (tenant, workspace, hook) -> effect
    rules: dict[tuple[str, str, str], PolicyEffect] = field(default_factory=dict)
    global_rules: dict[str, PolicyEffect] = field(default_factory=dict)
    constraints: GovernanceConstraints = field(default_factory=GovernanceConstraints)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        if not self.global_rules:
            self.global_rules = {
                "pre_plan": "allow",
                "post_plan": "allow",
                "pre_submit": "allow",
                "post_execution": "allow",
                "pre_promote": "require_approval",
                "pre_repair": "allow",
                "privileged_op": "require_approval",
            }

    def set_rule(
        self,
        hook: PolicyHook,
        effect: PolicyEffect,
        *,
        tenant: str | None = None,
        workspace: str | None = None,
    ) -> None:
        with self._lock:
            if tenant is not None and workspace is not None:
                self.rules[(tenant, workspace, hook)] = effect
            else:
                self.global_rules[hook] = effect

    def get_bundle(
        self, ctx: ControlPlaneContext, *, bundle_id: str | None = None
    ) -> PolicyBundle:
        self.require_available(ctx)
        bid = bundle_id or self.default_bundle_id
        fingerprint = compute_policy_fingerprint(
            bundle_id=bid,
            hook="bundle",
            plan_fingerprint=None,
            revision_id=self.default_version,
            constraints=self.constraints.to_dict(),
        )
        return PolicyBundle(
            bundle_id=bid,
            version=self.default_version,
            fingerprint=fingerprint,
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
        self.require_available(ctx)
        with self._lock:
            tenant, workspace = _scope(ctx)
            effect = self.rules.get(
                (tenant, workspace, hook),
                self.global_rules.get(hook, "deny"),
            )
            bundle = self.get_bundle(ctx, bundle_id=bundle_id)
            attrs = dict(attributes or {})
            if resource is not None:
                attrs.setdefault("resource", resource)
            # Governance boundary checks force deny.
            target_region = attrs.get("target_region")
            egress = attrs.get("egress_destination")
            if self.constraints.crosses_boundary(
                target_region=str(target_region) if target_region else None,
                egress_destination=str(egress) if egress else None,
            ):
                effect = "deny"
            fingerprint = compute_policy_fingerprint(
                bundle_id=bundle.bundle_id,
                hook=hook,
                plan_fingerprint=plan_fingerprint,
                revision_id=revision_id,
                constraints=self.constraints.to_dict(),
            )
            reasons: list[str] = []
            if effect == "deny":
                reasons.append(f"policy denied hook={hook}")
            elif effect == "require_approval":
                reasons.append(f"approval required for hook={hook}")
            else:
                reasons.append(f"policy allowed hook={hook}")
            return PolicyDecision(
                decision_id=str(uuid.uuid4()),
                hook=hook,
                effect=effect,  # type: ignore[arg-type]
                policy_bundle_id=bundle.bundle_id,
                policy_fingerprint=fingerprint,
                reasons=tuple(reasons),
                constraints=self.constraints,
                evidence_refs=(f"bundle:{bundle.fingerprint}",),
                plan_fingerprint=plan_fingerprint,
                revision_id=revision_id,
                metadata={"attributes": attrs} if attrs else {},
            )

    def require_available(self, ctx: ControlPlaneContext) -> None:
        if self.unavailable:
            raise ControlPlaneError(
                "policy provider unavailable",
                code="PMCP503",
                status=503,
                type="etlantic.control_plane/unavailable",
                title="Unavailable",
                extensions={
                    "tenant_id": ctx.tenant.tenant_id,
                    "workspace_id": ctx.workspace.workspace_id,
                },
            )


__all__ = ["MemoryPolicyProvider"]
