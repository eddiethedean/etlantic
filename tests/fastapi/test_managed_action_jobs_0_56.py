"""HTTP admission and SQLModel persistence for isolated connector actions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import sqlalchemy
from fastapi.testclient import TestClient

from etlantic import Profile
from etlantic.control_plane import (
    Authorizer,
    AuthzDecision,
    ControlPlaneContext,
    MemoryAuthorizer,
    Principal,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic_fastapi import (
    ManagedBackend,
    ManagedBackendConfig,
    create_app,
    create_managed_backend,
    static_context_factory,
)
from etlantic_sqlmodel.migrations import upgrade


def _context() -> ControlPlaneContext:
    from etlantic.control_plane import (
        EnvironmentRef,
        SecurityDomain,
        TenantRef,
        WorkspaceRef,
    )

    return ControlPlaneContext(
        principal=Principal("action-owner"),
        tenant=TenantRef("action-tenant"),
        workspace=WorkspaceRef("action-tenant", "action-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("action-domain"),
    )


def _config(
    tmp_path: Path,
    action_handler: Any,
    *,
    action: str = "connector.test",
    preview_result_ttl_seconds: int = 60 * 60,
    additional_action_handlers: Mapping[str, Any] | None = None,
) -> ManagedBackendConfig:
    database_url = f"sqlite:///{tmp_path / 'actions.sqlite'}"
    engine = sqlalchemy.create_engine(database_url)
    try:
        assert upgrade(engine) == "012_bounded_event_tombstone_retention_0_56"
    finally:
        engine.dispose()
    return ManagedBackendConfig(
        database_url=database_url,
        store_id="managed-action-jobs",
        profile=Profile(
            name="managed-action-jobs",
            security_mode="development",
            plugin_allowlist={"etlantic": None},
        ),
        action_handlers={
            action: action_handler,
            **dict(additional_action_handlers or {}),
        },
        preview_result_ttl_seconds=preview_result_ttl_seconds,
    )


def test_managed_action_handlers_fail_closed_during_configuration() -> None:
    with pytest.raises(ValueError, match="unsupported action"):
        ManagedBackendConfig(
            database_url="sqlite://",
            action_handlers={"connector.testtypo": _async_action_result},
        )

    def sync_handler(
        _ctx: ControlPlaneContext, _request: Mapping[str, Any]
    ) -> dict[str, bool]:
        return {"ok": True}

    with pytest.raises(TypeError, match="must be asynchronous"):
        ManagedBackendConfig(
            database_url="sqlite://",
            action_handlers={"connector.test": cast(Any, sync_handler)},
        )


async def _async_action_result(
    _ctx: ControlPlaneContext, _request: Mapping[str, Any]
) -> dict[str, Any]:
    return {"ok": True}


def _backend(config: ManagedBackendConfig, authorizer: Authorizer) -> ManagedBackend:
    return create_managed_backend(
        config,
        authorizer=authorizer,
        context_factory=static_context_factory(
            tenant_id="action-tenant",
            workspace_id="action-workspace",
            environment="test",
            security_domain="action-domain",
        ),
    )


def test_managed_http_action_jobs_are_durable_scoped_and_paginated(
    tmp_path: Path,
) -> None:
    ctx = _context()
    authorizer = MemoryAuthorizer()
    for action in (
        "connector.test",
        "connector.action.read",
        "connector.action.list",
    ):
        authorizer.grant(ctx, action)
    handler_contexts: list[ControlPlaneContext] = []

    async def test_connection(
        action_ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        handler_contexts.append(action_ctx)
        return {
            "ok": True,
            "provider": request["provider"],
            "token": "provider-secret",
        }

    config = _config(tmp_path, test_connection)
    backend = _backend(config, authorizer)
    first_app = create_app(backend.api, with_lifespan=False)
    client_type = cast(Any, TestClient)
    client = client_type(first_app)
    headers = {"X-Principal": "action-owner"}
    try:
        service = backend.api.managed_service
        assert service is not None
        with pytest.raises(ControlPlaneError) as inline_secret:
            service.submit_connector_action(
                ctx,
                "connector.test",
                {
                    "provider": "mock",
                    "connection_id": "saved-db",
                    "password": "never-persist-this",
                },
                idempotency_key="inline-secret",
            )
        assert inline_secret.value.status == 400

        first = service.submit_connector_action(
            ctx,
            "connector.test",
            {"provider": "mock", "connection_id": "saved-db"},
            idempotency_key="headless-check",
        )
        repeated = service.submit_connector_action(
            ctx,
            "connector.test",
            {"provider": "mock", "connection_id": "saved-db"},
            idempotency_key="headless-check",
        )
        assert first["action_id"] == repeated["action_id"]
        with pytest.raises(ControlPlaneError) as conflict:
            service.submit_connector_action(
                ctx,
                "connector.test",
                {"provider": "mock", "connection_id": "different-db"},
                idempotency_key="headless-check",
            )
        assert conflict.value.status == 409

        for connection_id in ("http-db-1", "http-db-2"):
            submitted = client.post(
                "/v1/connector-actions/connector.test",
                headers={**headers, "Idempotency-Key": connection_id},
                json={
                    "payload": {
                        "provider": "mock",
                        "connection_id": connection_id,
                    },
                    "deadline_seconds": 10,
                },
            )
            assert submitted.status_code == 202
            assert submitted.headers["Location"] == (
                f"/v1/connector-actions/{submitted.json()['action_id']}"
            )

        first_page = client.get("/v1/connector-actions?limit=1", headers=headers)
        assert first_page.status_code == 200
        assert len(first_page.json()["items"]) == 1
        assert first_page.json()["has_more"] is True
        second_page = client.get(
            f"/v1/connector-actions?limit=1&cursor={first_page.json()['next_cursor']}",
            headers=headers,
        )
        assert second_page.status_code == 200
        assert len(second_page.json()["items"]) == 1
        assert (
            second_page.json()["items"][0]["action_id"]
            != (first_page.json()["items"][0]["action_id"])
        )

        with pytest.raises(ControlPlaneError) as cross_owner:
            service.get_connector_action(
                replace(ctx, principal=Principal("other-owner")),
                first["action_id"],
            )
        assert cross_owner.value.status == 404
    finally:
        backend.close()

    # The accepted receipt and payload survive backend restart in the CP3
    # transactional snapshot. A separate worker, outside the HTTP app, runs it.
    restarted = _backend(config, authorizer)
    try:
        service = restarted.api.managed_service
        assert service is not None
        before_worker = service.get_connector_action(ctx, first["action_id"])
        assert before_worker["status"] == "queued"
        assert "request" not in before_worker
        assert restarted.create_action_execution_host().tick(ctx, limit=10) == 3
        after_worker = service.get_connector_action(ctx, first["action_id"])
        assert after_worker["status"] == "succeeded"
        assert after_worker["result"] == {
            "ok": True,
            "provider": "mock",
            "token": "***",
        }
        assert len(handler_contexts) == 3
        assert all(
            item.principal.subject == "action-owner" for item in handler_contexts
        )
    finally:
        restarted.close()


def test_connector_catalog_can_run_as_an_authorized_action_job(
    tmp_path: Path,
) -> None:
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.catalog")
    authorizer.grant(ctx, "connector.action.read")

    async def unused_test_handler(
        _ctx: ControlPlaneContext, _request: Mapping[str, Any]
    ) -> dict[str, Any]:
        return {"ok": True}

    config = _config(tmp_path, unused_test_handler)
    backend = _backend(config, authorizer)
    try:
        service = backend.api.managed_service
        assert service is not None
        accepted = service.submit_connector_action(
            ctx,
            "connector.catalog",
            {"limit": 1},
            idempotency_key="catalog-page-one",
        )
        assert backend.create_action_execution_host().tick(ctx) == 1
        receipt = service.get_connector_action(ctx, accepted["action_id"])
        assert receipt["status"] == "succeeded", (
            receipt["error_code"],
            receipt,
        )
        assert receipt["result"]["schema"].startswith("etlantic.connector_catalog/")
        assert len(receipt["result"]["items"]) <= 1
    finally:
        backend.close()


def test_managed_preview_http_result_expires_after_durable_persistence(
    tmp_path: Path,
) -> None:
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "connector.preview")
    authorizer.grant(ctx, "connector.action.read")
    handler_requests: list[Mapping[str, Any]] = []

    async def preview(
        _ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        handler_requests.append(request)
        return {
            "columns": [
                {"name": "email", "logical_type": "string", "sensitive": True},
                {"name": "note", "logical_type": "string"},
            ],
            "rows": [
                {"email": "private@example.test", "note": "private row"},
                {"email": "second@example.test", "note": "second row"},
            ],
        }

    config = _config(
        tmp_path,
        preview,
        action="connector.preview",
        preview_result_ttl_seconds=60,
    )
    backend = _backend(config, authorizer)
    client = cast(Any, TestClient)(create_app(backend.api, with_lifespan=False))
    try:
        response = client.post(
            "/v1/connector-actions/connector.preview",
            headers={
                "X-Principal": "action-owner",
                "Idempotency-Key": "preview-http",
            },
            json={
                "payload": {
                    "provider": "mock",
                    "connection_id": "saved-db",
                    "resource_id": "sample-table",
                    "max_rows": 1,
                    "max_bytes": 512,
                    "redact_fields": ["note"],
                },
                "deadline_seconds": 10,
            },
        )
        assert response.status_code == 202
        action_id = response.json()["action_id"]
        assert response.json()["result_expires_at"] is None
        assert backend.create_action_execution_host().tick(ctx) == 1
        service = backend.api.managed_service
        assert service is not None
        receipt = service.get_connector_action(ctx, action_id)
        assert receipt["status"] == "succeeded"
        assert receipt["result"]["truncated"] is True
        assert receipt["result"]["rows"] == [{"email": "***", "note": "***"}]
        assert receipt["result_expires_at"] is not None
        assert handler_requests[0] == {
            "provider": "mock",
            "connection_id": "saved-db",
            "resource_id": "sample-table",
            "max_rows": 1,
            "max_bytes": 512,
            "redact_fields": ["note"],
        }
        http_receipt = client.get(
            f"/v1/connector-actions/{action_id}",
            headers={"X-Principal": "action-owner"},
        )
        assert http_receipt.status_code == 200
        assert http_receipt.json()["result_expires_at"] == receipt["result_expires_at"]
        assert http_receipt.json()["result"] == receipt["result"]

        expired_at = datetime.now(UTC) + timedelta(minutes=2)
        assert backend.api.durable_work is not None
        assert (
            backend.api.durable_work.cleanup_expired_action_results(
                ctx, limit=10, now=expired_at
            )
            == 1
        )
        expired_receipt = service.get_connector_action(ctx, action_id)
        assert expired_receipt["status"] == "succeeded"
        assert expired_receipt["result"] is None
        assert expired_receipt["result_expires_at"] is not None
        expired_http_receipt = client.get(
            f"/v1/connector-actions/{action_id}",
            headers={"X-Principal": "action-owner"},
        )
        assert expired_http_receipt.status_code == 200
        assert expired_http_receipt.json()["result"] is None
    finally:
        backend.close()

    restarted = _backend(config, authorizer)
    try:
        service = restarted.api.managed_service
        assert service is not None
        persisted = service.get_connector_action(ctx, action_id)
        assert persisted["status"] == "succeeded"
        assert persisted["result"] is None
        assert persisted["result_expires_at"] is not None
    finally:
        restarted.close()


def test_managed_provision_is_explicit_idempotent_and_compensatable(
    tmp_path: Path,
) -> None:
    ctx = _context()
    authorized_actions = frozenset(
        (
            "connector.schema.inspect",
            "connector.provision",
            "connector.provision.cleanup",
            "connector.action.read",
        )
    )

    class PrincipalActionAuthorizer:
        def authorize(
            self, ctx: ControlPlaneContext, action: str, resource: str
        ) -> AuthzDecision:
            del resource
            return AuthzDecision(
                allowed=(
                    ctx.principal.subject == "action-owner"
                    and action in authorized_actions
                ),
                reason="principal action grant",
                disclosure="forbidden",
            )

    authorizer = PrincipalActionAuthorizer()
    provider_effects: dict[str, str] = {}
    observed_inspections: list[Mapping[str, Any]] = []

    async def inspect_schema(
        _ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        observed_inspections.append(request)
        return {"fields": [{"name": "id", "logical_type": "integer"}]}

    async def provision(
        _ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        assert request["mode"] == "create_only"
        assert request["if_exists"] == "fail"
        resource_id = str(request["resource_id"])
        effect_id = provider_effects.setdefault(resource_id, f"effect-{resource_id}")
        return {
            "action_id": request["action_id"],
            "effect_id": effect_id,
            "resource_id": resource_id,
            "schema_fingerprint": request["schema_fingerprint"],
            "created": True,
            "cleanup_supported": True,
        }

    async def cleanup(
        _ctx: ControlPlaneContext, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        resource_id = str(request["resource_id"])
        assert provider_effects[resource_id] == request["effect_id"]
        provider_effects.pop(resource_id)
        return {
            "action_id": request["action_id"],
            "effect_id": request["effect_id"],
            "resource_id": resource_id,
            "cleanup_of": request["provision_action_id"],
            "removed": True,
        }

    config = _config(
        tmp_path,
        provision,
        action="connector.provision",
        additional_action_handlers={
            "connector.schema.inspect": inspect_schema,
            "connector.provision.cleanup": cleanup,
        },
    )
    backend = _backend(config, authorizer)
    client = cast(Any, TestClient)(create_app(backend.api, with_lifespan=False))
    headers = {"X-Principal": "action-owner"}
    provision_payload = {
        "provider": "mock",
        "connection_id": "saved-db",
        "resource_id": "created-table",
        "target_kind": "table",
        "columns": [
            {"name": "id", "logical_type": "integer", "nullable": False},
            {"name": "label", "logical_type": "string"},
        ],
    }
    try:
        service = backend.api.managed_service
        assert service is not None
        with pytest.raises(ControlPlaneError) as denied:
            service.submit_connector_action(
                replace(ctx, principal=Principal("unprivileged-owner")),
                "connector.provision",
                provision_payload,
                idempotency_key="denied-provision",
            )
        assert denied.value.status == 403
        assert provider_effects == {}

        inspection = client.post(
            "/v1/connector-actions/connector.schema.inspect",
            headers={**headers, "Idempotency-Key": "inspect-before-create"},
            json={
                "payload": {"provider": "mock", "connection_id": "saved-db"},
                "deadline_seconds": 10,
            },
        )
        assert inspection.status_code == 202
        assert backend.create_action_execution_host().tick(ctx, limit=1) == 1
        assert observed_inspections == [
            {"provider": "mock", "connection_id": "saved-db", "max_fields": 100}
        ]
        assert provider_effects == {}

        submitted = client.post(
            "/v1/connector-actions/connector.provision",
            headers={**headers, "Idempotency-Key": "provision-http"},
            json={"payload": provision_payload, "deadline_seconds": 10},
        )
        assert submitted.status_code == 202
        action_id = submitted.json()["action_id"]
        duplicate = service.submit_connector_action(
            ctx,
            "connector.provision",
            provision_payload,
            idempotency_key="provision-http",
            deadline_seconds=10,
        )
        assert duplicate["action_id"] == action_id
        assert backend.create_action_execution_host().tick(ctx, limit=1) == 1
        provision_receipt = client.get(
            f"/v1/connector-actions/{action_id}", headers=headers
        )
        assert provision_receipt.status_code == 200
        assert provision_receipt.json()["status"] == "succeeded"
        assert provider_effects == {"created-table": "effect-created-table"}

        cleanup_response = client.post(
            "/v1/connector-actions/connector.provision.cleanup",
            headers={**headers, "Idempotency-Key": "cleanup-http"},
            json={
                "payload": {
                    "provider": "mock",
                    "connection_id": "saved-db",
                    "resource_id": "created-table",
                    "provision_action_id": action_id,
                },
                "deadline_seconds": 10,
            },
        )
        assert cleanup_response.status_code == 202
        cleanup_id = cleanup_response.json()["action_id"]
        assert backend.create_action_execution_host().tick(ctx, limit=1) == 1
        cleanup_receipt = client.get(
            f"/v1/connector-actions/{cleanup_id}", headers=headers
        )
        assert cleanup_receipt.status_code == 200
        assert cleanup_receipt.json()["status"] == "succeeded"
        assert cleanup_receipt.json()["result"]["cleanup_of"] == action_id
        assert provider_effects == {}

        with pytest.raises(ControlPlaneError) as cleanup_denied:
            service.submit_connector_action(
                replace(ctx, principal=Principal("unprivileged-owner")),
                "connector.provision.cleanup",
                {
                    "provider": "mock",
                    "connection_id": "saved-db",
                    "resource_id": "created-table",
                    "provision_action_id": action_id,
                },
                idempotency_key="denied-cleanup",
            )
        assert cleanup_denied.value.status == 403
    finally:
        backend.close()
