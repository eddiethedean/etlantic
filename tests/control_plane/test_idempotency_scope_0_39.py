"""ADR-016 idempotency scope: principal + operation in the store key (0.39)."""

from __future__ import annotations

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)


def _ctx(*, subject: str = "alice") -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject=subject),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def test_alice_then_bob_same_key_independent_receipts() -> None:
    store = MemorySubmissionStore()
    alice = _ctx(subject="alice")
    bob = _ctx(subject="bob")
    payload = {"definition_id": "pipe", "n": 1}

    alice_result = store.accept(alice, idempotency_key="shared-key", payload=payload)
    bob_result = store.accept(bob, idempotency_key="shared-key", payload=payload)

    assert alice_result.created is True
    assert bob_result.created is True
    assert alice_result.receipt.acceptance_id != bob_result.receipt.acceptance_id
    assert alice_result.receipt.submission_id != bob_result.receipt.submission_id

    # Bob must not receive Alice's receipt on lookup or replay.
    assert store.lookup_idempotency(bob, "shared-key") == bob_result.receipt
    assert store.lookup_idempotency(alice, "shared-key") == alice_result.receipt
    replay = store.accept(bob, idempotency_key="shared-key", payload=payload)
    assert replay.created is False
    assert replay.receipt.acceptance_id == bob_result.receipt.acceptance_id
    assert replay.receipt.acceptance_id != alice_result.receipt.acceptance_id


def test_different_payload_same_principal_conflicts() -> None:
    store = MemorySubmissionStore()
    alice = _ctx(subject="alice")
    store.accept(alice, idempotency_key="idem-42", payload={"definition_id": "a"})
    with pytest.raises(ControlPlaneError) as caught:
        store.accept(alice, idempotency_key="idem-42", payload={"definition_id": "b"})
    assert caught.value.status == 409


def test_operation_scopes_idempotency() -> None:
    store = MemorySubmissionStore()
    ctx = _ctx()
    payload = {"definition_id": "pipe"}
    submit = store.accept(
        ctx,
        idempotency_key="k",
        payload=payload,
        operation="run.submit",
    )
    other = store.accept(
        ctx,
        idempotency_key="k",
        payload=payload,
        operation="run.cancel",
    )
    assert submit.created is True
    assert other.created is True
    assert submit.receipt.acceptance_id != other.receipt.acceptance_id
    assert store.lookup_idempotency(ctx, "k", operation="run.submit") is not None
    assert store.lookup_idempotency(ctx, "k", operation="run.cancel") is not None


def test_poll_accepted_filters_tenant_workspace() -> None:
    store = MemorySubmissionStore()
    a = ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )
    b = ControlPlaneContext(
        principal=Principal(subject="bob"),
        tenant=TenantRef(tenant_id="tenant-b"),
        workspace=WorkspaceRef(tenant_id="tenant-b", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )
    store.accept(a, idempotency_key="a1", payload={"definition_id": "pipe"})
    store.accept(b, idempotency_key="b1", payload={"definition_id": "pipe"})
    polled_a = store.poll_accepted(a, limit=10)
    polled_b = store.poll_accepted(b, limit=10)
    assert len(polled_a) == 1
    assert len(polled_b) == 1
    assert polled_a[0]["tenant_id"] == "tenant-a"
    assert polled_b[0]["tenant_id"] == "tenant-b"


def test_cancel_run_changed_only_on_first_transition() -> None:
    store = MemorySubmissionStore()
    ctx = _ctx()
    result = store.accept(ctx, idempotency_key="c1", payload={"definition_id": "pipe"})
    run_id = result.receipt.resource_id or result.receipt.submission_id
    record, changed = store.cancel_run(ctx, run_id)
    assert changed is True
    assert record["status"] == "cancel_requested"
    record2, changed2 = store.cancel_run(ctx, run_id)
    assert changed2 is False
    assert record2["status"] == "cancel_requested"
