"""PostgreSQL qualification for durable report artifact cleanup state."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("etlantic_sqlmodel")

import sqlalchemy

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.reports.model import ArtifactResult, PipelineRunReport
from etlantic.runtime.artifact_retention import cleanup_expired_run_artifacts
from etlantic.runtime.artifacts import artifact_storage_path
from etlantic.runtime.managed_execution import managed_artifact_workspace
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus
from etlantic_sqlmodel.control_plane.report_stores import SqlModelRunReportStore
from etlantic_sqlmodel.migrations import upgrade


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal("postgresql-retention-test"),
        tenant=TenantRef("postgresql-retention-tenant"),
        workspace=WorkspaceRef("postgresql-retention-tenant", "retention-workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("retention-tests"),
    )


def test_postgresql_artifact_retention_failure_retry_survives_restart(
    tmp_path: Path,
) -> None:
    database_url = os.environ.get("ETLANTIC_CP_TEST_URL")
    if not database_url:
        pytest.skip("ETLANTIC_CP_TEST_URL must point to isolated PostgreSQL")

    engine = sqlalchemy.create_engine(database_url)
    assert upgrade(engine) == "013_durable_submission_scope_backfill_0_56"
    ctx = _context()
    run_id = f"retention-{uuid4().hex}"
    identity = "result:managed-output"
    artifact_root = tmp_path / "postgresql-artifacts"
    path = artifact_storage_path(
        managed_artifact_workspace(ctx, run_id, artifact_root=artifact_root),
        identity,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[{"id": 1}]', encoding="utf-8")
    now = datetime(2026, 1, 2, tzinfo=UTC)
    report = PipelineRunReport(
        pipeline_id="postgresql-retention-pipeline",
        plan_id="postgresql-retention-plan",
        run_id=run_id,
        intent=RunIntent.STANDARD,
        profile="test",
        status=RunStatus.SUCCEEDED,
        started_at=now - timedelta(days=2, minutes=1),
        ended_at=now - timedelta(days=2),
        artifacts=(ArtifactResult(identity, "result", "durable"),),
        plan_fingerprint=uuid4().hex + uuid4().hex,
    )
    store = SqlModelRunReportStore(engine, ctx)
    store.put(report)

    path.unlink()
    path.mkdir()
    failed = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=artifact_root,
        retention_seconds=60,
        limit=1,
        now=now,
    )
    assert failed.failed_artifacts == 1
    interrupted = store.get(run_id)
    assert interrupted is not None
    assert interrupted.status is RunStatus.SUCCEEDED
    assert interrupted.artifacts[0].status == "available"
    assert interrupted.metadata["etlantic.control_plane.artifact_retention"] == (
        "failed"
    )

    path.rmdir()
    path.write_text('[{"id": 1}]', encoding="utf-8")
    retried = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=artifact_root,
        retention_seconds=60,
        limit=1,
        now=now,
    )
    assert retried.completed_reports == 1
    assert not path.exists()
    completed = store.get(run_id)
    assert completed is not None
    assert completed.status is RunStatus.SUCCEEDED
    assert completed.artifacts[0].status == "expired"
    assert completed.metadata["etlantic.control_plane.artifact_retention"] == (
        "complete"
    )
    engine.dispose()

    restarted_engine = sqlalchemy.create_engine(database_url)
    try:
        restarted = SqlModelRunReportStore(restarted_engine, ctx).get(run_id)
        assert restarted is not None
        assert restarted.status is RunStatus.SUCCEEDED
        assert restarted.artifacts[0].status == "expired"
        assert restarted.metadata["etlantic.control_plane.artifact_retention"] == (
            "complete"
        )
    finally:
        restarted_engine.dispose()
