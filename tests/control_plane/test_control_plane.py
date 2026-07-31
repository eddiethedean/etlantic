"""Control-plane identity, isolation, authz, and idempotency tests."""

from __future__ import annotations

from typing import Any

import pytest

from etlantic.control_plane import (
    AcceptReceipt,
    AuthzDecision,
    ControlPlaneContext,
    ControlPlaneError,
    ControlPlaneEvent,
    CorrelationKey,
    EnvironmentRef,
    IdempotencyKey,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryEventStore,
    MemorySubmissionStore,
    Principal,
    ProblemDetails,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    authorized_get_definition,
    map_deny_disclosure,
)
from etlantic.control_plane.errors import CONTROL_PLANE_ERROR_SCHEMA
from etlantic.control_plane.models import (
    ACCEPT_RECEIPT_SCHEMA,
    CONTROL_PLANE_CONTEXT_SCHEMA,
    CONTROL_PLANE_EVENT_SCHEMA,
)


def _ctx(
    *,
    tenant: str = "tenant-a",
    workspace: str = "ws-1",
    subject: str = "user-a",
    idempotency: str | None = None,
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(
            subject=subject, issuer="https://issuer.example", kind="human"
        ),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
        correlation_key=CorrelationKey(value="corr-1"),
        idempotency_key=(
            IdempotencyKey(value=idempotency) if idempotency is not None else None
        ),
        request_id="req-1",
    )


def test_context_round_trip_stable() -> None:
    ctx = _ctx(idempotency="idem-1")
    payload = ctx.to_dict()
    assert payload["schema"] == CONTROL_PLANE_CONTEXT_SCHEMA
    restored = ControlPlaneContext.from_dict(payload)
    assert restored.to_dict() == payload
    assert restored.scope_key == ("tenant-a", "ws-1")


def test_accept_receipt_and_event_round_trip() -> None:
    receipt = AcceptReceipt(
        acceptance_id="acc-1",
        submission_id="sub-1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        idempotency_key="idem-1",
        created_at="2026-07-31T00:00:00Z",
    )
    assert receipt.to_dict()["schema"] == ACCEPT_RECEIPT_SCHEMA
    assert AcceptReceipt.from_dict(receipt.to_dict()).to_dict() == receipt.to_dict()

    event = ControlPlaneEvent(
        event_id="evt-1",
        sequence=1,
        cursor="cursor-1",
        kind="run.accepted",
        created_at="2026-07-31T00:00:00Z",
        payload={"status": "accepted"},
    )
    assert event.to_dict()["schema"] == CONTROL_PLANE_EVENT_SCHEMA
    assert ControlPlaneEvent.from_dict(event.to_dict()).to_dict() == event.to_dict()


def test_problem_details_round_trip() -> None:
    problem = ProblemDetails(
        type="etlantic.control_plane/not_found",
        title="Not Found",
        status=404,
        detail="Resource not found",
        code="PMCP404",
    )
    payload = problem.to_dict()
    assert payload["schema"] == CONTROL_PLANE_ERROR_SCHEMA
    assert ProblemDetails.from_dict(payload).to_dict() == payload
    err = ControlPlaneError.not_found("gone")
    assert err.to_dict()["status"] == 404


def test_context_rejects_workspace_tenant_mismatch() -> None:
    with pytest.raises(ValueError, match=r"workspace\.tenant_id"):
        ControlPlaneContext(
            principal=Principal(subject="u"),
            tenant=TenantRef(tenant_id="t1"),
            workspace=WorkspaceRef(tenant_id="t2", workspace_id="w"),
            environment=EnvironmentRef(name="development"),
            security_domain=SecurityDomain(domain_id="d"),
        )


def test_serialized_context_has_no_secrets() -> None:
    ctx = _ctx()
    blob = str(ctx.to_dict())
    forbidden = (
        "password",
        "secret",
        "token",
        "credential",
        "api_key",
        "Authorization",
        "Bearer",
    )
    lowered = blob.lower()
    for word in forbidden:
        assert word.lower() not in lowered
    # Structure uses refs / opaque keys only.
    assert set(ctx.to_dict()) == {
        "schema",
        "principal",
        "tenant",
        "workspace",
        "environment",
        "security_domain",
        "correlation_key",
        "idempotency_key",
        "request_id",
    }


