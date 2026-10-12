"""CP4 policy and approval unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    MemoryApprovalStore,
    MemoryAuditEvidenceStore,
    MemoryPolicyProvider,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    gate_pre_execution,
    gate_pre_submit,
)
from etlantic.control_plane.attestation_memory import MemoryAttestationStore
from etlantic.control_plane.attestation_models import Attestation
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
    with pytest.raises(ControlPlaneError, match="requester cannot decide"):
        store.decide(c, approval_id=req.approval_id, approve=True)


def test_sod_issuer_mismatch_still_blocked() -> None:
    store = MemoryApprovalStore()
    requester = ctx("alice")
    req = store.create(
        requester,
        hook="pre_promote",
        plan_fingerprint="p1",
        policy_fingerprint="pol1",
    )
    same_subject_other_issuer = ControlPlaneContext(
        principal=Principal("alice", issuer="other-issuer"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "workspace-a"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )
    with pytest.raises(ControlPlaneError, match="requester cannot decide"):
        store.decide(
            same_subject_other_issuer,
            approval_id=req.approval_id,
            approve=True,
        )


def test_sod_self_deny_blocked() -> None:
    store = MemoryApprovalStore()
    c = ctx()
    req = store.create(
        c,
        hook="pre_promote",
        plan_fingerprint="p1",
        policy_fingerprint="pol1",
    )
    with pytest.raises(ControlPlaneError, match="requester cannot decide"):
        store.decide(c, approval_id=req.approval_id, approve=False)


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


def test_approved_approval_expires_before_pre_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from etlantic.control_plane import approval_memory

    clock = [datetime(2026, 10, 1, tzinfo=UTC)]
    monkeypatch.setattr(approval_memory, "_now", lambda: clock[0])
    requester = ctx()
    policy = MemoryPolicyProvider()
    policy.set_rule("pre_execution", "require_approval")
    approvals = MemoryApprovalStore()
    decision = policy.decide(
        requester,
        hook="pre_execution",
        plan_fingerprint="accepted-plan",
        revision_id="revision-1",
        resource="definition:pipeline-a",
    )
    expires_at = clock[0] + timedelta(minutes=5)
    request = approvals.create(
        requester,
        hook="pre_execution",
        plan_fingerprint="accepted-plan",
        policy_fingerprint=decision.policy_fingerprint,
        revision_id="revision-1",
        expires_at=expires_at,
    )
    approvals.decide(ctx("reviewer"), approval_id=request.approval_id, approve=True)

    assert (
        gate_pre_execution(
            requester,
            policy=policy,
            approvals=approvals,
            plan_fingerprint="accepted-plan",
            revision_id="revision-1",
            resource="definition:pipeline-a",
            required=True,
        )
        is not None
    )

    clock[0] = expires_at
    with pytest.raises(
        ControlPlaneError, match="cannot revoke approval in status expired"
    ):
        approvals.revoke(requester, approval_id=request.approval_id)
    assert approvals.get(requester, approval_id=request.approval_id).status == "expired"
    with pytest.raises(ControlPlaneError, match="approval required and not satisfied"):
        gate_pre_execution(
            requester,
            policy=policy,
            approvals=approvals,
            plan_fingerprint="accepted-plan",
            revision_id="revision-1",
            resource="definition:pipeline-a",
            required=True,
        )


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


def test_pre_execution_rechecks_current_policy_and_audits_allow() -> None:
    c = ctx()
    policy = MemoryPolicyProvider()
    audit = MemoryAuditEvidenceStore()
    accepted_fingerprint = policy.decide(
        c,
        hook="pre_submit",
        plan_fingerprint="effective-plan",
        revision_id="revision-1",
        resource="definition:pipeline-a",
    ).policy_fingerprint

    decision = gate_pre_execution(
        c,
        policy=policy,
        audit=audit,
        plan_fingerprint="effective-plan",
        revision_id="revision-1",
        resource="definition:pipeline-a",
        required=True,
    )
    assert decision is not None
    assert decision.hook == "pre_execution"
    assert decision.policy_fingerprint != accepted_fingerprint
    entries = audit.list(c)
    assert len(entries) == 1
    assert entries[0].action == "pre_execution"
    assert entries[0].metadata["outcome"] == "allow"
    assert audit.verify_chain(c)

    # The same accepted work must be stopped when policy changes after submit.
    policy.set_rule("pre_execution", "deny")
    with pytest.raises(ControlPlaneError, match="policy denied"):
        gate_pre_execution(
            c,
            policy=policy,
            audit=audit,
            plan_fingerprint="effective-plan",
            revision_id="revision-1",
            resource="definition:pipeline-a",
            required=True,
        )
    entries = audit.list(c)
    assert len(entries) == 2
    assert entries[1].action == "pre_execution"
    assert entries[1].metadata["outcome"] == "deny"
    assert audit.verify_chain(c)


def test_pre_execution_without_required_policy_fails_closed() -> None:
    with pytest.raises(ControlPlaneError) as unavailable:
        gate_pre_execution(
            ctx(),
            policy=None,
            plan_fingerprint="effective-plan",
            revision_id="revision-1",
            resource="definition:pipeline-a",
            required=True,
        )
    assert unavailable.value.status == 503


def test_pre_execution_rechecks_approval_before_effects() -> None:
    c = ctx()
    policy = MemoryPolicyProvider()
    policy.set_rule("pre_execution", "require_approval")
    approvals = MemoryApprovalStore()
    with pytest.raises(ControlPlaneError, match="approval required and not satisfied"):
        gate_pre_execution(
            c,
            policy=policy,
            approvals=approvals,
            plan_fingerprint="effective-plan",
            revision_id="revision-1",
            resource="definition:pipeline-a",
            required=True,
        )

    decision = policy.decide(
        c,
        hook="pre_execution",
        plan_fingerprint="effective-plan",
        revision_id="revision-1",
        resource="definition:pipeline-a",
    )
    request = approvals.create(
        c,
        hook="pre_execution",
        plan_fingerprint="effective-plan",
        policy_fingerprint=decision.policy_fingerprint,
        revision_id="revision-1",
    )
    approvals.decide(ctx("reviewer"), approval_id=request.approval_id, approve=True)
    allowed = gate_pre_execution(
        c,
        policy=policy,
        approvals=approvals,
        plan_fingerprint="effective-plan",
        revision_id="revision-1",
        resource="definition:pipeline-a",
        required=True,
    )
    assert allowed is not None
    assert allowed.effect == "require_approval"


def test_policy_fingerprint_stable() -> None:
    policy = MemoryPolicyProvider()
    c = ctx()
    a = policy.decide(c, hook="pre_plan", plan_fingerprint="plan")
    b = policy.decide(c, hook="pre_plan", plan_fingerprint="plan")
    assert a.policy_fingerprint == b.policy_fingerprint


def test_pre_submit_attestations_are_fresh_and_bound_to_effective_fingerprint() -> None:
    c = ctx()
    store = MemoryAttestationStore.for_tests()
    for kind, subject in (
        ("plan", "effective-plan"),
        ("revision", "rev-1"),
        ("policy_bundle", "unsigned"),
    ):
        store.put(
            c,
            attestation=store.make_attestation(
                c, kind=kind, subject_fingerprint=subject
            ),
        )

    gate_pre_submit(
        c,
        policy=None,
        attestations=store,
        plan_fingerprint="raw-plan",
        effective_fingerprint="effective-plan",
        revision_id="rev-1",
        require_attestations=True,
        attestation_max_age_seconds=60,
    )


def test_plan_attestation_created_at_is_signed_and_stale_evidence_fails_closed() -> (
    None
):
    from dataclasses import replace
    from datetime import UTC, datetime

    c = ctx()
    store = MemoryAttestationStore.for_tests()
    stale = Attestation(
        attestation_id="stale-plan",
        kind="plan",
        subject_fingerprint="plan",
        signature="",
        signer_id="tests",
        tenant_id=c.tenant.tenant_id,
        workspace_id=c.workspace.workspace_id,
        environment=c.environment.name,
        created_at=datetime.now(UTC) - timedelta(hours=2),
    )
    store.put(c, attestation=store.sign(stale))
    for kind, subject in (("revision", "rev"), ("policy_bundle", "policy")):
        store.put(
            c,
            attestation=store.make_attestation(
                c, kind=kind, subject_fingerprint=subject
            ),
        )

    results = store.verify_plan(
        c,
        plan_fingerprint="plan",
        revision_id="rev",
        policy_fingerprint="policy",
        plugin_fingerprints=(),
        max_age_seconds=60,
    )
    assert [result.ok for result in results] == [False, True, True]
    assert results[0].reasons == ("stale plan attestation",)

    # Timestamp edits invalidate the signature, so freshness cannot be reset
    # by rewriting the public created_at field.
    with pytest.raises(ControlPlaneError, match="invalid attestation signature"):
        store.put(c, attestation=replace(stale, created_at=datetime.now(UTC)))
