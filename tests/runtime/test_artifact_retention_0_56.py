"""Durable run-artifact cleanup and recovery qualification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.reports.model import ArtifactResult, PipelineRunReport
from etlantic.reports.retention import (
    RUN_ARTIFACT_RETENTION_DETAILS_KEY,
    RUN_ARTIFACT_RETENTION_STATE_KEY,
)
from etlantic.reports.store import ReportStore
from etlantic.runtime.artifact_retention import (
    cleanup_expired_run_artifacts,
)
from etlantic.runtime.artifacts import artifact_storage_path
from etlantic.runtime.managed_execution import managed_artifact_workspace
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus


def _ctx() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="artifact-retention-test"),
        tenant=TenantRef(tenant_id="retention-tenant"),
        workspace=WorkspaceRef(
            tenant_id="retention-tenant", workspace_id="retention-workspace"
        ),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(domain_id="retention-tests"),
    )


def _report(
    run_id: str,
    *,
    ended_at: datetime,
    artifacts: tuple[ArtifactResult, ...],
    status: RunStatus = RunStatus.SUCCEEDED,
) -> PipelineRunReport:
    return PipelineRunReport(
        pipeline_id="retention-pipeline",
        plan_id="retention-plan",
        run_id=run_id,
        intent=RunIntent.STANDARD,
        profile="test",
        status=status,
        started_at=ended_at - timedelta(minutes=1),
        ended_at=ended_at,
        artifacts=artifacts,
        plan_fingerprint="a" * 64,
    )


def _write_artifact(
    ctx: ControlPlaneContext, root: Path, run_id: str, identity: str
) -> Path:
    workspace = managed_artifact_workspace(ctx, run_id, artifact_root=root)
    path = artifact_storage_path(workspace, identity)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"private": false}', encoding="utf-8")
    return path


def test_artifact_cleanup_is_bounded_resumable_and_preserves_run_result(
    tmp_path: Path,
) -> None:
    ctx = _ctx()
    now = datetime(2026, 1, 2, tzinfo=UTC)
    ended = now - timedelta(days=2)
    store = ReportStore()
    first = _write_artifact(ctx, tmp_path, "run-bounded", "result:first")
    second = _write_artifact(ctx, tmp_path, "run-bounded", "result:second")
    store.put(
        _report(
            "run-bounded",
            ended_at=ended,
            artifacts=(
                ArtifactResult("result:first", "first", "durable"),
                ArtifactResult("result:ephemeral", "ephemeral", "memory"),
                ArtifactResult("result:second", "second", "durable"),
            ),
        )
    )

    first_pass = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=tmp_path,
        retention_seconds=24 * 60 * 60,
        limit=1,
        now=now,
    )

    assert first_pass.enabled is True
    assert first_pass.processed_reports == 1
    assert first_pass.deleted_artifacts == 1
    assert first_pass.remaining_candidates is True
    assert not first.exists()
    assert second.exists()
    partial = store.get("run-bounded")
    assert partial is not None
    assert partial.status is RunStatus.SUCCEEDED
    assert partial.artifacts[0].status == "expired"
    assert partial.artifacts[1].status == "available"
    assert partial.artifacts[2].status == "available"
    assert partial.metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] == "running"

    second_pass = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=tmp_path,
        retention_seconds=24 * 60 * 60,
        limit=1,
        now=now,
    )

    assert second_pass.deleted_artifacts == 1
    assert second_pass.completed_reports == 1
    assert second_pass.remaining_candidates is False
    assert not second.exists()
    complete = store.get("run-bounded")
    assert complete is not None
    assert complete.status is RunStatus.SUCCEEDED
    assert [item.status for item in complete.artifacts] == [
        "expired",
        "available",
        "expired",
    ]
    assert complete.metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] == "complete"
    assert complete.metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY]["attempts"] == 2

    repeated = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=tmp_path,
        retention_seconds=24 * 60 * 60,
        limit=1,
        now=now,
    )
    assert repeated.processed_reports == 0
    assert store.get("run-bounded") == complete


def test_artifact_cleanup_records_failure_and_retries_without_changing_run_status(
    tmp_path: Path,
) -> None:
    ctx = _ctx()
    now = datetime(2026, 1, 2, tzinfo=UTC)
    artifact = _write_artifact(ctx, tmp_path, "run-retry", "result:retry")
    store = ReportStore()
    store.put(
        _report(
            "run-retry",
            ended_at=now - timedelta(days=2),
            artifacts=(ArtifactResult("result:retry", "retry", "durable"),),
        )
    )

    artifact.unlink()
    artifact.mkdir()
    child = artifact / "keep-during-failed-cleanup"
    child.write_text("still present", encoding="utf-8")
    failed = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=tmp_path,
        retention_seconds=24 * 60 * 60,
        now=now,
    )
    assert failed.failed_artifacts == 1
    assert failed.completed_reports == 0
    assert artifact.is_dir()
    assert child.read_text(encoding="utf-8") == "still present"
    report = store.get("run-retry")
    assert report is not None
    assert report.status is RunStatus.SUCCEEDED
    assert report.artifacts[0].status == "available"
    assert report.metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] == "failed"
    assert report.metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY]["failure_code"] == (
        "filesystem_cleanup_failed"
    )

    child.unlink()
    artifact.rmdir()
    artifact.write_text("retry after correcting the filesystem", encoding="utf-8")
    retried = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=tmp_path,
        retention_seconds=24 * 60 * 60,
        now=now,
    )
    assert retried.deleted_artifacts == 1
    assert retried.completed_reports == 1
    assert not artifact.exists()
    recovered = store.get("run-retry")
    assert recovered is not None
    assert recovered.status is RunStatus.SUCCEEDED
    assert recovered.artifacts[0].status == "expired"
    assert recovered.metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] == "complete"
    assert recovered.metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY]["attempts"] == 2


def test_artifact_cleanup_treats_missing_files_as_completed_work(
    tmp_path: Path,
) -> None:
    ctx = _ctx()
    now = datetime(2026, 1, 2, tzinfo=UTC)
    store = ReportStore()
    store.put(
        _report(
            "run-missing",
            ended_at=now - timedelta(days=2),
            artifacts=(ArtifactResult("missing", "missing", "durable"),),
        )
    )

    result = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=tmp_path,
        retention_seconds=24 * 60 * 60,
        now=now,
    )

    report = store.get("run-missing")
    assert result.failed_artifacts == 0
    assert result.completed_reports == 1
    assert report is not None
    assert report.status is RunStatus.SUCCEEDED
    assert report.artifacts[0].status == "expired"


def test_artifact_cleanup_unlinks_symlink_without_following_target(
    tmp_path: Path,
) -> None:
    if not hasattr(Path, "symlink_to"):
        pytest.skip("symlinks are unavailable")
    root = tmp_path / "artifacts"
    ctx = _ctx()
    target = tmp_path / "outside.json"
    target.write_text("preserve", encoding="utf-8")
    link = _write_artifact(ctx, root, "run-symlink", "result:link")
    link.unlink()
    link.symlink_to(target)
    now = datetime(2026, 1, 2, tzinfo=UTC)
    store = ReportStore()
    store.put(
        _report(
            "run-symlink",
            ended_at=now - timedelta(days=2),
            artifacts=(ArtifactResult("result:link", "link", "durable"),),
        )
    )

    result = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=root,
        retention_seconds=24 * 60 * 60,
        now=now,
    )

    assert result.completed_reports == 1
    assert not link.exists()
    assert target.read_text(encoding="utf-8") == "preserve"


@pytest.mark.parametrize("retention_seconds", [0, -1, True, 1.5])
def test_artifact_cleanup_rejects_invalid_retention(retention_seconds: Any) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        cleanup_expired_run_artifacts(
            _ctx(),
            report_store=ReportStore(),
            artifact_root=None,
            retention_seconds=retention_seconds,
        )


@pytest.mark.parametrize("limit", [0, -1, 1001, True, 1.5])
def test_artifact_cleanup_rejects_invalid_batch_limit(limit: Any) -> None:
    with pytest.raises(ValueError, match="between 1 and 1000"):
        cleanup_expired_run_artifacts(
            _ctx(),
            report_store=ReportStore(),
            artifact_root=None,
            retention_seconds=60,
            limit=limit,
        )


def test_disabled_artifact_cleanup_does_not_open_a_report_store() -> None:
    result = cleanup_expired_run_artifacts(
        _ctx(),
        report_store=None,
        artifact_root=None,
        retention_seconds=None,
    )
    assert result.enabled is False
    assert result.processed_reports == 0