def test_two_tenant_two_workspace_isolation() -> None:
    repo = MemoryDefinitionRepository()
    events = MemoryEventStore()
    submissions = MemorySubmissionStore()

    a1 = _ctx(tenant="tenant-a", workspace="ws-1", subject="a")
    a2 = _ctx(tenant="tenant-a", workspace="ws-2", subject="a")
    b1 = _ctx(tenant="tenant-b", workspace="ws-1", subject="b")

    repo.put(a1, "pipe", {"name": "a1"})
    repo.put(a2, "pipe", {"name": "a2"})
    repo.put(b1, "pipe", {"name": "b1"})

    assert repo.get(a1, "pipe")["name"] == "a1"
    assert repo.get(a2, "pipe")["name"] == "a2"
    assert repo.get(b1, "pipe")["name"] == "b1"
    assert list(repo.list(a1)) == ["pipe"]

    with pytest.raises(KeyError):
        repo.get(a1, "missing")

    # Cross-tenant: a1 must not see b1's exclusive definition id.
    repo.put(b1, "secret-pipe", {"name": "secret"})
    with pytest.raises(KeyError):
        repo.get(a1, "secret-pipe")
    assert "secret-pipe" not in repo.list(a1)
    assert "secret-pipe" not in repo.list(a2)

    # Same tenant, different workspace isolation.
    repo.put(a1, "only-a1", {"name": "only"})
    with pytest.raises(KeyError):
        repo.get(a2, "only-a1")
    assert "only-a1" not in repo.list(a2)

    events.append(a1, kind="run.accepted", payload={"id": "1"})
    events.append(b1, kind="run.accepted", payload={"id": "2"})
    a_events = events.list_after_cursor(a1, None)
    b_events = events.list_after_cursor(b1, None)
    assert len(a_events) == 1
    assert a_events[0].payload == {"id": "1"}
    assert len(b_events) == 1
    assert b_events[0].payload == {"id": "2"}

    submissions.accept(a1, idempotency_key="k1", payload={"definition_id": "pipe"})
    assert submissions.lookup_idempotency(b1, "k1") is None
    assert submissions.lookup_idempotency(a2, "k1") is None
    assert submissions.lookup_idempotency(a1, "k1") is not None


def test_authorizer_deny_before_get_does_not_call_store() -> None:
    class SpyRepo(MemoryDefinitionRepository):
        def __init__(self) -> None:
            super().__init__()
            self.get_calls = 0

        def get(self, ctx: ControlPlaneContext, definition_id: str) -> Any:
            self.get_calls += 1
            return super().get(ctx, definition_id)

    repo = SpyRepo()
    repo.put(_ctx(), "pipe", {"name": "x"})
    authz = MemoryAuthorizer()  # deny by default

    with pytest.raises(ControlPlaneError) as caught:
        authorized_get_definition(authz, repo, _ctx(), "pipe")

    assert caught.value.status == 404
    assert repo.get_calls == 0


def test_authorizer_in_scope_forbidden_disclosure() -> None:
    decision = AuthzDecision(allowed=False, reason="no edit", disclosure="forbidden")
    assert map_deny_disclosure(decision, resource_in_caller_scope=True) == "forbidden"
    assert (
        map_deny_disclosure(
            AuthzDecision(allowed=False), resource_in_caller_scope=False
        )
        == "not_found"
    )


def test_idempotency_same_key_same_receipt() -> None:
    store = MemorySubmissionStore()
    ctx = _ctx()
    first = store.accept(
        ctx,
        idempotency_key="idem-42",
        payload={"definition_id": "pipe"},
    )
    second = store.accept(
        ctx,
        idempotency_key="idem-42",
        payload={"definition_id": "pipe"},
    )
    assert first == second
    assert first.acceptance_id == second.acceptance_id
    assert first.submission_id == second.submission_id


def test_idempotency_conflict_on_different_payload() -> None:
    store = MemorySubmissionStore()
    ctx = _ctx()
    store.accept(ctx, idempotency_key="idem-42", payload={"definition_id": "a"})
    with pytest.raises(ControlPlaneError) as caught:
        store.accept(ctx, idempotency_key="idem-42", payload={"definition_id": "b"})
    assert caught.value.status == 409


def test_lazy_namespace_import() -> None:
    import etlantic as etl

    assert etl.control_plane.ControlPlaneContext is ControlPlaneContext
    assert etl.control_plane.__name__ == "etlantic.control_plane"
