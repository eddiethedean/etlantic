"""Managed service idempotency against independent PostgreSQL processes."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from typing import cast

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")
pytest.importorskip("fastapi")

import sqlalchemy
from sqlalchemy import text

from etlantic import Data, Extract, Load, Pipeline
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    Principal,
    RevisionedDefinitionRepository,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.runtime.request import RunRequest
from etlantic_fastapi import (
    ManagedBackendConfig,
    create_managed_backend,
    static_context_factory,
)
from etlantic_sqlmodel.control_plane.cp4_stores import SQLModelQuotaProvider
from etlantic_sqlmodel.migrations import upgrade
from sqlmodel import Session


class _ServiceRow(Data):
    id: int


class _ServicePipeline(Pipeline):
    source: Extract[_ServiceRow] = Extract(asset="source")
    result: Load[_ServiceRow] = Load(input=source, asset="result")


def _context(scope: str) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("phase056-postgres-service", issuer="phase056-tests"),
        tenant=TenantRef(scope),
        workspace=WorkspaceRef(scope, "workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain(f"security-{scope}"),
    )


def _cleanup_scope(engine: sqlalchemy.engine.Engine, store_id: str, scope: str) -> None:
    """Remove only rows created under this test's random scope and store id."""
    with Session(engine) as session, session.begin():
        connection = session.connection()
        for table in (
            "cp_event_idempotency",
            "cp_events",
            "cp_submissions",
            "cp_registry_aliases",
            "cp_registry_promotions",
            "cp_registry_revisions",
            "cp_registry_environments",
            "cp_registry_logical",
            "cp_registry_workspaces",
        ):
            connection.execute(
                text(
                    f"DELETE FROM {table} "
                    "WHERE tenant_id = :tenant_id AND workspace_id = :workspace_id"
                ),
                {"tenant_id": scope, "workspace_id": "workspace"},
            )
        connection.execute(
            text("DELETE FROM cp_registry_tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": scope},
        )
        connection.execute(
            text(
                "DELETE FROM cp_registry_security_domains "
                "WHERE domain_id = :domain_id"
            ),
            {"domain_id": f"security-{scope}"},
        )
        for table in (
            "cp_durable_outbox_entity",
            "cp_durable_submission_entity",
            "cp_durable_snapshot",
            "cp_cp4_governance_snapshot",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE store_id = :store_id"),
                {"store_id": store_id},
            )


def _submit_managed_run_in_process(
    url: str,
    store_id: str,
    scope: str,
    revision_id: str,
    idempotency_key: str,
    no_write: bool,
) -> tuple[str, str, str | None]:
    ctx = _context(scope)
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "run.submit")
    backend = create_managed_backend(
        ManagedBackendConfig(database_url=url, store_id=store_id),
        authorizer=authorizer,
        context_factory=static_context_factory(
            tenant_id=scope,
            workspace_id="workspace",
            environment="test",
            security_domain=f"security-{scope}",
        ),
    )
    try:
        service = backend.api.managed_service
        assert service is not None
        service.quotas = SQLModelQuotaProvider(backend.engine, store_id=store_id)
        try:
            receipt = service.submit_run(
                ctx,
                "postgres-service-pipe",
                idempotency_key=idempotency_key,
                revision_selector=revision_id,
                request=RunRequest(no_write=True) if no_write else None,
            )
        except ControlPlaneError as exc:
            return "conflict", str(exc.status), None
        return "accepted", receipt.submission_id, receipt.resource_id
    finally:
        backend.close()


