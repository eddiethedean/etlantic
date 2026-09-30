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
    first = _accepted(
        store, ctx, key="first", request={"provider": "mock", "connection_id": "db"}
    )
    second = _accepted(
        store, ctx, key="second", request={"provider": "mock", "connection_id": "db"}
    )
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
    resource_denied_receipt = store.get_action_job(
        ctx, resource_denied.action_id
    ).to_dict()
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


def test_action_worker_executes_schema_and_preflight_handlers_with_typed_requests() -> (
    None
):
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
    assert all(
        store.get_action_job(ctx, job.action_id).status == "succeeded"
        for job in accepted
    )


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


def test_preview_requests_are_closed_and_bounded() -> None:
    from etlantic.control_plane.action_jobs import parse_connector_action_request

    with pytest.raises(ControlPlaneError):
        parse_connector_action_request(
            "connector.preview",
            {
                "provider": "mock",
                "connection_id": "saved-db",
                "resource_id": "table-a",
                "password": "inline-secret",
            },
        )
    with pytest.raises(ControlPlaneError):
        parse_connector_action_request(
            "connector.preview",
            {
                "provider": "mock",
                "connection_id": "saved-db",
                "resource_id": "table-a",
                "max_rows": 101,
            },
        )
    with pytest.raises(ControlPlaneError):
        parse_connector_action_request(
            "connector.preview",
            {
                "provider": "mock",
                "connection_id": "saved-db",
                "resource_id": "table-a",
                "redact_fields": ["email", "email"],
            },
        )
    with pytest.raises(ControlPlaneError):
        parse_connector_action_request(
            "connector.provision",
            {
                "provider": "mock",
                "connection_id": "saved-db",
                "resource_id": "table-a",
                "columns": [{"name": "id", "logical_type": "integer"}],
                "if_exists": "replace",
            },
        )


def test_preview_results_are_redacted_bounded_and_expire_separately() -> None:
    store = MemoryDurableWorkStore()
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.preview")
    observed: list[Mapping[str, Any]] = []

    async def preview(
        _action_ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        observed.append(request)
        return {
            "columns": [
                {"name": "id", "logical_type": "integer"},
                {"name": "email", "logical_type": "string", "sensitive": True},
                {"name": "note", "logical_type": "string"},
            ],
            "rows": [
                {"id": 1, "email": "private@example.test", "note": "first"},
                {"id": 2, "email": "other@example.test", "note": "second"},
                {"id": 3, "email": "third@example.test", "note": "third"},
            ],
        }

    bounded = _accepted(
        store,
        ctx,
        key="preview-row-bound",
        action="connector.preview",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "table-a",
            "max_rows": 2,
            "max_bytes": 1024,
            "redact_fields": ["note"],
        },
    )
    byte_limited = _accepted(
        store,
        ctx,
        key="preview-byte-bound",
        action="connector.preview",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "table-b",
            "max_rows": 10,
            "max_bytes": 256,
        },
    )

    async def byte_preview(
        _action_ctx: ControlPlaneContext, _request: Mapping[str, Any]
    ) -> dict[str, Any]:
        return {
            "columns": [{"name": "payload", "logical_type": "string"}],
            "rows": [{"payload": "x" * 300}, {"payload": "y" * 300}],
        }

    worker = ActionExecutionHost(
        store,
        handlers={"connector.preview": preview},
        authorizer=authorizer,
        max_result_bytes=2048,
        max_result_items=10,
        preview_result_ttl_seconds=60,
    )
    byte_worker = ActionExecutionHost(
        store,
        handlers={"connector.preview": byte_preview},
        authorizer=authorizer,
        max_result_bytes=2048,
        preview_result_ttl_seconds=60,
    )
    assert worker.tick(ctx, limit=1) == 1
    bounded_receipt = store.get_action_job(ctx, bounded.action_id).to_dict()
    assert bounded_receipt["status"] == "succeeded"
    assert bounded_receipt["result"]["truncated"] is True
    assert len(bounded_receipt["result"]["rows"]) == 2
    assert all(row["email"] == "***" for row in bounded_receipt["result"]["rows"])
    assert all(row["note"] == "***" for row in bounded_receipt["result"]["rows"])
    assert observed[0]["max_rows"] == 2
    assert observed[0]["max_bytes"] == 1024
    assert bounded_receipt["result_expires_at"] is not None
    assert byte_worker.tick(ctx) == 1
    byte_receipt = store.get_action_job(ctx, byte_limited.action_id).to_dict()
    assert byte_receipt["status"] == "succeeded"
    assert byte_receipt["result"]["truncated"] is True
    encoded = json.dumps(
        byte_receipt["result"], sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert len(encoded) <= 256

    expired_at = datetime.now(UTC) + timedelta(minutes=2)
    assert store.cleanup_expired_action_results(ctx, limit=10, now=expired_at) == 2
    expired = store.get_action_job(ctx, bounded.action_id)
    assert expired.status == "succeeded"
    assert expired.result_json is None
    assert expired.result_expires_at is not None
    assert expired.to_dict()["result"] is None


def test_failed_preview_action_does_not_require_a_result_retention_ttl() -> None:
    store = MemoryDurableWorkStore()
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.preview")
    job = _accepted(
        store,
        ctx,
        key="failed-preview",
        action="connector.preview",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "table-a",
        },
    )

    async def failure(
        _ctx: ControlPlaneContext, _request: Mapping[str, Any]
    ) -> dict[str, Any]:
        raise RuntimeError("secret-bearing provider error")

    worker = ActionExecutionHost(
        store,
        handlers={"connector.preview": failure},
        authorizer=authorizer,
    )
    assert worker.tick(ctx) == 1
    failed = store.get_action_job(ctx, job.action_id)
    assert failed.status == "failed"
    assert failed.error_code == "action_failed"
    assert failed.result_json is None
    assert failed.result_expires_at is None


