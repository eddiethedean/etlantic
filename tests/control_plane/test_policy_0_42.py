"""CP4 policy and approval unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    MemoryApprovalStore,
    MemoryPolicyProvider,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    gate_pre_submit,
)
from etlantic.testing import run_policy_conformance_suite


def ctx(subject: str = "alice") -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject, issuer="tests"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "workspace-a"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )


def test_policy_conformance_suite() -> None:
    run_policy_conformance_suite()


def test_self_approval_rejected() -> None:
    store = MemoryApprovalStore()
    c = ctx()
    req = store.create(
        c,
        hook="pre_promote",
        plan_fingerprint="p1",
        policy_fingerprint="pol1",
    )
    with pytest.raises(ControlPlaneError):
        store.decide(c, approval_id=req.approval_id, approve=True)


def test_expired_approval() -> None:
    store = MemoryApprovalStore()
    c = ctx()
    req = store.create(
        c,
        hook="pre_promote",
        plan_fingerprint="p1",
        policy_fingerprint="pol1",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    got = store.get(c, approval_id=req.approval_id)
    assert got.status == "expired"


def test_pre_submit_deny() -> None:
    policy = MemoryPolicyProvider()
    policy.set_rule("pre_submit", "deny")
    with pytest.raises(ControlPlaneError):
        gate_pre_submit(
            ctx(),
            policy=policy,
            plan_fingerprint="plan",
            require_policy=True,
        )


def test_policy_fingerprint_stable() -> None:
    policy = MemoryPolicyProvider()
    c = ctx()
    a = policy.decide(c, hook="pre_plan", plan_fingerprint="plan")
    b = policy.decide(c, hook="pre_plan", plan_fingerprint="plan")
    assert a.policy_fingerprint == b.policy_fingerprint
