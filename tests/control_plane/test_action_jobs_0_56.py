"""Authorization, persistence semantics and bounded execution of action jobs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDurableWorkStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.runtime import ActionExecutionHost, ActionHandler


def _context(owner: str = "action-owner") -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(owner),
        tenant=TenantRef("action-tenant"),
        workspace=WorkspaceRef("action-tenant", "action-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("action-domain"),
    )


def _accepted(
    store: MemoryDurableWorkStore,
    ctx: ControlPlaneContext,
    *,
    key: str,
    request: dict[str, Any],
    action: str = "connector.test",
    now: datetime | None = None,
) -> Any:
    created = now or datetime.now(UTC)
    return store.accept_action_job(
        ctx,
        action=action,
        idempotency_key=key,
        request=request,
        deadline_at=(created + timedelta(minutes=2)).isoformat(),
    )


def test_action_job_acceptance_is_redacted_idempotent_and_owner_scoped() -> None:
    store = MemoryDurableWorkStore()
    ctx = _context()
    original = _accepted(
        store,
        ctx,
        key="connection-check",
        request={"provider": "mock", "connection_id": "local-db", "password": "hidden"},
    )
    repeated = _accepted(
        store,
        ctx,
        key="connection-check",
        request={"provider": "mock", "connection_id": "local-db", "password": "hidden"},
    )

    assert repeated.action_id == original.action_id
    assert "hidden" not in original.request_json
    assert json.loads(original.request_json)["password"] == "***"
    assert "request" not in original.to_dict()
    with pytest.raises(ControlPlaneError) as conflict:
        _accepted(
            store,
            ctx,
            key="connection-check",
            request={"provider": "mock", "connection_id": "different-db"},
        )
    assert conflict.value.status == 409
    with pytest.raises(ControlPlaneError) as cross_owner:
        store.get_action_job(_context("other-owner"), original.action_id)
    assert cross_owner.value.status == 404


def test_action_job_claim_fencing_and_receipt_pagination() -> None:
    store = MemoryDurableWorkStore()
    ctx = _context()
    first = _accepted(store, ctx, key="first", request={"provider": "mock", "connection_id": "db"})
    second = _accepted(store, ctx, key="second", request={"provider": "mock", "connection_id": "db"})
    page = store.list_action_jobs(ctx, limit=1)
    assert len(page) == 1
    assert page[0].action_id == first.action_id
    next_page = store.list_action_jobs(
        ctx, after=(page[0].created_at, page[0].action_id), limit=1
    )
    assert [job.action_id for job in next_page] == [second.action_id]

    now = datetime.now(UTC) + timedelta(seconds=1)
    stale = store.claim_action_job(ctx, worker_id="worker-a", lease_seconds=1, now=now)
    assert stale is not None
    takeover_at = now + timedelta(seconds=2)
    current = store.claim_action_job(
        ctx, worker_id="worker-b", lease_seconds=10, now=takeover_at
    )
    assert current is not None
    assert current.action_id == stale.action_id
    assert current.fencing_token == stale.fencing_token + 1
    with pytest.raises(ControlPlaneError, match="stale"):
        store.finish_action_job(
            ctx,
            stale.action_id,
            worker_id="worker-a",
            fencing_token=stale.fencing_token,
            status="succeeded",
            now=takeover_at,
        )
    finished = store.finish_action_job(
        ctx,
        current.action_id,
        worker_id="worker-b",
        fencing_token=current.fencing_token,
        status="succeeded",
        result={"ok": True, "token": "hidden"},
        now=takeover_at + timedelta(seconds=1),
    )
    assert finished.status == "succeeded"
    assert finished.to_dict()["result"]["token"] == "***"

    failed_store = MemoryDurableWorkStore()
    failed_job = _accepted(
        failed_store,
        ctx,
        key="safe-error-code",
        request={"provider": "mock", "connection_id": "db"},
    )
    failed_claim = failed_store.claim_action_job(
        ctx, worker_id="worker-c", lease_seconds=10
    )
    assert failed_claim is not None
    assert failed_claim.action_id == failed_job.action_id
    failed = failed_store.finish_action_job(
        ctx,
        failed_claim.action_id,
        worker_id="worker-c",
        fencing_token=failed_claim.fencing_token,
        status="failed",
        error_code="PRIVATE-TOKEN-NEVER-DISCLOSE",
    )
    assert failed.to_dict()["error_code"] == "action_failed"


def test_action_worker_rechecks_authorization_and_redacts_bounded_receipts() -> None:
    store = MemoryDurableWorkStore()
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.test")
    calls: list[ControlPlaneContext] = []

    async def test_connection(
        action_ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        assert request == {"provider": "mock", "connection_id": "db"}
        calls.append(action_ctx)
        return {"ok": True, "token": "provider-secret", "items": ["source"]}

    job = _accepted(
        store,
        ctx,
        key="worker-run",
        request={"provider": "mock", "connection_id": "db"},
    )
    worker = ActionExecutionHost(
        store,
        handlers={"connector.test": test_connection},
        authorizer=authorizer,
    )
    assert worker.tick(ctx) == 1
    completed = store.get_action_job(ctx, job.action_id)
    assert completed.status == "succeeded"
    assert completed.to_dict()["result"] == {
        "items": ["source"],
        "ok": True,
        "token": "***",
    }
    assert calls[0].principal.subject == ctx.principal.subject
    assert calls[0].tenant == ctx.tenant

    denied = _accepted(
        store,
        ctx,
        key="revoked-run",
        request={"provider": "mock", "connection_id": "db"},
    )
    authorizer.grants.clear()
    assert worker.tick(ctx) == 1
    denied_receipt = store.get_action_job(ctx, denied.action_id).to_dict()
    assert denied_receipt["status"] == "failed"
    assert denied_receipt["error_code"] == "authorization_denied"
    assert len(calls) == 1

    resource_denied = _accepted(
        store,
        ctx,
        key="resource-revoked-run",
        request={"provider": "mock", "connection_id": "db"},
    )
    authorizer.grant(ctx, "connector.test")
    authorizer.forbidden_resources.add(
        (
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            "connector.test",
            "connection:db",
        )
    )
    assert worker.tick(ctx) == 1
    resource_denied_receipt = store.get_action_job(ctx, resource_denied.action_id).to_dict()
    assert resource_denied_receipt["status"] == "failed"
    assert resource_denied_receipt["error_code"] == "authorization_denied"
    assert len(calls) == 1


def test_action_worker_cancels_handler_at_deadline() -> None:
    store = MemoryDurableWorkStore()
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.test")
    cancelled = False
    created = datetime.now(UTC)
    job = store.accept_action_job(
        ctx,
        action="connector.test",
        idempotency_key="timeout-run",
        request={"provider": "mock", "connection_id": "slow"},
        deadline_at=(created + timedelta(milliseconds=100)).isoformat(),
    )

    async def slow_connection(
        _ctx: ControlPlaneContext, _request: Mapping[str, Any]
    ) -> dict[str, Any]:
        nonlocal cancelled
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            cancelled = True
            raise
        return {"ok": True}

    worker = ActionExecutionHost(
        store,
        handlers={"connector.test": slow_connection},
        authorizer=authorizer,
        lease_seconds=2,
    )
    assert worker.tick(ctx) == 1
    timed_out = store.get_action_job(ctx, job.action_id)
    assert timed_out.status == "timed_out"
    assert timed_out.error_code == "deadline_exceeded"
    assert cancelled


def test_action_worker_executes_schema_and_preflight_handlers_with_typed_requests() -> None:
    store = MemoryDurableWorkStore()
    ctx = _context()
    authorizer = MemoryAuthorizer()
    calls: list[tuple[str, Mapping[str, Any]]] = []
    cases = (
        (
            "connector.schema.inspect",
            {"provider": "mock", "connection_id": "db", "max_fields": 3},
            ("connector:mock", "connection:db"),
        ),
        (
            "connector.preflight",
            {"definition_id": "definition-7", "revision_selector": "rev-2"},
            ("definition:definition-7",),
        ),
    )
    handlers: dict[str, ActionHandler] = {}
    accepted: list[Any] = []
    for index, (action, request, _resources) in enumerate(cases):
        authorizer.grant(ctx, action)

        async def handler(
            _action_ctx: ControlPlaneContext,
            typed_request: Mapping[str, Any],
            *,
            _action: str = action,
        ) -> dict[str, Any]:
            calls.append((_action, typed_request))
            return {"ok": True}

        handlers[action] = handler
        accepted.append(
            _accepted(
                store,
                ctx,
                key=f"typed-action-{index}",
                request=request,
                action=action,
            )
        )

    worker: ActionExecutionHost = ActionExecutionHost(
        store, handlers=handlers, authorizer=authorizer
    )
    assert worker.tick(ctx, limit=2) == 2
    assert [(action, dict(request)) for action, request in calls] == [
        (action, request) for action, request, _resources in cases
    ]
    assert all(store.get_action_job(ctx, job.action_id).status == "succeeded" for job in accepted)


def test_action_worker_hides_provider_error_codes_and_bounds_nested_results() -> None:
    store = MemoryDurableWorkStore()
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.test")

    class ProviderFailure(Exception):
        code = "PASSWORD-NEVER-DISCLOSE"

    async def fail_with_provider_error(
        _ctx: ControlPlaneContext, _request: Mapping[str, Any]
    ) -> dict[str, Any]:
        raise ProviderFailure("provider reported private detail")

    failed = _accepted(
        store,
        ctx,
        key="provider-failure",
        request={"provider": "mock", "connection_id": "db"},
    )
    worker = ActionExecutionHost(
        store,
        handlers={"connector.test": fail_with_provider_error},
        authorizer=authorizer,
        max_result_items=1,
    )
    assert worker.tick(ctx) == 1
    failure_receipt = store.get_action_job(ctx, failed.action_id).to_dict()
    assert failure_receipt["error_code"] == "action_failed"
    assert "PASSWORD" not in json.dumps(failure_receipt)
    assert "private detail" not in json.dumps(failure_receipt)

    async def oversized_nested_result(
        _ctx: ControlPlaneContext, _request: Mapping[str, Any]
    ) -> dict[str, Any]:
        return {"result": {"rows": [1, 2]}}

    oversized = _accepted(
        store,
        ctx,
        key="nested-result-limit",
        request={"provider": "mock", "connection_id": "db-2"},
    )
    bounded_worker = ActionExecutionHost(
        store,
        handlers={"connector.test": oversized_nested_result},
        authorizer=authorizer,
        max_result_items=1,
    )
    assert bounded_worker.tick(ctx) == 1
    assert store.get_action_job(ctx, oversized.action_id).error_code == (
        "result_limit_exceeded"
    )
    with pytest.raises(ValueError, match="limit"):
        bounded_worker.tick(ctx, limit=101)