def test_provision_and_cleanup_are_explicit_parent_linked_effects() -> None:
    store = MemoryDurableWorkStore()
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.provision")
    authorizer.grant(ctx, "connector.provision.cleanup")
    provision_calls: list[Mapping[str, Any]] = []
    cleanup_calls: list[Mapping[str, Any]] = []
    fake_effects: dict[str, str] = {}

    async def provision(
        _action_ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        provision_calls.append(request)
        resource_id = str(request["resource_id"])
        effect_id = fake_effects.setdefault(resource_id, f"effect-{resource_id}")
        return {
            "action_id": request["action_id"],
            "effect_id": effect_id,
            "resource_id": resource_id,
            "schema_fingerprint": request["schema_fingerprint"],
            "created": True,
            "cleanup_supported": True,
        }

    async def cleanup(
        _action_ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        cleanup_calls.append(request)
        resource_id = str(request["resource_id"])
        assert fake_effects[resource_id] == request["effect_id"]
        fake_effects.pop(resource_id)
        return {
            "action_id": request["action_id"],
            "effect_id": request["effect_id"],
            "resource_id": request["resource_id"],
            "cleanup_of": request["provision_action_id"],
            "removed": True,
        }

    provision_job = _accepted(
        store,
        ctx,
        key="explicit-provision",
        action="connector.provision",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "new-table",
            "target_kind": "table",
            "columns": [
                {"name": "id", "logical_type": "integer", "nullable": False},
                {"name": "label", "logical_type": "string"},
            ],
        },
    )
    provision_retry = _accepted(
        store,
        ctx,
        key="explicit-provision",
        action="connector.provision",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "new-table",
            "target_kind": "table",
            "columns": [
                {"name": "id", "logical_type": "integer", "nullable": False},
                {"name": "label", "logical_type": "string"},
            ],
        },
    )
    assert provision_retry.action_id == provision_job.action_id
    worker = ActionExecutionHost(
        store,
        handlers={
            "connector.provision": provision,
            "connector.provision.cleanup": cleanup,
        },
        authorizer=authorizer,
    )
    assert worker.tick(ctx, limit=1) == 1
    created = store.get_action_job(ctx, provision_job.action_id)
    provision_receipt = json.loads(created.result_json or "{}")
    assert created.status == "succeeded"
    assert provision_receipt["action_id"] == provision_job.action_id
    assert fake_effects == {"new-table": "effect-new-table"}
    assert len(provision_calls) == 1
    assert provision_calls[0]["mode"] == "create_only"
    assert provision_calls[0]["if_exists"] == "fail"
    assert len(provision_calls[0]["schema_fingerprint"]) == 64

    mismatched_cleanup = _accepted(
        store,
        ctx,
        key="mismatched-provision-cleanup",
        action="connector.provision.cleanup",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "different-table",
            "provision_action_id": provision_job.action_id,
        },
    )
    assert worker.tick(ctx, limit=1) == 1
    assert store.get_action_job(ctx, mismatched_cleanup.action_id).error_code == (
        "provision_parent_unavailable"
    )
    assert cleanup_calls == []

    cleanup_job = _accepted(
        store,
        ctx,
        key="compensate-explicit-provision",
        action="connector.provision.cleanup",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "new-table",
            "provision_action_id": provision_job.action_id,
        },
    )
    assert worker.tick(ctx, limit=1) == 1
    cleaned = store.get_action_job(ctx, cleanup_job.action_id)
    assert cleaned.status == "succeeded"
    assert cleanup_calls[0]["effect_id"] == "effect-new-table"
    assert (
        cleanup_calls[0]["schema_fingerprint"]
        == provision_receipt["schema_fingerprint"]
    )
    assert json.loads(cleaned.result_json or "{}")["cleanup_of"] == (
        provision_job.action_id
    )
    assert fake_effects == {}

    invalid_job = _accepted(
        store,
        ctx,
        key="invalid-provision-effect-receipt",
        action="connector.provision",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "invalid-table",
            "columns": [{"name": "id", "logical_type": "integer"}],
        },
    )

    async def mismatched_effect(
        _action_ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        return {
            "action_id": request["action_id"],
            "effect_id": "effect-invalid",
            "resource_id": request["resource_id"],
            "schema_fingerprint": request["schema_fingerprint"],
            "created": True,
            "cleanup_supported": True,
            "provider_payload": "private effect data",
        }

    invalid_worker = ActionExecutionHost(
        store,
        handlers={"connector.provision": mismatched_effect},
        authorizer=authorizer,
    )
    assert invalid_worker.tick(ctx) == 1
    invalid_receipt = store.get_action_job(ctx, invalid_job.action_id)
    assert invalid_receipt.status == "failed"
    assert invalid_receipt.error_code == "invalid_effect_receipt"
    assert invalid_receipt.result_json is None
    assert "private effect data" not in json.dumps(invalid_receipt.to_dict())


def test_cleanup_rejects_mismatched_or_foreign_provision_parent() -> None:
    store = MemoryDurableWorkStore()
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.provision.cleanup")
    invoked = False

    async def cleanup(
        _action_ctx: ControlPlaneContext, _request: Mapping[str, Any]
    ) -> dict[str, Any]:
        nonlocal invoked
        invoked = True
        return {"removed": True}

    foreign = _accepted(
        store,
        _context("another-owner"),
        key="foreign-provision",
        action="connector.provision",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "private-table",
            "columns": [{"name": "id", "logical_type": "integer"}],
        },
    )
    cleanup_job = _accepted(
        store,
        ctx,
        key="foreign-cleanup-attempt",
        action="connector.provision.cleanup",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "private-table",
            "provision_action_id": foreign.action_id,
        },
    )
    worker = ActionExecutionHost(
        store,
        handlers={"connector.provision.cleanup": cleanup},
        authorizer=authorizer,
    )
    assert worker.tick(ctx) == 2
    denied = store.get_action_job(ctx, cleanup_job.action_id)
    assert denied.status == "failed"
    assert denied.error_code == "authorization_denied"
    assert invoked is False

    missing = _accepted(
        store,
        ctx,
        key="missing-provision-cleanup",
        action="connector.provision.cleanup",
        request={
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "table-a",
            "provision_action_id": "missing-parent",
        },
    )
    assert worker.tick(ctx) == 1
    assert store.get_action_job(ctx, missing.action_id).error_code == (
        "authorization_denied"
    )
    assert invoked is False
