"""Standard managed FastAPI backend construction and resource ownership."""

from __future__ import annotations

from pathlib import Path
from time import sleep
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

from etlantic import Data, Extract, Load, Pipeline
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    ExecutionEnvelope,
    MemoryAuthorizer,
    Principal,
    RevisionedDefinitionRepository,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic_fastapi import (
    ManagedBackend,
    ManagedBackendConfig,
    create_managed_app,
    create_managed_backend,
    static_context_factory,
)
from etlantic_sqlmodel.migrations import upgrade


class _ManagedBackendRow(Data):
    id: int


class _ManagedBackendPipeline(Pipeline):
    source: Extract[_ManagedBackendRow] = Extract(asset="source")
    result: Load[_ManagedBackendRow] = Load(input=source, asset="result")


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
    assert upgrade(engine) == "009_event_retention_tombstones_0_56"
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


def test_managed_backend_persists_and_resolves_definition_revision(
    tmp_path: Path,
) -> None:
    config = ManagedBackendConfig(
        database_url=_migrated_url(tmp_path),
        store_id="managed-backend-revision",
    )
    backend = _backend(config)
    ctx = _context()
    try:
        authorizer = cast(MemoryAuthorizer, backend.api.authorizer)
        authorizer.grant(ctx, "definition.write")
        authorizer.grant(ctx, "run.submit")
        service = backend.api.managed_service
        assert service is not None
        definitions = cast(RevisionedDefinitionRepository, service.definitions)
        service.register_definition(
            ctx,
            "persisted-pipe",
            pipeline_to_dict(definition_from_pipeline(_ManagedBackendPipeline)),
        )
        resolution = definitions.resolve_revision(ctx, "persisted-pipe", "current")
        receipt = service.submit_run(
            ctx,
            "persisted-pipe",
            idempotency_key="persisted-revision-run",
            revision_selector=resolution.revision_id,
        )
        durable = backend.api.durable_work
        assert durable is not None
        accepted = durable.get_submission(ctx, receipt.submission_id)
        assert accepted.input_snapshot is not None
        envelope = ExecutionEnvelope.from_json(accepted.input_snapshot)
        assert envelope.revision_id == resolution.revision_id
    finally:
        backend.close()

    restarted = _backend(config)
    try:
        service = restarted.api.managed_service
        assert service is not None
        definitions = cast(RevisionedDefinitionRepository, service.definitions)
        pinned = definitions.resolve_revision(
            ctx, "persisted-pipe", resolution.revision_id
        )
        assert pinned.revision_id == resolution.revision_id
        assert pinned.document == resolution.document
    finally:
        restarted.close()


