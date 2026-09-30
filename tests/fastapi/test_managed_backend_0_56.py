"""Standard managed FastAPI backend construction and resource ownership."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import sqlalchemy
from fastapi.testclient import TestClient as FastAPITestClient
from sqlalchemy.engine import Engine

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_fastapi import (
    ManagedBackend,
    ManagedBackendConfig,
    create_managed_app,
    create_managed_backend,
    static_context_factory,
)
from etlantic_sqlmodel.migrations import upgrade


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("managed-backend-test"),
        tenant=TenantRef("managed-backend-tenant"),
        workspace=WorkspaceRef("managed-backend-tenant", "managed-backend-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("managed-backend-tests"),
    )


def _migrated_url(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'managed.db'}"
    engine = sqlalchemy.create_engine(url)
    assert upgrade(engine) == "005_cp1_reference"
    engine.dispose()
    return url


def _backend(
    config: ManagedBackendConfig,
) -> ManagedBackend:
    return create_managed_backend(
        config,
        authorizer=MemoryAuthorizer(),
        context_factory=static_context_factory(
            tenant_id="managed-backend-tenant",
            workspace_id="managed-backend-workspace",
            environment="test",
            security_domain="managed-backend-tests",
        ),
    )


def test_managed_app_shares_stores_and_preserves_accepted_work_on_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = _migrated_url(tmp_path)
    original_create_engine = sqlalchemy.create_engine
    engines: list[Engine] = []

    def capture_engine(*args: Any, **kwargs: Any) -> Engine:
        engine = original_create_engine(*args, **kwargs)
        engines.append(engine)
        return engine

    monkeypatch.setattr(sqlalchemy, "create_engine", capture_engine)
    config = ManagedBackendConfig(
        database_url=database_url,
        store_id="managed-backend-test",
    )
    app = create_managed_app(
        config,
        authorizer=MemoryAuthorizer(),
        context_factory=static_context_factory(
            tenant_id="managed-backend-tenant",
            workspace_id="managed-backend-workspace",
            environment="test",
            security_domain="managed-backend-tests",
        ),
    )
    backend = app.state.managed_backend
    assert isinstance(backend, ManagedBackend)
    assert engines == [backend.engine]
    pool_before_shutdown = backend.engine.pool

    test_client = cast(Any, FastAPITestClient)
    with test_client(app) as client:
        assert client.get("/ready").json()["status"] == "ready"
        assert app.state.etlantic_api is backend.api
        assert app.state.managed_service is backend.api.managed_service
        assert app.state.durable_work is backend.api.durable_work
        service = backend.api.managed_service
        assert service is not None
        durable_work = backend.api.durable_work
        assert durable_work is not None
        submission, created = durable_work.accept(
            _context(),
            idempotency_key="accepted-before-shutdown",
            operation="run.submit",
            plan_fingerprint="a" * 64,
            input_snapshot='{"schema":"accepted-test/1"}',
        )
        assert created
        assert client.get("/health").status_code == 200

    assert backend.engine.pool is not pool_before_shutdown

    restarted = _backend(config)
    try:
        durable_work = restarted.api.durable_work
        assert durable_work is not None
        recovered = durable_work.get_submission_by_idempotency(
            _context(), idempotency_key="accepted-before-shutdown"
        )
        assert recovered is not None
        assert recovered.submission_id == submission.submission_id
        assert len(durable_work.pending_outbox(_context())) == 1
    finally:
        restarted.close()


def test_managed_backend_rejects_unmigrated_schema_and_disposes_partial_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_create_engine = sqlalchemy.create_engine
    engines: list[Engine] = []

    disposed_pool: Any = None

    def capture_initial_pool(*args: Any, **kwargs: Any) -> Engine:
        engine = original_create_engine(*args, **kwargs)
        nonlocal disposed_pool
        disposed_pool = engine.pool
        engines.append(engine)
        return engine

    monkeypatch.setattr(sqlalchemy, "create_engine", capture_initial_pool)
    with pytest.raises(RuntimeError, match="not migrated"):
        _backend(
            ManagedBackendConfig(
                database_url=f"sqlite:///{tmp_path / 'unmigrated.db'}"
            )
        )

    assert len(engines) == 1
    assert engines[0].pool is not disposed_pool


def test_managed_app_disposes_backend_after_partial_lifespan_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_managed_app(
        ManagedBackendConfig(
            database_url=_migrated_url(tmp_path),
            store_id="managed-backend-startup-failure",
        ),
        authorizer=MemoryAuthorizer(),
        context_factory=static_context_factory(
            tenant_id="managed-backend-tenant",
            workspace_id="managed-backend-workspace",
            environment="test",
            security_domain="managed-backend-tests",
        ),
    )
    backend = app.state.managed_backend
    initial_pool = backend.engine.pool
    monkeypatch.setattr(backend.api, "stores_ready", lambda: False)

    test_client = cast(Any, FastAPITestClient)
    with pytest.raises(RuntimeError, match="stores are not ready"), test_client(
        app
    ):
        pytest.fail("the application entered service with unready stores")

    assert backend.engine.pool is not initial_pool
    assert app.state.control_plane_ready is False


def test_managed_backend_configuration_hides_database_credentials() -> None:
    config = ManagedBackendConfig(
        database_url="postgresql+psycopg://user:secret-value@db.example.test/app",
        profile={"connector_options": {"password": "secret-value"}},
    )

    assert "secret-value" not in repr(config)
