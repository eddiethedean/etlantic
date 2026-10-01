"""Standard managed FastAPI backend construction and resource ownership."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
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

from etlantic import Data, Extract, Load, Pipeline, Profile
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.connectors.local_files import LocalFilesSourceConnector
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
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.reports.model import ArtifactResult, PipelineRunReport
from etlantic.runtime.artifacts import artifact_storage_path
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.managed_errors import ExecutionRejected
from etlantic.runtime.managed_execution import (
    ManagedExecutionAdapter,
    managed_artifact_workspace,
)
from etlantic.runtime.request import MaterializationPolicy, RunIntent, RunRequest
from etlantic.runtime.state import RunStatus
from etlantic.service import managed as managed_service_module
from etlantic_fastapi import (
    ManagedBackend,
    ManagedBackendConfig,
    create_managed_app,
    create_managed_backend,
    static_context_factory,
)
from etlantic_sqlmodel.control_plane.report_stores import SqlModelRunReportStore
from etlantic_sqlmodel.migrations import upgrade


class _ManagedBackendRow(Data):
    id: int


class _ManagedBackendPipeline(Pipeline):
    source: Extract[_ManagedBackendRow] = Extract(asset="source")
    result: Load[_ManagedBackendRow] = Load(input=source, asset="result")


class _ManagedCsvRow(Data):
    id: int
    name: str


class _ManagedCsvPipeline(Pipeline):
    source: Extract[_ManagedCsvRow] = Extract(asset="source")
    result: Load[_ManagedCsvRow] = Load(input=source, asset="result")


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
    assert upgrade(engine) == "012_bounded_event_tombstone_retention_0_56"
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


def test_standard_worker_reads_configured_csv_and_does_not_retain_row_content(
    tmp_path: Path,
) -> None:
    database_url = _migrated_url(tmp_path)
    landing = tmp_path / "landing"
    landing.mkdir()
    source = landing / "orders.csv"
    source.write_bytes("\ufeffid;name\n42;Zoë\n".encode("utf-8"))
    target = tmp_path / "managed-output.csv"
    ctx = _context()
    profile = Profile(
        name="csv-worker",
        security_mode="development",
        safe_io={"approved_roots": [str(tmp_path)]},
    )

    def planning_context_factory(
        _ctx: ControlPlaneContext, effective_profile: Any
    ) -> PlanningContext:
        planning = PlanningContext.create(profile=effective_profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="source",
                provider="local-files",
                location="landing",
                kind="source",
                config={
                    "format": "csv",
                    "mode": "snapshot",
                    "root": "landing",
                    "root_ref": "managed-orders",
                    "glob": "*.csv",
                    "encoding": "utf-8-sig",
                    "delimiter": ";",
                },
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

    authorizer = MemoryAuthorizer()
    for action in (
        "definition.write",
        "run.submit",
        "run.read",
        "run.report",
        "run.artifacts",
        "run.artifact.content",
        "run.lineage",
    ):
        authorizer.grant(ctx, action)
    backend = create_managed_backend(
        ManagedBackendConfig(
            database_url=database_url,
            store_id="managed-csv-worker",
            profile=profile,
            artifact_root=str(tmp_path / "managed-csv-artifacts"),
        ),
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
            "managed-csv-pipe",
            pipeline_to_dict(definition_from_pipeline(_ManagedCsvPipeline)),
        )
        receipt = service.submit_run(
            ctx,
            "managed-csv-pipe",
            idempotency_key="managed-csv-worker-run",
            request=RunRequest(materialization=MaterializationPolicy.DURABLE),
        )
        assert receipt.resource_id is not None
        durable = backend.api.durable_work
        assert durable is not None
        accepted = durable.get_submission(ctx, receipt.submission_id)
        assert accepted is not None
        drifted_worker = ManagedExecutionAdapter(
            report_store_factory=backend.report_store_factory,
            profile=profile.with_updates(timeout_seconds=15),
        )
        with pytest.raises(ExecutionRejected, match="differs from the accepted plan"):
            drifted_worker(
                ctx,
                submission=accepted,
                submission_id=receipt.submission_id,
                attempt_id="drifted-profile-attempt",
                fencing_token=2,
            )
        assert not target.exists()

        assert (
            backend.create_execution_host(owner_id="managed-csv-worker").tick(ctx) == 1
        )

        report = service.get_run_report(ctx, receipt.resource_id)
        assert report["status"] == "succeeded"
        assert target.read_text(encoding="utf-8").splitlines() == [
            "id,name",
            "42,Zoë",
        ]
        assert source.is_file()
        assert "Zoë" not in json.dumps(report, ensure_ascii=False)
        downloadable = next(
            item
            for item in service.list_run_artifacts(ctx, receipt.resource_id)
            if item["content_available"]
        )
        content, media_type = service.get_run_artifact_content(
            ctx, receipt.resource_id, str(downloadable["artifact_id"])
        )
        assert media_type == "application/json"
        assert json.loads(content) == [{"id": "42", "name": "Zoë"}]
    finally:
        backend.close()


def test_managed_worker_executes_finalized_upload_and_lease_outlives_staging_ttl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = _migrated_url(tmp_path)
    ctx = _context()
    target = tmp_path / "immutable-upload-output.csv"
    content = "\ufeffid;name\n91;Gráce\n".encode("utf-8")
    profile = Profile(
        name="immutable-upload-worker",
        security_mode="development",
        plugin_allowlist={"etlantic": None},
    )
    reference: Any = None

    def planning_context_factory(
        _ctx: ControlPlaneContext, effective_profile: Any
    ) -> PlanningContext:
        planning = PlanningContext.create(profile=effective_profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="source",
                provider="local-files",
                kind="source",
                config={
                    "input_resource": reference.to_dict(),
                    "encoding": "utf-8-sig",
                    "delimiter": ";",
                },
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

    authorizer = MemoryAuthorizer()
    for action in (
        "definition.write",
        "run.submit",
        "run.retry",
        "run.rerun",
        "run.replay",
        "run.read",
        "input.read",
        "run.report",
    ):
        authorizer.grant(ctx, action)
    backend = create_managed_backend(
        ManagedBackendConfig(
            database_url=database_url,
            store_id="managed-immutable-upload",
            profile=profile,
            input_resource_retention_seconds=60 * 60 * 24 * 4,
        ),
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
        store = backend.input_resources
        staged = store.stage(
            ctx,
            content,
            media_type="text/csv",
            format="csv",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        reference = store.finalize(
            ctx,
            staged.upload_id,
            expected_sha256=hashlib.sha256(content).hexdigest(),
            expected_byte_length=len(content),
        )
        service = backend.api.managed_service
        assert service is not None
        service.register_definition(
            ctx,
            "immutable-upload-pipe",
            pipeline_to_dict(definition_from_pipeline(_ManagedCsvPipeline)),
        )
        receipt = service.submit_run(
            ctx,
            "immutable-upload-pipe",
            idempotency_key="immutable-upload-run",
        )
        durable = backend.api.durable_work
        assert durable is not None
        accepted = durable.get_submission(ctx, receipt.submission_id)
        assert accepted.input_snapshot is not None
        envelope = ExecutionEnvelope.from_json(accepted.input_snapshot)
        assert envelope.resource_versions == {
            f"input:{reference.resource_id}": reference.version
        }
        future = datetime.now(UTC) + timedelta(days=2)
        assert store.read(ctx, reference, now=future) == content

        refusing_host = ExecutionHost(
            durable,
            owner_id="immutable-upload-refusing-worker",
            runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                ExecutionRejected("transient worker startup rejection")
            ),
        )
        assert refusing_host.tick(ctx) == 1
        assert service.get_run_status(ctx, str(receipt.resource_id))["status"] == (
            "failed"
        )

        # Simulate a prior application version accepting this lifecycle
        # command before the lease identity included environment and principal.
        # The current service must still recover that immutable receipt.
        current_lease_id = managed_service_module.__dict__["_input_resource_lease_id"]

        def legacy_lease_id(
            context: ControlPlaneContext,
            operation: str,
            idempotency_key: str,
            *,
            legacy_scope: bool = False,
        ) -> str:
            return current_lease_id(
                context, operation, idempotency_key, legacy_scope=True
            )

        monkeypatch.setattr(
            managed_service_module, "_input_resource_lease_id", legacy_lease_id
        )
        retry = service.retry_run(
            ctx,
            str(receipt.resource_id),
            idempotency_key="immutable-upload-retry",
        )
        monkeypatch.setattr(
            managed_service_module, "_input_resource_lease_id", current_lease_id
        )
        assert (
            service.retry_run(
                ctx,
                str(receipt.resource_id),
                idempotency_key="immutable-upload-retry",
            ).to_dict()
            == retry.to_dict()
        )

        rerun = service.rerun_run(
            ctx,
            str(receipt.resource_id),
            idempotency_key="immutable-upload-rerun",
        )
        replay = service.replay_run(
            ctx,
            str(receipt.resource_id),
            idempotency_key="immutable-upload-replay",
        )
        with backend.engine.connect() as connection:
            lease_count = connection.execute(
                sqlalchemy.text(
                    "SELECT count(*) FROM cp_input_resource_leases "
                    "WHERE upload_id = :upload_id"
                ),
                {"upload_id": reference.resource_id},
            ).scalar_one()
        assert lease_count == 4
        assert store.read(ctx, reference, now=future) == content
        assert (
            backend.create_execution_host(
                owner_id="immutable-upload-replay-worker"
            ).tick(ctx)
            == 3
        )
        assert target.read_text(encoding="utf-8").splitlines() == [
            "id,name",
            "91,Gráce",
        ]
        report = service.get_run_report(ctx, str(retry.resource_id))
        assert report["status"] == "succeeded"
        assert "Gráce" not in json.dumps(report)
        assert service.get_run_report(ctx, str(rerun.resource_id))["status"] == (
            "succeeded"
        )
        assert service.get_run_report(ctx, str(replay.resource_id))["status"] == (
            "succeeded"
        )

        alternate_trusted_context = ControlPlaneContext(
            principal=Principal(
                "managed-backend-alternate-workload",
                issuer="alternate-issuer",
                kind="workload",
            ),
            tenant=ctx.tenant,
            workspace=ctx.workspace,
            environment=EnvironmentRef("staging"),
            security_domain=ctx.security_domain,
            resource_owner_id=ctx.principal.subject,
        )
        with backend.engine.connect() as connection:
            before_alternate = set(
                connection.execute(
                    sqlalchemy.text(
                        "SELECT lease_id FROM cp_input_resource_leases "
                        "WHERE upload_id = :upload_id"
                    ),
                    {"upload_id": reference.resource_id},
                )
                .scalars()
                .all()
            )
        assert len(before_alternate) == 4
        service.submit_run(
            alternate_trusted_context,
            "immutable-upload-pipe",
            idempotency_key="same-resource-alternate-trusted-context",
        )
        with backend.engine.connect() as connection:
            after_alternate = set(
                connection.execute(
                    sqlalchemy.text(
                        "SELECT lease_id FROM cp_input_resource_leases "
                        "WHERE upload_id = :upload_id"
                    ),
                    {"upload_id": reference.resource_id},
                )
                .scalars()
                .all()
            )
        assert len(after_alternate) == 5
        assert len(after_alternate - before_alternate) == 1
    finally:
        backend.close()


@pytest.mark.parametrize(
    ("case", "content", "max_file_bytes", "max_rows", "tamper_after_accept"),
    [
        ("empty", b"", 1024, 100, False),
        ("malformed", b"id,name\n1\n", 1024, 100, False),
        ("over_budget", b"id,name\n1,private-value\n", 8, 100, False),
        ("over_rows", b"id,name\n1,Ada\n2,Grace\n", 1024, 1, False),
        ("tampered", b"id,name\n1,private-value\n", 1024, 100, True),
    ],
)
def test_managed_worker_rejects_invalid_or_tampered_finalized_csv_uploads(
    tmp_path: Path,
    case: str,
    content: bytes,
    max_file_bytes: int,
    max_rows: int,
    tamper_after_accept: bool,
) -> None:
    database_url = _migrated_url(tmp_path)
    ctx = _context()
    target = tmp_path / f"invalid-upload-{case}.csv"
    profile = Profile(
        name=f"invalid-upload-{case}",
        security_mode="development",
        plugin_allowlist={"etlantic": None},
    )
    reference: Any = None

    def planning_context_factory(
        _ctx: ControlPlaneContext, effective_profile: Any
    ) -> PlanningContext:
        planning = PlanningContext.create(profile=effective_profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="source",
                provider="local-files",
                kind="source",
                config={"input_resource": reference.to_dict()},
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

    authorizer = MemoryAuthorizer()
    for action in ("definition.write", "run.submit", "input.read", "run.report"):
        authorizer.grant(ctx, action)
    backend = create_managed_backend(
        ManagedBackendConfig(
            database_url=database_url,
            store_id=f"managed-invalid-upload-{case}",
            profile=profile,
        ),
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
        staged = backend.input_resources.stage(
            ctx,
            content,
            media_type="text/csv",
            format="csv",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        reference = backend.input_resources.finalize(
            ctx,
            staged.upload_id,
            expected_sha256=hashlib.sha256(content).hexdigest(),
            expected_byte_length=len(content),
        )
        service = backend.api.managed_service
        assert service is not None
        service.register_definition(
            ctx,
            f"invalid-upload-{case}",
            pipeline_to_dict(definition_from_pipeline(_ManagedCsvPipeline)),
        )
        receipt = service.submit_run(
            ctx,
            f"invalid-upload-{case}",
            idempotency_key=f"invalid-upload-{case}",
        )
        if tamper_after_accept:
            tampered = content.replace(b"1,", b"2,", 1)
            assert len(tampered) == len(content)
            with backend.engine.begin() as connection:
                connection.execute(
                    sqlalchemy.text(
                        "UPDATE cp_input_uploads SET content = :content "
                        "WHERE upload_id = :upload_id"
                    ),
                    {"content": tampered, "upload_id": reference.resource_id},
                )

        host = backend.create_execution_host(owner_id=f"invalid-upload-{case}-worker")
        adapter = cast(ManagedExecutionAdapter, host.runner)

        def runtime_factory() -> PipelineRuntime:
            runtime = PipelineRuntime()
            runtime.register_source_connector(
                "local-files",
                LocalFilesSourceConnector(
                    max_file_bytes=max_file_bytes,
                    max_total_bytes=max_file_bytes,
                    max_rows=max_rows,
                ),
            )
            return runtime

        adapter.runtime_factory = runtime_factory
        assert host.tick(ctx) == 1
        report = service.get_run_report(ctx, str(receipt.resource_id))
        assert report["status"] == "failed"
        assert not target.exists()
        assert "private-value" not in json.dumps(report)
    finally:
        backend.close()


def test_managed_http_stages_finalizes_and_aborts_only_staged_input(
    tmp_path: Path,
) -> None:
    ctx = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(ctx, "input.upload")
    authorizer.grant(ctx, "input.finalize")
    authorizer.grant(ctx, "input.delete")
    app = create_managed_app(
        ManagedBackendConfig(
            database_url=_migrated_url(tmp_path),
            store_id="managed-http-upload",
            input_upload_ttl_seconds=600,
        ),
        authorizer=authorizer,
        context_factory=static_context_factory(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            environment=ctx.environment.name,
            security_domain=ctx.security_domain.domain_id,
        ),
    )
    backend = app.state.managed_backend
    other_owner = ControlPlaneContext(
        principal=Principal("other-upload-owner", kind="workload"),
        tenant=ctx.tenant,
        workspace=ctx.workspace,
        environment=ctx.environment,
        security_domain=ctx.security_domain,
        resource_owner_id="other-upload-owner",
    )
    cleanup_expiry = datetime.now(UTC) + timedelta(seconds=1)
    for _ in range(2):
        backend.input_resources.stage(
            ctx,
            b"id\n1\n",
            media_type="text/csv",
            format="csv",
            expires_at=cleanup_expiry,
        )
    other_orphan = backend.input_resources.stage(
        other_owner,
        b"id\n2\n",
        media_type="text/csv",
        format="csv",
        expires_at=cleanup_expiry,
    )
    content = b"id,name\n11,Ada\n"
    client_type = cast(Any, FastAPITestClient)
    with client_type(app) as client:
        headers = {
            "X-Principal": ctx.principal.subject,
            "Content-Type": "text/csv",
        }
        staged = client.post(
            "/v1/input-resources?format=csv", headers=headers, content=content
        )
        assert staged.status_code == 202
        upload_id = staged.json()["upload_id"]
        finalized = client.post(
            f"/v1/input-resources/{upload_id}/finalize",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "expected_sha256": hashlib.sha256(content).hexdigest(),
                "expected_byte_length": len(content),
            },
        )
        assert finalized.status_code == 200
        assert finalized.json()["sha256"] == hashlib.sha256(content).hexdigest()
        assert finalized.json()["byte_length"] == len(content)

        denied_cleanup = client.post(
            "/v1/input-resources/cleanup?limit=1", headers=headers
        )
        assert denied_cleanup.status_code == 404
        authorizer.grant(ctx, "input.cleanup")
        sleep(1.1)
        first_cleanup = client.post(
            "/v1/input-resources/cleanup?limit=1", headers=headers
        )
        assert first_cleanup.status_code == 200
        assert first_cleanup.json() == {
            "deleted_count": 1,
            "remaining_candidates": 1,
        }
        second_cleanup = client.post(
            "/v1/input-resources/cleanup?limit=1", headers=headers
        )
        assert second_cleanup.status_code == 200
        assert second_cleanup.json() == {
            "deleted_count": 1,
            "remaining_candidates": 0,
        }
        assert (
            backend.input_resources.abort(other_owner, other_orphan.upload_id) is None
        )
        empty_cleanup = client.post(
            "/v1/input-resources/cleanup?limit=1", headers=headers
        )
        assert empty_cleanup.status_code == 200
        assert empty_cleanup.json() == {
            "deleted_count": 0,
            "remaining_candidates": 0,
        }

        aborted = client.delete(f"/v1/input-resources/{upload_id}", headers=headers)
        assert aborted.status_code == 409
        cross_owner = client.delete(
            f"/v1/input-resources/{upload_id}",
            headers={"X-Principal": "different-owner"},
        )
        assert cross_owner.status_code == 404


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

        original_report_put = SqlModelRunReportStore.put
        report_persist_faulted = False

        def fail_first_successful_report_put(
            store: SqlModelRunReportStore, report: PipelineRunReport
        ) -> None:
            nonlocal report_persist_faulted
            if not report_persist_faulted and report.status is RunStatus.SUCCEEDED:
                report_persist_faulted = True
                raise RuntimeError("simulated report publication interruption")
            original_report_put(store, report)

        monkeypatch.setattr(
            SqlModelRunReportStore, "put", fail_first_successful_report_put
        )

        def fail_after_report_is_published(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("simulated worker crash after report publication")

        monkeypatch.setattr(durable, "finish_attempt", fail_after_report_is_published)
        with pytest.raises(RuntimeError, match="after report publication"):
            host.tick(ctx)
        report = service.get_run_report(ctx, receipt.resource_id)
        assert report["run_id"] == receipt.resource_id
        assert report["status"] == "succeeded"
        assert report_persist_faulted
        execution = report["metadata"]["etlantic.control_plane.execution"]
        assert execution["result_publication_status"] == "recovered"
        assert execution["effect_status"] == "committed"
        assert any(
            diagnostic["code"] == "PMEXEC410" and diagnostic["severity"] == "warning"
            for diagnostic in report["diagnostics"]
        )
        assert (
            durable.get_effect(ctx, f"{receipt.submission_id}:execution").status
            == "committed"
        )
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
        recovered_report = service.get_run_report(ctx, receipt.resource_id)
        assert recovered_report["status"] == "succeeded"
        assert target.read_text(encoding="utf-8").splitlines() == ["id", "29"]
        execution = recovered_report["metadata"]["etlantic.control_plane.execution"]
        assert {item["role"] for item in execution["attempt_history"]} == {
            "executed",
            "result_reconciled",
        }
        lineage = service.get_run_lineage(ctx, receipt.resource_id)
        attempt_nodes = [
            node for node in lineage["nodes"] if node.get("kind") == "attempt"
        ]
        assert {node["role"] for node in attempt_nodes} == {
            "executed",
            "result_reconciled",
        }
        assert len({node["attempt_id"] for node in attempt_nodes}) == 2
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


def test_managed_report_outage_recovers_fenced_result_without_rerunning(
    tmp_path: Path,
) -> None:
    database_url = _migrated_url(tmp_path)
    source = tmp_path / "report-outage-input.json"
    target = tmp_path / "report-outage-output.csv"
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
        store_id="managed-report-outage-recovery",
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
    online = False

    def use_toggled_report_store(
        original_factory: Any,
    ) -> Any:
        def factory(context: ControlPlaneContext) -> Any:
            store = original_factory(context)

            class ToggledStore:
                def get(self, run_id: str) -> Any:
                    if not online:
                        raise OSError("simulated persistent report-store outage")
                    return store.get(run_id)

                def put(self, report: PipelineRunReport) -> None:
                    if not online:
                        raise OSError("simulated persistent report-store outage")
                    store.put(report)

            return ToggledStore()

        return factory

    restarted: ManagedBackend | None = None
    try:
        service = backend.api.managed_service
        assert service is not None
        service.register_definition(
            ctx,
            "report-outage-pipe",
            pipeline_to_dict(definition_from_pipeline(_ManagedBackendPipeline)),
        )
        receipt = service.submit_run(
            ctx, "report-outage-pipe", idempotency_key="report-outage-run"
        )
        assert receipt.resource_id is not None
        durable = backend.api.durable_work
        assert durable is not None
        toggled_factory = use_toggled_report_store(backend.report_store_factory)
        backend.report_store_factory = toggled_factory
        service.report_store_factory = toggled_factory
        host = backend.create_execution_host(owner_id="report-outage-worker")
        assert host.tick(ctx) == 1
        online = True
        assert target.exists()
        online = False
        assert target.read_text(encoding="utf-8").splitlines() == ["id", "29"]
        pending = durable.pending_result_publications(ctx)
        assert len(pending) == 1
        assert pending[0].published_at is None

        # The worker process can disappear while the report store remains
        # unavailable; the authorized query recovers the committed result.
        backend.close()
        source.write_text('[{"id": 30}]', encoding="utf-8")
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
        service = restarted.api.managed_service
        assert service is not None
        toggled_factory = use_toggled_report_store(restarted.report_store_factory)
        restarted.report_store_factory = toggled_factory
        service.report_store_factory = toggled_factory
        report = service.get_run_report(ctx, receipt.resource_id)
        assert report["status"] == "succeeded"
        execution = report["metadata"]["etlantic.control_plane.execution"]
        assert execution["result_publication_status"] == "pending"
        assert any(
            diagnostic["code"] == "PMEXEC410" and diagnostic["severity"] == "warning"
            for diagnostic in report["diagnostics"]
        )

        online = True
        restarted_host = restarted.create_execution_host(
            owner_id="report-outage-restarted-worker"
        )
        assert restarted_host.tick(ctx) == 0
        restarted_durable = restarted.api.durable_work
        assert restarted_durable is not None
        assert not restarted_durable.pending_result_publications(ctx)
        assert target.read_text(encoding="utf-8").splitlines() == ["id", "29"]
        published = service.get_run_report(ctx, receipt.resource_id)
        assert (
            published["metadata"]["etlantic.control_plane.execution"][
                "result_publication_status"
            ]
            == "published"
        )
    finally:
        backend.close()
        if restarted is not None:
            restarted.close()


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


def test_managed_backend_enforces_configured_event_retention(
    tmp_path: Path,
) -> None:
    backend = _backend(
        ManagedBackendConfig(
            database_url=_migrated_url(tmp_path),
            store_id="managed-event-retention",
            event_retention_max_events_per_scope=2,
        )
    )
    try:
        events = backend.api.events
        events.append(_context(), kind="run.started", payload={"run_id": "run-1"})
        events.append(_context(), kind="run.progress", payload={"run_id": "run-1"})
        events.append(_context(), kind="run.completed", payload={"run_id": "run-1"})

        page = events.list_after_cursor(_context(), None)
        assert [event.sequence for event in page] == [2, 3]
    finally:
        backend.close()


def test_managed_backend_rejects_invalid_event_retention_configuration() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        ManagedBackendConfig(
            database_url="sqlite:///managed.db",
            event_retention_max_events_per_scope=0,
        )


def test_managed_backend_action_lease_exceeds_every_preparation_deadline() -> None:
    with pytest.raises(ValueError, match="action_job_lease_seconds"):
        ManagedBackendConfig(
            database_url="sqlite:///managed.db",
            action_job_max_deadline_seconds=300,
            action_job_lease_seconds=300,
        )
    with pytest.raises(ValueError, match="action_job_lease_seconds"):
        ManagedBackendConfig(
            database_url="sqlite:///managed.db",
            action_job_lease_seconds=cast(Any, True),
        )


def test_managed_backend_artifact_retention_is_scoped_and_survives_restart(
    tmp_path: Path,
) -> None:
    database_url = _migrated_url(tmp_path)
    artifact_root = tmp_path / "managed-retention-artifacts"
    config = ManagedBackendConfig(
        database_url=database_url,
        store_id="managed-artifact-retention",
        artifact_root=str(artifact_root),
        run_artifact_retention_seconds=60,
        run_artifact_cleanup_batch_size=1,
    )
    backend = _backend(config)
    ctx = _context()
    other_ctx = ControlPlaneContext(
        principal=Principal("other-retention-owner"),
        tenant=TenantRef("other-retention-tenant"),
        workspace=WorkspaceRef("other-retention-tenant", "other-retention-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("other-retention-domain"),
    )
    now = datetime(2026, 1, 2, tzinfo=UTC)
    ended_at = now - timedelta(days=2)
    try:
        run_id = "retained-run"
        identity = "result:private"
        artifact = artifact_storage_path(
            managed_artifact_workspace(ctx, run_id, artifact_root=artifact_root),
            identity,
        )
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('[{"id": 1}]', encoding="utf-8")
        report = PipelineRunReport(
            pipeline_id="retention-pipeline",
            plan_id="retention-plan",
            run_id=run_id,
            intent=RunIntent.STANDARD,
            profile="test",
            status=RunStatus.SUCCEEDED,
            started_at=ended_at - timedelta(minutes=1),
            ended_at=ended_at,
            artifacts=(ArtifactResult(identity, "result", "durable"),),
            plan_fingerprint="b" * 64,
        )
        backend.report_store_factory(ctx).put(report)

        other_run_id = "other-scope-retained-run"
        other_artifact = artifact_storage_path(
            managed_artifact_workspace(
                other_ctx, other_run_id, artifact_root=artifact_root
            ),
            "result:other",
        )
        other_artifact.parent.mkdir(parents=True, exist_ok=True)
        other_artifact.write_text('[{"id": 2}]', encoding="utf-8")
        backend.report_store_factory(other_ctx).put(
            PipelineRunReport(
                pipeline_id="retention-pipeline",
                plan_id="retention-plan",
                run_id=other_run_id,
                intent=RunIntent.STANDARD,
                profile="test",
                status=RunStatus.SUCCEEDED,
                started_at=ended_at - timedelta(minutes=1),
                ended_at=ended_at,
                artifacts=(ArtifactResult("result:other", "result", "durable"),),
                plan_fingerprint="c" * 64,
            )
        )

        first = backend.cleanup_expired_run_artifacts(ctx, now=now)
        assert first.enabled is True
        assert first.deleted_artifacts == 1
        assert first.completed_reports == 1
        assert first.remaining_candidates is False
        assert not artifact.exists()
        assert other_artifact.exists()

        retained = backend.report_store_factory(ctx).get(run_id)
        assert retained is not None
        assert retained.status is RunStatus.SUCCEEDED
        assert retained.artifacts[0].status == "expired"
        assert retained.metadata["etlantic.control_plane.artifact_retention"] == (
            "complete"
        )
        assert [item.run_id for item in backend.report_store_factory(ctx).list()] == [
            run_id
        ]
    finally:
        backend.close()

    restarted = _backend(config)
    try:
        store = restarted.report_store_factory(ctx)
        retained = store.get("retained-run")
        assert retained is not None
        assert retained.status is RunStatus.SUCCEEDED
        assert retained.artifacts[0].status == "expired"
        assert [item.run_id for item in store.list()] == ["retained-run"]
        repeat = restarted.cleanup_expired_run_artifacts(ctx, now=now)
        assert repeat.processed_reports == 0
        assert repeat.deleted_artifacts == 0
    finally:
        restarted.close()
