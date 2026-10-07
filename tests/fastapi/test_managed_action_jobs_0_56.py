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
pytest.importorskip("httpx2")

import sqlalchemy
from fastapi.testclient import TestClient

from etlantic import Data, Extract, Load, Pipeline, Profile
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.control_plane import (
    Authorizer,
    AuthzDecision,
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.runtime.request import RunRequest
from etlantic_fastapi import (
    ManagedBackend,
    ManagedBackendConfig,
    create_app,
    create_managed_backend,
    membership_context_factory,
    static_context_factory,
)
from etlantic_sqlmodel.migrations import upgrade


class _PreparationRow(Data):
    id: int


class _PreparationPipeline(Pipeline):
    source: Extract[_PreparationRow] = Extract(asset="source")
    result: Load[_PreparationRow] = Load(input=source, asset="result")


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
        assert upgrade(engine) == "014_cp1_complete_principal_idempotency_0_56"
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


def test_managed_run_preparation_survives_sql_backend_restart(
    tmp_path: Path,
) -> None:
    ctx = _context()
    authorizer = MemoryAuthorizer()
    for action in (
        "definition.write",
        "run.submit",
        "run.read",
        "run.cancel",
    ):
        authorizer.grant(ctx, action)
    config: Any = cast(Any, _config(tmp_path, _async_action_result))
    backend: Any = cast(Any, _backend(config, authorizer))
    headers = {"X-Principal": "action-owner"}
    body = {"payload": {"request": RunRequest().to_dict()}}
    try:
        service: Any = backend.api.managed_service
        assert service is not None
        service.register_definition(
            ctx,
            "preparation-pipe",
            pipeline_to_dict(definition_from_pipeline(_PreparationPipeline)),
        )
        client: Any = cast(
            Any,
            TestClient(cast(Any, create_app(backend.api, with_lifespan=False))),
        )
        queued = client.post(
            "/v1/definitions/preparation-pipe/preparations",
            headers={**headers, "Idempotency-Key": "preparation-sql-cancel"},
            json=body,
        )
        assert queued.status_code == 202, queued.text
        cancelled_id = queued.json()["operation_id"]
        cancelled = client.delete(f"/v1/preparations/{cancelled_id}", headers=headers)
        assert cancelled.status_code == 202, cancelled.text
        assert cancelled.json()["status"] == "cancelled"

        secret = client.post(
            "/v1/definitions/preparation-pipe/preparations",
            headers={**headers, "Idempotency-Key": "preparation-sql-secret"},
            json={"payload": {"request": {"metadata": {"password": "do-not-store"}}}},
        )
        assert secret.status_code == 400

        operation_response = client.post(
            "/v1/definitions/preparation-pipe/preparations",
            headers={**headers, "Idempotency-Key": "preparation-sql-restart"},
            json=body,
        )
        assert operation_response.status_code == 202, operation_response.text
        operation_id = operation_response.json()["operation_id"]
        replay = client.post(
            "/v1/definitions/preparation-pipe/preparations",
            headers={**headers, "Idempotency-Key": "preparation-sql-restart"},
            json=body,
        )
        assert replay.json()["operation_id"] == operation_id

        durable: Any = backend.api.durable_work
        assert durable is not None
        claimed: Any = durable.claim_action_job(
            ctx,
            worker_id="terminated-preparation-worker",
            lease_seconds=1,
            now=datetime.now(UTC) - timedelta(seconds=10),
        )
        assert claimed is not None
        assert claimed.action_id == operation_id
        assert claimed.status == "running"
        assert "do-not-store" not in repr(durable.get_action_job(ctx, operation_id))
    finally:
        backend.close()

    restarted: Any = cast(Any, _backend(config, authorizer))
    try:
        client: Any = cast(
            Any,
            TestClient(cast(Any, create_app(restarted.api, with_lifespan=False))),
        )
        recovered = client.get(f"/v1/preparations/{operation_id}", headers=headers)
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["operation_id"] == operation_id
        assert recovered.json()["status"] == "running"

        worker: Any = restarted.create_action_execution_host(
            worker_id="recovery-worker"
        )
        assert worker.tick(ctx) == 1
        completed = client.get(f"/v1/preparations/{operation_id}", headers=headers)
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "succeeded"
        assert completed.json()["result"]["submission_id"]
        durable: Any = restarted.api.durable_work
        assert durable is not None
        submission: Any = durable.get_submission_by_idempotency(
            ctx,
            idempotency_key=f"preparation-{operation_id}",
            operation="run.submit",
        )
        assert submission is not None
        assert submission.revision_id
        assert len(durable.pending_outbox(ctx)) == 1
    finally:
        restarted.close()


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


def test_action_receipts_and_cursors_are_bound_to_owner_environment_and_domain(
    tmp_path: Path,
) -> None:
    ctx = replace(_context(), resource_owner_id="owner-a")
    bob = replace(ctx, principal=Principal("other-owner"), resource_owner_id="owner-b")
    authorizer = MemoryAuthorizer()
    for action in (
        "connector.test",
        "connector.action.read",
        "connector.action.list",
    ):
        authorizer.grant(ctx, action)
    config = _config(tmp_path, _async_action_result)
    backend = create_managed_backend(
        config,
        authorizer=authorizer,
        context_factory=membership_context_factory(
            {
                "action-owner": (
                    "action-tenant",
                    "action-workspace",
                    "test",
                    "action-domain",
                ),
                "other-owner": (
                    "action-tenant",
                    "action-workspace",
                    "test",
                    "action-domain",
                ),
                "foreign-tenant": (
                    "foreign-tenant",
                    "action-workspace",
                    "test",
                    "action-domain",
                ),
                "foreign-workspace": (
                    "action-tenant",
                    "foreign-workspace",
                    "test",
                    "action-domain",
                ),
                "foreign-environment": (
                    "action-tenant",
                    "action-workspace",
                    "production",
                    "action-domain",
                ),
                "foreign-domain": (
                    "action-tenant",
                    "action-workspace",
                    "test",
                    "restricted",
                ),
            },
            resource_owners={
                "action-owner": "owner-a",
                "other-owner": "owner-b",
                "foreign-tenant": "owner-a",
                "foreign-workspace": "owner-a",
                "foreign-environment": "owner-a",
                "foreign-domain": "owner-a",
            },
        ),
    )
    try:
        service = backend.api.managed_service
        assert service is not None
        request = {"provider": "mock", "connection_id": "same-saved-connection"}
        base = service.submit_connector_action(
            ctx, "connector.test", request, idempotency_key="same-key"
        )
        contexts = (
            (
                "other-owner",
                replace(
                    ctx,
                    principal=Principal("other-owner"),
                    resource_owner_id="owner-b",
                ),
            ),
            (
                "foreign-tenant",
                replace(
                    ctx,
                    principal=Principal("foreign-tenant"),
                    tenant=TenantRef("foreign-tenant"),
                    workspace=WorkspaceRef("foreign-tenant", "action-workspace"),
                ),
            ),
            (
                "foreign-workspace",
                replace(
                    ctx,
                    principal=Principal("foreign-workspace"),
                    workspace=WorkspaceRef("action-tenant", "foreign-workspace"),
                ),
            ),
            (
                "foreign-environment",
                replace(
                    ctx,
                    principal=Principal("foreign-environment"),
                    environment=EnvironmentRef("production"),
                ),
            ),
            (
                "foreign-domain",
                replace(
                    ctx,
                    principal=Principal("foreign-domain"),
                    security_domain=SecurityDomain("restricted"),
                ),
            ),
        )
        for _subject, variant in contexts:
            for action in (
                "connector.test",
                "connector.action.read",
                "connector.action.list",
            ):
                authorizer.grant(variant, action)
        isolated = [
            service.submit_connector_action(
                variant, "connector.test", request, idempotency_key="same-key"
            )
            for _subject, variant in contexts
        ]
        assert len({base["action_id"], *(item["action_id"] for item in isolated)}) == 6

        client = cast(Any, TestClient(create_app(backend.api, with_lifespan=False)))

        for subject, variant in contexts:
            with pytest.raises(ControlPlaneError) as hidden:
                service.get_connector_action(variant, base["action_id"])
            assert hidden.value.status == 404
            variant_page = service.list_connector_actions(variant)
            assert all(
                item["action_id"] != base["action_id"] for item in variant_page["items"]
            )
            hidden_http = client.get(
                f"/v1/connector-actions/{base['action_id']}",
                headers={"X-Principal": subject},
            )
            assert hidden_http.status_code == 404

        second = service.submit_connector_action(
            ctx, "connector.test", request, idempotency_key="second-key"
        )
        assert second["action_id"] != base["action_id"]
        first_page = service.list_connector_actions(ctx, limit=1)
        cursor = first_page["next_cursor"]
        assert cursor is not None
        with pytest.raises(ControlPlaneError) as invalid_headless_cursor:
            service.list_connector_actions(bob, limit=1, cursor=cursor)
        assert invalid_headless_cursor.value.status == 400

        invalid_http_cursor = client.get(
            "/v1/connector-actions",
            params={"limit": 1, "cursor": cursor},
            headers={"X-Principal": "other-owner"},
        )
        assert invalid_http_cursor.status_code == invalid_headless_cursor.value.status
        assert invalid_http_cursor.json()["code"] == invalid_headless_cursor.value.code
    finally:
        backend.close()


@pytest.mark.parametrize(
    "variant_headers",
    [
        {"X-Principal-Issuer": "issuer-b"},
        {"X-Principal-Kind": "service"},
    ],
)
def test_action_receipts_and_http_listing_use_issuer_qualified_owner(
    tmp_path: Path, variant_headers: Mapping[str, str]
) -> None:
    owner = _context()
    variant = replace(
        owner,
        principal=Principal(
            "action-owner",
            issuer=variant_headers.get("X-Principal-Issuer"),
            kind=variant_headers.get("X-Principal-Kind", "human"),
        ),
    )
    authorizer = MemoryAuthorizer()
    for context in (owner, variant):
        for action in (
            "connector.test",
            "connector.action.read",
            "connector.action.list",
            "run.cancel",
        ):
            authorizer.grant(context, action)
    backend = _backend(_config(tmp_path, _async_action_result), authorizer)
    client = cast(Any, TestClient(create_app(backend.api, with_lifespan=False)))
    try:
        service = backend.api.managed_service
        assert service is not None
        receipt = service.submit_connector_action(
            owner,
            "connector.test",
            {"provider": "mock", "connection_id": "same-connection"},
            idempotency_key="issuer-qualified-key",
        )
        service.submit_connector_action(
            owner,
            "connector.test",
            {"provider": "mock", "connection_id": "second"},
            idempotency_key="second-owner-action",
        )
        repeated_as_variant = service.submit_connector_action(
            variant,
            "connector.test",
            {"provider": "mock", "connection_id": "same-connection"},
            idempotency_key="issuer-qualified-key",
        )
        assert repeated_as_variant["action_id"] != receipt["action_id"]
        preparation = backend.api.durable_work.accept_action_job(
            owner,
            action="run.prepare",
            idempotency_key="private-preparation",
            request={"definition_id": "private-definition"},
            deadline_at=(datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
        )
        with pytest.raises(ControlPlaneError) as hidden_cancel:
            service.cancel_run_preparation(variant, preparation.action_id)
        assert hidden_cancel.value.status == 404
        assert (
            backend.api.durable_work.get_action_job(owner, preparation.action_id).status
            == "queued"
        )
        with pytest.raises(ControlPlaneError) as hidden:
            service.get_connector_action(variant, receipt["action_id"])
        assert hidden.value.status == 404
        assert all(
            item["action_id"] != receipt["action_id"]
            for item in service.list_connector_actions(variant)["items"]
        )
        owner_page = service.list_connector_actions(owner, limit=1)
        cursor = owner_page["next_cursor"]
        assert cursor is not None
        with pytest.raises(ControlPlaneError) as wrong_owner_cursor:
            service.list_connector_actions(variant, limit=1, cursor=cursor)
        assert wrong_owner_cursor.value.status == 400

        headers = {"X-Principal": "action-owner", **variant_headers}
        hidden_http = client.get(
            f"/v1/connector-actions/{receipt['action_id']}", headers=headers
        )
        assert hidden_http.status_code == 404
        hidden_cancel_http = client.delete(
            f"/v1/preparations/{preparation.action_id}", headers=headers
        )
        assert hidden_cancel_http.status_code == 404
        listed_http = client.get("/v1/connector-actions", headers=headers)
        assert listed_http.status_code == 200
        assert all(
            item["action_id"] != receipt["action_id"]
            for item in listed_http.json()["items"]
        )
        cursor_http = client.get(
            "/v1/connector-actions",
            params={"limit": 1, "cursor": cursor},
            headers=headers,
        )
        assert cursor_http.status_code == 400
    finally:
        backend.close()


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