def _qualify_managed_service_race(
    *,
    url: str,
    store_id: str,
    idempotency_key: str,
    no_write_intents: list[bool],
) -> tuple[list[tuple[str, str, str | None]], str, str, ControlPlaneContext]:
    scope = f"phase056-{uuid.uuid4().hex}"
    ctx = _context(scope)
    engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
    try:
        assert upgrade(engine) == "010_immutable_input_resources_0_56"
    finally:
        engine.dispose()

    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "definition.write")
    authorizer.grant(ctx, "run.submit")
    backend = create_managed_backend(
        ManagedBackendConfig(database_url=url, store_id=store_id),
        authorizer=authorizer,
        context_factory=static_context_factory(
            tenant_id=scope,
            workspace_id="workspace",
            environment="test",
            security_domain=f"security-{scope}",
        ),
    )
    try:
        service = backend.api.managed_service
        assert service is not None
        service.quotas = SQLModelQuotaProvider(backend.engine, store_id=store_id)
        service.register_definition(
            ctx,
            "postgres-service-pipe",
            pipeline_to_dict(definition_from_pipeline(_ServicePipeline)),
        )
        definitions = cast(
            RevisionedDefinitionRepository, service.definitions
        )
        resolution = definitions.resolve_revision(
            ctx, "postgres-service-pipe", "current"
        )
        with ProcessPoolExecutor(
            max_workers=len(no_write_intents), mp_context=get_context("spawn")
        ) as workers:
            results = list(
                workers.map(
                    _submit_managed_run_in_process,
                    [url] * len(no_write_intents),
                    [store_id] * len(no_write_intents),
                    [scope] * len(no_write_intents),
                    [resolution.revision_id] * len(no_write_intents),
                    [idempotency_key] * len(no_write_intents),
                    no_write_intents,
                )
            )
        return results, scope, resolution.revision_id, ctx
    finally:
        backend.close()


def test_postgresql_multiprocess_managed_service_retry_and_intent_conflict() -> None:
    url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not url:
        pytest.skip("set ETLANTIC_CP_TEST_URL for live PostgreSQL service qualification")

    same_store = f"phase056-managed-same-{uuid.uuid4().hex}"
    same_results, same_scope, _same_revision, same_ctx = _qualify_managed_service_race(
        url=url,
        store_id=same_store,
        idempotency_key="managed-same-intent",
        no_write_intents=[False] * 8,
    )
    assert {result[0] for result in same_results} == {"accepted"}
    assert len({result[1] for result in same_results}) == 1
    assert len({result[2] for result in same_results}) == 1

    reopened = create_managed_backend(
        ManagedBackendConfig(database_url=url, store_id=same_store),
        authorizer=MemoryAuthorizer(),
        context_factory=static_context_factory(
            tenant_id=same_scope,
            workspace_id="workspace",
            environment="test",
            security_domain="phase056-postgres-tests",
        ),
    )
    try:
        service = reopened.api.managed_service
        assert service is not None
        record = service.durable_work.get_submission_by_idempotency(
            same_ctx,
            idempotency_key="managed-same-intent",
            operation="run.submit",
        )
        assert record is not None
        assert record.submission_id == same_results[0][1]
        assert len(service.durable_work.pending_outbox(same_ctx)) == 1
        assert SQLModelQuotaProvider(
            reopened.engine, store_id=same_store
        ).get_state(same_ctx).usage["concurrency"] == 1
    finally:
        reopened.close()
        cleanup_engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
        try:
            _cleanup_scope(cleanup_engine, same_store, same_scope)
        finally:
            cleanup_engine.dispose()

    changed_store = f"phase056-managed-changed-{uuid.uuid4().hex}"
    changed_results, _changed_scope, _changed_revision, _changed_ctx = (
        _qualify_managed_service_race(
            url=url,
            store_id=changed_store,
            idempotency_key="managed-changed-intent",
            no_write_intents=[False] * 4 + [True] * 4,
        )
    )
    accepted = [result for result in changed_results if result[0] == "accepted"]
    conflicts = [result for result in changed_results if result[0] == "conflict"]
    assert len(accepted) == len(conflicts) == 4
    assert len({result[1] for result in accepted}) == 1
    cleanup_engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
    try:
        _cleanup_scope(cleanup_engine, changed_store, _changed_scope)
    finally:
        cleanup_engine.dispose()
