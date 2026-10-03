"""Managed repair and backfill through the live PostgreSQL worker path."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("etlantic_sql")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from etlantic import Data, Extract, Load, Pipeline, PipelineRuntime, Profile
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.connectors.capabilities import (
    IDEMPOTENCY,
    SOURCE_PARTITIONED,
    WRITE_PARTITION_REPLACE,
)
from etlantic.control_plane import (
    ControlPlaneContext,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemoryEventStore,
    MemorySubmissionStore,
)
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.reports.model import PipelineRunReport
from etlantic.reports.retention import ARTIFACT_STORAGE_RUN_ID_KEY
from etlantic.runtime.artifact_retention import cleanup_expired_run_artifacts
from etlantic.runtime.artifacts import artifact_storage_path
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.managed_execution import (
    ManagedExecutionAdapter,
    managed_artifact_workspace,
    managed_report_store,
)
from etlantic.runtime.request import MaterializationPolicy, RunRequest
from etlantic.service import ManagedApplicationService
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)
from etlantic_sql.live_postgresql import (
    LivePostgresSinkConnector,
    LivePostgresSourceConnector,
)


class _PartitionRow(Data):
    id: str
    payload: str
    partition_key: str


class _PartitionPipeline(Pipeline):
    source: Extract[_PartitionRow] = Extract(asset="source")
    result: Load[_PartitionRow] = Load(input=source, asset="sink")


def _context() -> ControlPlaneContext:
    from etlantic.control_plane import (
        EnvironmentRef,
        Principal,
        SecurityDomain,
        TenantRef,
        WorkspaceRef,
    )

    return ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="ws-1"),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def test_managed_repair_and_backfill_execute_selected_postgresql_partitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = os.environ.get("ETLANTIC_SQL_TEST_URL")
    if not database_url:
        pytest.skip("requires an isolated live PostgreSQL URL")
    monkeypatch.setenv("ETLANTIC_SQL_URL", database_url)

    ctx = _context()
    schema_suffix = uuid.uuid4().hex[:10]
    source_table = f"phase056_partition_source_{schema_suffix}"
    sink_table = f"phase056_partition_sink_{schema_suffix}"
    engine = create_engine(database_url, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                f'CREATE TABLE public."{source_table}" '
                "(id text PRIMARY KEY, payload text NOT NULL, partition_key text NOT NULL)"
            )
        )
        connection.execute(
            text(
                f'CREATE TABLE public."{sink_table}" '
                "(id text PRIMARY KEY, payload text NOT NULL, partition_key text NOT NULL)"
            )
        )
        connection.execute(
            text(
                f'CREATE TABLE public."{source_table}_effects" '
                "(effect_id text PRIMARY KEY, intent_fingerprint text NOT NULL, "
                "publication_id text NOT NULL UNIQUE, row_count bigint NOT NULL, "
                "committed_at timestamptz NOT NULL DEFAULT now())"
            )
        )
        connection.execute(
            text(
                f'CREATE TABLE public."{sink_table}_effects" '
                "(effect_id text PRIMARY KEY, intent_fingerprint text NOT NULL, "
                "publication_id text NOT NULL UNIQUE, row_count bigint NOT NULL, "
                "committed_at timestamptz NOT NULL DEFAULT now())"
            )
        )
        connection.execute(
            text(
                f'INSERT INTO public."{source_table}" VALUES '
                "('a-old', 'old-a', 'a'), ('b-old', 'old-b', 'b')"
            )
        )

    authz = MemoryAuthorizer()
    for action in (
        "definition.write",
        "definition.read",
        "definition.validate",
        "definition.plan",
        "run.submit",
        "run.read",
        "run.report",
        "run.actions",
        "run.lineage",
        "run.repair",
        "run.backfill",
        "run.artifacts",
        "run.artifact.content",
    ):
        authz.grant(ctx, action)

    definitions = MemoryDefinitionRepository()
    submissions = MemorySubmissionStore()
    durable = MemoryDurableWorkStore()
    events = MemoryEventStore()
    service = ManagedApplicationService(
        authorizer=authz,
        definitions=definitions,
        submissions=submissions,
        durable_work=durable,
        events=events,
        profile="development",
        report_root=tmp_path / "reports",
        artifact_root=tmp_path / "artifacts",
    )

    def planning_context(
        _ctx: ControlPlaneContext, profile: Profile
    ) -> PlanningContext:
        planning = PlanningContext.create(profile=profile)
        planning.registry.register_binding(
            BindingDescriptor(
                binding="source",
                provider="postgresql",
                location=source_table,
                kind="source",
                config={"partition_column": "partition_key"},
                required_capabilities=(SOURCE_PARTITIONED,),
            )
        )
        planning.registry.register_binding(
            BindingDescriptor(
                binding="sink",
                provider="postgresql",
                location=sink_table,
                kind="sink",
                config={
                    "mode": "append",
                    "partition_column": "partition_key",
                    "effect_table": f"public.{sink_table}_effects",
                },
                required_capabilities=(WRITE_PARTITION_REPLACE, IDEMPOTENCY),
            )
        )
        return planning

    service.planning_context_factory = planning_context
    service.register_definition(
        ctx,
        "partition-pipeline",
        pipeline_to_dict(definition_from_pipeline(_PartitionPipeline)),
    )

    def runtime_factory() -> PipelineRuntime:
        runtime = PipelineRuntime()
        runtime.register_source_connector("postgresql", LivePostgresSourceConnector())
        runtime.register_sink_connector("postgresql", LivePostgresSinkConnector())
        return runtime

    adapter = ManagedExecutionAdapter(
        runtime_factory=runtime_factory,
        report_root=tmp_path / "reports",
        artifact_root=tmp_path / "artifacts",
    )
    checkpoint_id = f"checkpoint:{schema_suffix}"

    def checkpointed_runner(
        worker_ctx: ControlPlaneContext, **kwargs: Any
    ) -> PipelineRunReport:
        report = adapter(worker_ctx, **kwargs)
        if kwargs["submission"].operation == "run.submit":
            durable.compare_and_swap_checkpoint(
                worker_ctx,
                checkpoint_id,
                expected_version=None,
                value_fingerprint="a" * 64,
                attempt_id=kwargs["attempt_id"],
                fencing_token=kwargs["fencing_token"],
            )
        return report

    host = ExecutionHost(
        durable,
        owner_id=f"partition-worker-{schema_suffix}",
        runner=checkpointed_runner,
    )

    try:
        parent = service.submit_run(
            ctx,
            "partition-pipeline",
            idempotency_key=f"parent-{schema_suffix}",
            request=RunRequest(materialization=MaterializationPolicy.DURABLE),
        )
        assert isinstance(parent.resource_id, str)
        assert host.tick(ctx) == 1
        assert service.get_run_status(ctx, parent.resource_id)["status"] == "completed"

        with engine.begin() as connection:
            connection.execute(
                text(
                    f'UPDATE public."{source_table}" SET payload = :payload '
                    "WHERE id = 'a-old'"
                ),
                {"payload": "repaired-a"},
            )
        api = ETLanticAPI(
            authorizer=authz,
            definitions=definitions,
            submissions=submissions,
            events=events,
            durable_work=durable,
            managed_service=service,
            profile="development",
            context_factory=membership_context_factory(
                {"alice": ("tenant-a", "ws-1", "development", "default")}
            ),
            principal_dependency=principal_from_header,
        )
        client = TestClient(create_app(api))
        response = client.post(
            f"/v1/runs/{parent.resource_id}/repair",
            headers={
                "X-Principal": "alice",
                "Idempotency-Key": f"repair-{schema_suffix}",
            },
            json={
                "invalidated_partition_ids": {"source": ["a"], "result": ["a"]},
                "checkpoint_id": checkpoint_id,
            },
        )
        assert response.status_code == 202, response.text
        repair = response.json()
        assert host.tick(ctx) == 1
        repair_run_id = repair["resource_id"]
        assert isinstance(repair_run_id, str)
        assert service.get_run_status(ctx, repair_run_id)["status"] == "completed"
        artifacts = service.list_run_artifacts(ctx, repair_run_id)
        assert artifacts and all(item["content_available"] for item in artifacts)
        for artifact in artifacts:
            content, media_type = service.get_run_artifact_content(
                ctx, repair_run_id, artifact["artifact_id"]
            )
            assert media_type == "application/json"
            assert json.loads(content) == [
                {"id": "a-old", "payload": "repaired-a", "partition_key": "a"}
            ]
        repair_record = durable.get_submission(ctx, repair["submission_id"])
        repair_envelope = json.loads(repair_record.input_snapshot or "{}")
        evidence_refs = repair_envelope["evidence_refs"]
        assert evidence_refs["command"] == "repair"
        assert evidence_refs["parent_run_id"] == parent.resource_id
        assert evidence_refs["parent_submission_id"] == parent.submission_id
        assert evidence_refs["parent_attempt_id"]

        with engine.begin() as connection:
            connection.execute(
                text(
                    f'UPDATE public."{source_table}" SET payload = :payload '
                    "WHERE id = 'b-old'"
                ),
                {"payload": "backfilled-b"},
            )
        backfill = service.backfill_run(
            ctx,
            parent.resource_id,
            idempotency_key=f"backfill-{schema_suffix}",
            partition_ids={"source": ["b"], "result": ["b"]},
        )
        assert isinstance(backfill.resource_id, str)
        assert (
            service.backfill_run(
                ctx,
                parent.resource_id,
                idempotency_key=f"backfill-{schema_suffix}",
                partition_ids={"source": ["b"], "result": ["b"]},
            ).to_dict()
            == backfill.to_dict()
        )
        assert host.tick(ctx) == 1
        assert (
            service.get_run_status(ctx, backfill.resource_id)["status"] == "completed"
        )
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f'SELECT id, payload, partition_key FROM public."{sink_table}" '
                    "ORDER BY id"
                )
            ).all()
        assert rows == [
            ("a-old", "repaired-a", "a"),
            ("b-old", "backfilled-b", "b"),
        ]
        assert {
            "from": parent.resource_id,
            "to": repair_run_id,
            "kind": "repair",
        } in service.get_run_lineage(ctx, repair_run_id)["edges"]
        assert {
            "from": parent.resource_id,
            "to": backfill.resource_id,
            "kind": "backfill",
        } in service.get_run_lineage(ctx, backfill.resource_id)["edges"]
        reports = managed_report_store(ctx, report_root=tmp_path / "reports")
        repair_report = reports.get(repair_run_id)
        parent_report = reports.get(parent.resource_id)
        assert repair_report is not None and parent_report is not None
        assert repair_report.metadata[ARTIFACT_STORAGE_RUN_ID_KEY] == parent.resource_id
        workspace = managed_artifact_workspace(
            ctx, parent.resource_id, artifact_root=tmp_path / "artifacts"
        )
        parent_files = [
            artifact_storage_path(workspace, item.identity)
            for item in parent_report.artifacts
            if item.strategy == "durable"
        ]
        repair_files = [
            artifact_storage_path(workspace, item.identity)
            for item in repair_report.artifacts
            if item.strategy == "durable"
        ]
        assert parent_files and repair_files
        now = datetime.now(UTC)
        ended = now - timedelta(days=2)
        reports.put(
            replace(
                repair_report, started_at=ended - timedelta(minutes=1), ended_at=ended
            )
        )
        cleanup = cleanup_expired_run_artifacts(
            ctx,
            report_store=reports,
            artifact_root=tmp_path / "artifacts",
            retention_seconds=60,
            now=now,
        )
        assert cleanup.completed_reports == 1
        assert all(path.exists() for path in parent_files)
        assert not any(path.exists() for path in repair_files)
    finally:
        with engine.begin() as connection:
            for table in (
                source_table,
                sink_table,
                f"{source_table}_effects",
                f"{sink_table}_effects",
            ):
                connection.execute(text(f'DROP TABLE IF EXISTS public."{table}"'))
        engine.dispose()
