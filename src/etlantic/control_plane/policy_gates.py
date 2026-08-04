"""Policy gate helpers for plan, submit, promote, and repair hooks (CP4)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from etlantic.control_plane.approval_protocols import ApprovalStore
from etlantic.control_plane.attestation_models import require_verified
from etlantic.control_plane.attestation_protocols import AttestationStore
from etlantic.control_plane.audit_protocols import AuditEvidenceStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.policy_models import (
    PolicyDecision,
    PolicyHook,
    decision_allows,
    decision_requires_approval,
)
from etlantic.control_plane.policy_protocols import PolicyProvider
from etlantic.control_plane.quota_models import QuotaDecision, QuotaResource
from etlantic.control_plane.quota_protocols import QuotaProvider


def evaluate_policy(
    provider: PolicyProvider | None,
    ctx: ControlPlaneContext,
    *,
    hook: PolicyHook,
    plan_fingerprint: str | None = None,
    revision_id: str | None = None,
    resource: str | None = None,
    attributes: Mapping[str, Any] | None = None,
    required: bool = False,
) -> PolicyDecision | None:
    """Evaluate policy; when ``required`` and provider is missing, fail closed."""
    if provider is None:
        if required:
            raise ControlPlaneError(
                "policy provider required for protected operation",
                code="PMCP503",
                status=503,
                type="etlantic.control_plane/unavailable",
                title="Unavailable",
            )
        return None
    provider.require_available(ctx)
    return provider.decide(
        ctx,
        hook=hook,
        plan_fingerprint=plan_fingerprint,
        revision_id=revision_id,
        resource=resource,
        attributes=attributes,
    )


def enforce_policy_decision(
    decision: PolicyDecision | None,
    *,
    approvals: ApprovalStore | None = None,
    ctx: ControlPlaneContext | None = None,
) -> PolicyDecision | None:
    """Raise on deny; require satisfied approval when effect is require_approval."""
    if decision is None:
        return None
    if decision.effect == "deny":
        raise ControlPlaneError.forbidden(
            "; ".join(decision.reasons) or "policy denied",
            extensions={
                "policy_fingerprint": decision.policy_fingerprint,
                "hook": decision.hook,
            },
        )
    if decision_requires_approval(decision):
        if approvals is None or ctx is None:
            raise ControlPlaneError.forbidden(
                "approval required but approval store not configured",
                extensions={"hook": decision.hook},
            )
        ok = approvals.is_satisfied(
            ctx,
            plan_fingerprint=decision.plan_fingerprint or "",
            policy_fingerprint=decision.policy_fingerprint,
            revision_id=decision.revision_id,
            hook=decision.hook,
        )
        if not ok:
            raise ControlPlaneError.forbidden(
                "approval required and not satisfied",
                extensions={
                    "hook": decision.hook,
                    "policy_fingerprint": decision.policy_fingerprint,
                },
            )
    return decision


def gate_pre_submit(
    ctx: ControlPlaneContext,
    *,
    policy: PolicyProvider | None,
    approvals: ApprovalStore | None = None,
    quotas: QuotaProvider | None = None,
    audit: AuditEvidenceStore | None = None,
    attestations: AttestationStore | None = None,
    plan_fingerprint: str,
    revision_id: str | None = None,
    plugin_fingerprints: list[str] | None = None,
    sbom_digest: str | None = None,
    require_policy: bool = False,
    require_attestations: bool = False,
    resource: QuotaResource = "concurrency",
) -> tuple[PolicyDecision | None, QuotaDecision | None]:
    """Run pre-submit policy, quota admission, and optional attestation checks."""
    decision = evaluate_policy(
        policy,
        ctx,
        hook="pre_submit",
        plan_fingerprint=plan_fingerprint,
        revision_id=revision_id,
        required=require_policy,
    )
    enforce_policy_decision(decision, approvals=approvals, ctx=ctx)

    quota_decision: QuotaDecision | None = None
    if quotas is not None:
        quotas.require_available(ctx)
        quota_decision = quotas.admit(ctx, resource=resource, units=1)
        if quota_decision.effect != "allow":
            raise ControlPlaneError.conflict(
                f"quota {quota_decision.effect}: {quota_decision.reason}",
                extensions=quota_decision.to_dict(),
            )

    if require_attestations:
        if attestations is None:
            raise ControlPlaneError(
                "attestation store required",
                code="PMCP503",
                status=503,
                type="etlantic.control_plane/unavailable",
                title="Unavailable",
            )
        results = attestations.verify_plan(
            ctx,
            plan_fingerprint=plan_fingerprint,
            revision_id=revision_id or plan_fingerprint,
            policy_fingerprint=(
                decision.policy_fingerprint if decision else "unsigned"
            ),
            plugin_fingerprints=plugin_fingerprints or (),
            sbom_digest=sbom_digest,
        )
        require_verified(results)

    if audit is not None:
        audit.append(
            ctx,
            action="pre_submit",
            resource=plan_fingerprint,
            decision_refs=([decision.decision_id] if decision is not None else []),
            metadata={
                "policy_fingerprint": (
                    decision.policy_fingerprint if decision else None
                ),
                "quota_effect": (quota_decision.effect if quota_decision else None),
            },
        )
    return decision, quota_decision


def gate_pre_promote(
    ctx: ControlPlaneContext,
    *,
    policy: PolicyProvider,
    approvals: ApprovalStore,
    audit: AuditEvidenceStore | None = None,
    plan_fingerprint: str,
    revision_id: str,
) -> PolicyDecision:
    """Promotion requires current policy allow or satisfied SoD approval."""
    decision = evaluate_policy(
        policy,
        ctx,
        hook="pre_promote",
        plan_fingerprint=plan_fingerprint,
        revision_id=revision_id,
        required=True,
    )
    assert decision is not None
    if decision_allows(decision):
        if audit is not None:
            audit.append(
                ctx,
                action="pre_promote",
                resource=revision_id,
                decision_refs=[decision.decision_id],
            )
        return decision
    enforce_policy_decision(decision, approvals=approvals, ctx=ctx)
    if audit is not None:
        audit.append(
            ctx,
            action="pre_promote",
            resource=revision_id,
            decision_refs=[decision.decision_id],
            metadata={"via": "approval"},
        )
    return decision


def gate_pre_plan(
    ctx: ControlPlaneContext,
    *,
    policy: PolicyProvider | None,
    attributes: Mapping[str, Any] | None = None,
    required: bool = False,
) -> PolicyDecision | None:
    """Pre-plan policy gate (optimizer/compiler must not cross constraints)."""
    decision = evaluate_policy(
        policy,
        ctx,
        hook="pre_plan",
        attributes=attributes,
        required=required,
    )
    enforce_policy_decision(decision)
    if (
        decision is not None
        and attributes
        and decision.constraints.crosses_boundary(
            target_region=(
                str(attributes["target_region"])
                if attributes.get("target_region")
                else None
            ),
            egress_destination=(
                str(attributes["egress_destination"])
                if attributes.get("egress_destination")
                else None
            ),
        )
    ):
        raise ControlPlaneError.forbidden(
            "plan would cross governance boundary",
            extensions={"hook": "pre_plan"},
        )
    return decision


__all__ = [
    "enforce_policy_decision",
    "evaluate_policy",
    "gate_pre_plan",
    "gate_pre_promote",
    "gate_pre_submit",
]
