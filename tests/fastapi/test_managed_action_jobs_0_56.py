"""HTTP admission and SQLModel persistence for isolated connector actions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
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
from etlantic.control_plane import ControlPlaneContext, MemoryAuthorizer, Principal
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


def _config(tmp_path: Path, action_handler: Any) -> ManagedBackendConfig:
    database_url = f"sqlite:///{tmp_path / 'actions.sqlite'}"
    engine = sqlalchemy.create_engine(database_url)
    try:
        assert upgrade(engine) == "010_immutable_input_resources_0_56"
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
        action_handlers={"connector.test": action_handler},
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


def _backend(
    config: ManagedBackendConfig, authorizer: MemoryAuthorizer
) -> ManagedBackend:
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

        first_page = client.get(
            "/v1/connector-actions?limit=1", headers=headers
        )
        assert first_page.status_code == 200
        assert len(first_page.json()["items"]) == 1
        assert first_page.json()["has_more"] is True
        second_page = client.get(
            "/v1/connector-actions?limit=1"
            f"&cursor={first_page.json()['next_cursor']}",
            headers=headers,
        )
        assert second_page.status_code == 200
        assert len(second_page.json()["items"]) == 1
        assert second_page.json()["items"][0]["action_id"] != (
            first_page.json()["items"][0]["action_id"]
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
        assert all(item.principal.subject == "action-owner" for item in handler_contexts)
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
