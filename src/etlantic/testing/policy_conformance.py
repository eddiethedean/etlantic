"""CP4 policy / approval / quota conformance helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    GovernanceConstraints,
    MemoryApprovalStore,
    MemoryPolicyProvider,
    MemoryQuotaProvider,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    gate_pre_plan,
    gate_pre_promote,
    gate_pre_submit,
)


def _ctx(
    tenant: str = "tenant-a",
    workspace: str = "workspace-a",
    subject: str = "worker-a",
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject, issuer="conformance"),
        tenant=TenantRef(tenant),
        workspace=WorkspaceRef(tenant, workspace),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def run_policy_conformance_suite(
    policy: Any | None = None,
    approvals: Any | None = None,
    quotas: Any | None = None,
) -> None:
    """Exercise policy, approval SoD, and quota fail-closed invariants."""
    policy = policy or MemoryPolicyProvider()
    approvals = approvals or MemoryApprovalStore()
    quotas = quotas or MemoryQuotaProvider()

    ctx = _ctx()
    decision = policy.decide(ctx, hook="pre_plan", plan_fingerprint="plan-1")
    assert decision.effect == "allow"
    assert decision.policy_fingerprint

    # Outage fails closed.
    policy.unavailable = True
    try:
        policy.decide(ctx, hook="pre_submit")
        raise AssertionError("expected unavailable")
    except ControlPlaneError as exc:
        assert exc.status == 503
    policy.unavailable = False

    # Governance boundary.
    policy.constraints = GovernanceConstraints(
        residency_regions=("us-east",),
        egress_allowlist=("approved-sink",),
    )
    try:
        gate_pre_plan(
            ctx,
            policy=policy,
            attributes={"target_region": "eu-west"},
            required=True,
        )
        raise AssertionError("expected boundary deny")
    except ControlPlaneError:
        pass
    policy.constraints = GovernanceConstraints()

    # Approvals SoD.
    req = approvals.create(
        ctx,
        hook="pre_promote",
        plan_fingerprint="plan-1",
        policy_fingerprint=decision.policy_fingerprint,
        revision_id="rev-1",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    try:
        approvals.decide(ctx, approval_id=req.approval_id, approve=True)
        raise AssertionError("requester must not self-approve")
    except ControlPlaneError as exc:
        assert exc.status == 403

    approver = _ctx(subject="approver-b")
    approved = approvals.decide(approver, approval_id=req.approval_id, approve=True)
    assert approved.status == "approved"

    # Stale fingerprint.
    req2 = approvals.create(
        ctx,
        hook="pre_promote",
        plan_fingerprint="plan-2",
        policy_fingerprint="pol-2",
        revision_id="rev-2",
    )
    try:
        approvals.decide(
            approver,
            approval_id=req2.approval_id,
            approve=True,
            plan_fingerprint="plan-other",
        )
        raise AssertionError("expected stale")
    except ControlPlaneError:
        pass

    # Quotas.
    quotas.default_limits["concurrency"] = 1
    first = quotas.admit(ctx, resource="concurrency")
    assert first.effect == "allow"
    second = quotas.admit(ctx, resource="concurrency")
    assert second.effect == "deny"
    quotas.release(ctx, resource="concurrency")
    quotas.set_suspended(ctx, suspended=True)
    suspended = quotas.admit(ctx, resource="concurrency")
    assert suspended.effect == "suspended"
    quotas.set_suspended(ctx, suspended=False)

    quotas.unavailable = True
    try:
        quotas.admit(ctx, resource="concurrency")
        raise AssertionError("expected quota unavailable")
    except ControlPlaneError as exc:
        assert exc.status == 503
    quotas.unavailable = False

    # Pre-submit gate.
    policy.set_rule("pre_submit", "allow")
    d, q = gate_pre_submit(
        ctx,
        policy=policy,
        approvals=approvals,
        quotas=quotas,
        plan_fingerprint="plan-1",
        revision_id="rev-1",
        require_policy=True,
    )
    assert d is not None and q is not None and q.effect == "allow"

    # Promotion gate with approval.
    policy.set_rule("pre_promote", "require_approval")
    promo_decision = policy.decide(
        ctx, hook="pre_promote", plan_fingerprint="plan-1", revision_id="rev-1"
    )
    req3 = approvals.create(
        ctx,
        hook="pre_promote",
        plan_fingerprint="plan-1",
        policy_fingerprint=promo_decision.policy_fingerprint,
        revision_id="rev-1",
    )
    approvals.decide(approver, approval_id=req3.approval_id, approve=True)
    gate_pre_promote(
        ctx,
        policy=policy,
        approvals=approvals,
        plan_fingerprint="plan-1",
        revision_id="rev-1",
    )


__all__ = ["run_policy_conformance_suite"]