def test_standard_backend_worker_persists_queryable_report_in_sqlmodel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = _migrated_url(tmp_path)
    source = tmp_path / "input.json"
    target = tmp_path / "output.csv"
    source.write_text('[{"id": 29}]', encoding="utf-8")

    def planning_context_factory(
        _ctx: ControlPlaneContext, profile: Any
    ) -> PlanningContext:
        planning = PlanningContext.create(profile=profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="source",
                provider="json",
                location=str(source),
                kind="source",
            )
        )
        planning.registry.register_binding(
            BindingDescriptor(
                binding="result",
                provider="csv",
                location=str(target),
                kind="sink",
            )
        )
        return planning

    config = ManagedBackendConfig(
        database_url=database_url,
        store_id="managed-backend-report",
    )
    authorizer = MemoryAuthorizer()
    ctx = _context()
    for action in (
        "definition.write",
        "run.submit",
        "run.read",
        "run.report",
        "run.lineage",
    ):
        authorizer.grant(ctx, action)
    backend = create_managed_backend(
        config,
        authorizer=authorizer,
        context_factory=static_context_factory(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            environment=ctx.environment.name,
            security_domain=ctx.security_domain.domain_id,
        ),
        planning_context_factory=planning_context_factory,
    )
    try:
        service = backend.api.managed_service
        assert service is not None
        service.register_definition(
            ctx,
            "reported-pipe",
            pipeline_to_dict(definition_from_pipeline(_ManagedBackendPipeline)),
        )
        receipt = service.submit_run(
            ctx, "reported-pipe", idempotency_key="sqlmodel-report-run"
        )
        assert receipt.resource_id is not None
        durable = backend.api.durable_work
        assert durable is not None
        host = backend.create_execution_host(owner_id="sqlmodel-worker", ttl_seconds=1)

        def fail_after_report_is_published(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("simulated worker crash after report publication")

        monkeypatch.setattr(durable, "finish_attempt", fail_after_report_is_published)
        with pytest.raises(RuntimeError, match="after report publication"):
            host.tick(ctx)
        report = service.get_run_report(ctx, receipt.resource_id)
        assert report["run_id"] == receipt.resource_id
        assert report["status"] == "succeeded"
        assert target.read_text(encoding="utf-8").splitlines() == ["id", "29"]
    finally:
        backend.close()

    # The restarted worker must reuse the published report rather than rerun
    # the transfer against changed source contents.
    source.write_text('[{"id": 30}]', encoding="utf-8")
    sleep(1.1)

    restarted = create_managed_backend(
        config,
        authorizer=authorizer,
        context_factory=static_context_factory(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            environment=ctx.environment.name,
            security_domain=ctx.security_domain.domain_id,
        ),
        planning_context_factory=planning_context_factory,
    )
    try:
        service = restarted.api.managed_service
        assert service is not None
        durable = restarted.api.durable_work
        assert durable is not None
        assert (
            durable.get_submission_by_idempotency(
                ctx, idempotency_key="sqlmodel-report-run"
            )
            is not None
        )
        assert (
            restarted.create_execution_host(
                owner_id="sqlmodel-worker-restarted", ttl_seconds=1
            ).tick(ctx)
            == 1
        )
        assert service.get_run_report(ctx, receipt.resource_id)["status"] == (
            "succeeded"
        )
        assert target.read_text(encoding="utf-8").splitlines() == ["id", "29"]
        assert restarted.api.events is not None
        run_events = [
            event
            for event in restarted.api.events.list_after_cursor(ctx, None, limit=50)
            if dict(event.payload or {}).get("run_id") == receipt.resource_id
        ]
        attempt_events = [
            event
            for event in run_events
            if event.kind in {"run.started", "run.completed"}
        ]
        assert [event.kind for event in attempt_events].count("run.started") == 2
        assert [event.kind for event in attempt_events].count("run.completed") == 2
        assert len({event.event_id for event in attempt_events}) == len(attempt_events)
        assert all(
            dict(event.payload or {}).get("submission_id") == receipt.submission_id
            for event in attempt_events
        )
        assert (
            len(
                {
                    dict(event.payload or {}).get("attempt_id")
                    for event in attempt_events
                }
            )
            == 2
        )
        other_workspace = ControlPlaneContext(
            principal=ctx.principal,
            tenant=ctx.tenant,
            workspace=WorkspaceRef(ctx.tenant.tenant_id, "other-workspace"),
            environment=ctx.environment,
            security_domain=ctx.security_domain,
        )
        assert (
            restarted.report_store_factory(other_workspace).get(report["run_id"])
            is None
        )
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
            ManagedBackendConfig(database_url=f"sqlite:///{tmp_path / 'unmigrated.db'}")
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
    with pytest.raises(RuntimeError, match="stores are not ready"), test_client(app):
        pytest.fail("the application entered service with unready stores")

    assert backend.engine.pool is not initial_pool
    assert app.state.control_plane_ready is False


def test_managed_backend_configuration_hides_database_credentials() -> None:
    config = ManagedBackendConfig(
        database_url="postgresql+psycopg://user:secret-value@db.example.test/app",
        profile={"connector_options": {"password": "secret-value"}},
    )

    assert "secret-value" not in repr(config)
