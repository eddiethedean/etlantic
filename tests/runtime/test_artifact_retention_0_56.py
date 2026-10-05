"""Durable run-artifact cleanup and recovery qualification."""

from __future__ import annotations

import os
from collections.abc import Callable
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
from etlantic.reports.file_store import FileReportStore
from etlantic.reports.model import ArtifactResult, PipelineRunReport
from etlantic.reports.retention import (
    RUN_ARTIFACT_RETENTION_DETAILS_KEY,
    RUN_ARTIFACT_RETENTION_STATE_KEY,
)
from etlantic.reports.store import ReportStore
from etlantic.runtime.artifact_coordination import record_artifact_ownership
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


@pytest.mark.parametrize("store_kind", ["memory", "file"])
@pytest.mark.parametrize("busy_reports", [1, 3])
def test_busy_workspace_does_not_consume_ready_report_batch(
    tmp_path: Path, store_kind: str, busy_reports: int
) -> None:
    from dataclasses import replace

    from etlantic.reports.file_store import FileReportStore
    from etlantic.reports.retention import ARTIFACT_STORAGE_RUN_ID_KEY
    from etlantic.runtime.artifact_coordination import artifact_workspace_lock

    ctx, now = _ctx(), datetime.now(UTC)
    root = tmp_path / "artifacts"
    store = (
        FileReportStore(tmp_path / "reports") if store_kind == "file" else ReportStore()
    )
    pinned = _write_artifact(ctx, root, "busy", "shared")
    for index in range(busy_reports):
        store.put(
            replace(
                _report(
                    f"busy-{index}",
                    ended_at=now - timedelta(days=3),
                    artifacts=(ArtifactResult("shared", "output", "durable"),),
                ),
                metadata={ARTIFACT_STORAGE_RUN_ID_KEY: "busy"},
            )
        )
    ready = [
        _write_artifact(ctx, root, f"ready-{index}", "output") for index in range(2)
    ]
    for index in range(2):
        store.put(
            _report(
                f"ready-{index}",
                ended_at=now - timedelta(days=2),
                artifacts=(ArtifactResult("output", "output", "durable"),),
            )
        )
    workspace = managed_artifact_workspace(ctx, "busy", artifact_root=root)
    with artifact_workspace_lock(workspace):
        for index in range(2):
            result = cleanup_expired_run_artifacts(
                ctx,
                report_store=store,
                artifact_root=root,
                retention_seconds=60,
                limit=1,
                now=now,
            )
            assert result.processed_reports == result.completed_reports == 1
            assert result.deleted_artifacts == 1 and result.remaining_candidates
            assert not ready[index].exists() and pinned.is_file()
            if index == 0:
                assert ready[1].is_file()
        for index in range(busy_reports):
            saved = store.get(f"busy-{index}")
            assert saved is not None and saved.artifacts[0].status == "available"
    for _ in range(busy_reports):
        result = cleanup_expired_run_artifacts(
            ctx,
            report_store=store,
            artifact_root=root,
            retention_seconds=60,
            limit=1,
            now=now,
        )
        assert result.processed_reports == 1
    assert not pinned.exists()
    assert not cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=root,
        retention_seconds=60,
        limit=1,
        now=now,
    ).remaining_candidates


def test_cleanup_still_bounds_processed_reports_without_durable_references(
    tmp_path: Path,
) -> None:
    ctx, now = _ctx(), datetime.now(UTC)
    store = ReportStore()
    for index in range(3):
        store.put(_report(str(index), ended_at=now - timedelta(days=2), artifacts=()))
    for index in range(3):
        result = cleanup_expired_run_artifacts(
            ctx,
            report_store=store,
            artifact_root=tmp_path,
            retention_seconds=60,
            limit=1,
            now=now,
        )
        assert result.processed_reports == result.completed_reports == 1
        assert result.deleted_artifacts == 0
        assert result.remaining_candidates == (index < 2)


def test_idle_orphan_scan_inventory_does_not_scale_with_workspace_count(
    tmp_path: Path,
) -> None:
    ctx, now = _ctx(), datetime.now(UTC)
    artifact_root = tmp_path / "artifacts"
    report_root = tmp_path / "reports"
    store = FileReportStore(report_root)
    for index in range(20):
        run_id = f"fresh-{index}"
        report = _report(
            run_id,
            ended_at=now,
            artifacts=(ArtifactResult(f"artifact-{index}", "output", "durable"),),
        )
        workspace = managed_artifact_workspace(ctx, run_id, artifact_root=artifact_root)
        record_artifact_ownership(workspace, report)
        store.put(report)
        _write_artifact(ctx, artifact_root, run_id, f"artifact-{index}")

    inventory_reads = 0

    def fresh_store() -> FileReportStore:
        nonlocal inventory_reads
        inventory_reads += 1
        return FileReportStore(report_root)

    result = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=artifact_root,
        retention_seconds=60,
        report_store_factory=fresh_store,
        now=now,
    )

    assert not result.remaining_candidates
    # The pass performs bounded final inventory checks, not one refresh per
    # workspace with a live owner.
    assert inventory_reads <= 2

    expired_at = now + timedelta(days=2)
    completed = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=artifact_root,
        retention_seconds=60,
        report_store_factory=fresh_store,
        now=expired_at,
    )
    assert completed.completed_reports == 20
    assert completed.deleted_artifacts == 20
    assert not completed.remaining_candidates

    inventory_reads = 0
    idle = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=artifact_root,
        retention_seconds=60,
        report_store_factory=fresh_store,
        now=expired_at,
    )
    assert not idle.remaining_candidates
    # Completed owners now have no artifact bytes and must not force a report
    # inventory reload for every old workspace on subsequent polls.
    assert inventory_reads <= 2


@pytest.mark.skipif(os.name != "posix", reason="POSIX read-only mode")
def test_cleanup_without_durable_artifacts_does_not_create_workspace(
    tmp_path: Path,
) -> None:
    ctx, now = _ctx(), datetime.now(UTC)
    store = ReportStore()
    store.put(_report("memory-only", ended_at=now - timedelta(days=2), artifacts=()))
    artifact_root = tmp_path / "readonly-artifacts"
    artifact_root.mkdir()
    artifact_root.chmod(0o555)
    try:
        result = cleanup_expired_run_artifacts(
            ctx,
            report_store=store,
            artifact_root=artifact_root,
            retention_seconds=60,
            now=now,
        )
        assert result.completed_reports == 1
        assert not result.remaining_candidates
        assert list(artifact_root.iterdir()) == []
    finally:
        artifact_root.chmod(0o755)


def test_unpublished_only_cleanup_is_bounded_and_resumes_after_restart(
    tmp_path: Path,
) -> None:
    from etlantic.reports.file_store import FileReportStore
    from etlantic.runtime.artifact_coordination import (
        artifact_workspace_lock,
        record_artifact_ownership,
    )

    ctx, now = _ctx(), datetime.now(UTC)
    root = tmp_path / "artifacts"
    identities = ("one", "two", "three")
    paths = [_write_artifact(ctx, root, "orphan", identity) for identity in identities]
    report = _report(
        "orphan",
        ended_at=now - timedelta(days=2),
        artifacts=tuple(
            ArtifactResult(identity, identity, "durable") for identity in identities
        ),
    )
    workspace = managed_artifact_workspace(ctx, report.run_id, artifact_root=root)
    with artifact_workspace_lock(workspace):
        record_artifact_ownership(workspace, report)
    for index in range(len(paths)):
        result = cleanup_expired_run_artifacts(
            ctx,
            report_store=FileReportStore(tmp_path / "reports"),
            artifact_root=root,
            retention_seconds=60,
            now=now,
            limit=1,
        )
        assert result.deleted_artifacts == 1 and result.failed_artifacts == 0
        assert result.processed_reports == 0 and result.completed_reports == 0
        assert sum(path.exists() for path in paths) == len(paths) - index - 1
        assert result.remaining_candidates == (index + 1 < len(paths))
    final = cleanup_expired_run_artifacts(
        ctx,
        report_store=FileReportStore(tmp_path / "reports"),
        artifact_root=root,
        retention_seconds=60,
        now=now,
        limit=1,
    )
    assert not final.remaining_candidates and final.deleted_artifacts == 0


def test_unpublished_cleanup_transfers_shared_file_to_retained_owner(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    from etlantic.runtime.artifact_coordination import (
        apply_artifact_expiry,
        artifact_workspace_lock,
        record_artifact_ownership,
    )

    ctx, now = _ctx(), datetime.now(UTC)
    path = _write_artifact(ctx, tmp_path, "workspace", "shared")
    old = _report(
        "expired-owner",
        ended_at=now - timedelta(days=2),
        artifacts=(ArtifactResult("shared", "output", "durable"),),
    )
    young = replace(old, run_id="young-owner", ended_at=now)
    workspace = managed_artifact_workspace(ctx, "workspace", artifact_root=tmp_path)
    with artifact_workspace_lock(workspace):
        record_artifact_ownership(workspace, old)
        record_artifact_ownership(workspace, young)
    first = cleanup_expired_run_artifacts(
        ctx,
        report_store=ReportStore(),
        artifact_root=tmp_path,
        retention_seconds=60,
        now=now,
        limit=1,
    )
    assert first.deleted_artifacts == 0 and path.is_file()
    assert apply_artifact_expiry(workspace, old).artifacts[0].status == "expired"
    assert apply_artifact_expiry(workspace, young).artifacts[0].status == "available"
    final = cleanup_expired_run_artifacts(
        ctx,
        report_store=ReportStore(),
        artifact_root=tmp_path,
        retention_seconds=60,
        now=now + timedelta(days=1),
        limit=1,
    )
    assert final.deleted_artifacts == 1 and not path.exists()
    assert not final.remaining_candidates


def test_unpublished_cleanup_retries_failed_deletion_without_reviving_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import cast

    import etlantic.runtime.artifact_retention as retention
    from etlantic.runtime.artifact_coordination import (
        apply_artifact_expiry,
        artifact_workspace_lock,
        record_artifact_ownership,
    )

    ctx, now = _ctx(), datetime.now(UTC)
    path = _write_artifact(ctx, tmp_path, "orphan", "result")
    report = _report(
        "orphan",
        ended_at=now - timedelta(days=2),
        artifacts=(ArtifactResult("result", "output", "durable"),),
    )
    workspace = managed_artifact_workspace(ctx, "orphan", artifact_root=tmp_path)
    with artifact_workspace_lock(workspace):
        record_artifact_ownership(workspace, report)
    remove = cast(Callable[[Path], bool], vars(retention)["_remove_artifact_file"])

    def fail(_path: Path) -> bool:
        raise OSError("transient deletion failure")

    monkeypatch.setattr(retention, "_remove_artifact_file", fail)
    first = cleanup_expired_run_artifacts(
        ctx,
        report_store=ReportStore(),
        artifact_root=tmp_path,
        retention_seconds=60,
        now=now,
        limit=1,
    )
    assert first.failed_artifacts == 1 and first.remaining_candidates and path.exists()
    assert apply_artifact_expiry(workspace, report).artifacts[0].status == "expired"
    monkeypatch.setattr(retention, "_remove_artifact_file", remove)
    final = cleanup_expired_run_artifacts(
        ctx,
        report_store=ReportStore(),
        artifact_root=tmp_path,
        retention_seconds=60,
        now=now,
        limit=1,
    )
    assert (
        final.deleted_artifacts == 1
        and not final.remaining_candidates
        and not path.exists()
    )


@pytest.mark.parametrize("scope_dimension", ["tenant", "workspace", "security_domain"])
def test_unpublished_workspace_discovery_stays_inside_accepted_scope(
    tmp_path: Path,
    scope_dimension: str,
) -> None:
    from dataclasses import replace

    from etlantic.runtime.artifact_coordination import (
        artifact_workspace_lock,
        record_artifact_ownership,
    )

    ctx, now = _ctx(), datetime.now(UTC)
    foreign = (
        replace(
            ctx, tenant=TenantRef("other"), workspace=WorkspaceRef("other", "workspace")
        )
        if scope_dimension == "tenant"
        else replace(ctx, workspace=WorkspaceRef(ctx.tenant.tenant_id, "other"))
        if scope_dimension == "workspace"
        else replace(ctx, security_domain=SecurityDomain("other"))
    )
    paths: list[Path] = []
    for scope in (ctx, foreign):
        paths.append(_write_artifact(scope, tmp_path, "orphan", "result"))
        workspace = managed_artifact_workspace(scope, "orphan", artifact_root=tmp_path)
        with artifact_workspace_lock(workspace):
            record_artifact_ownership(
                workspace,
                _report(
                    "orphan",
                    ended_at=now - timedelta(days=2),
                    artifacts=(ArtifactResult("result", "output", "durable"),),
                ),
            )
    result = cleanup_expired_run_artifacts(
        ctx,
        report_store=ReportStore(),
        artifact_root=tmp_path,
        retention_seconds=60,
        now=now,
    )
    assert (
        result.deleted_artifacts == 1 and not paths[0].exists() and paths[1].is_file()
    )


@pytest.mark.parametrize("store_kind", ["memory", "file"])
def test_deferred_references_do_not_hide_unfinished_or_unrelated_cleanup(
    tmp_path: Path,
    store_kind: str,
) -> None:
    from dataclasses import replace

    from etlantic.reports.file_store import FileReportStore
    from etlantic.reports.retention import ARTIFACT_STORAGE_RUN_ID_KEY
    from etlantic.runtime.artifact_coordination import (
        artifact_workspace_lock,
        record_artifact_ownership,
    )

    ctx, now = _ctx(), datetime.now(UTC)
    root = tmp_path / "artifacts"
    shared = tuple(
        _write_artifact(ctx, root, "oldest", str(index)) for index in range(3)
    )
    ready_path = _write_artifact(ctx, root, "ready", "ready")
    parent = _report(
        "oldest",
        ended_at=now - timedelta(days=3),
        artifacts=tuple(
            ArtifactResult(str(index), str(index), "durable") for index in range(3)
        ),
    )
    child = replace(
        parent,
        run_id="unpublished",
        ended_at=now,
        metadata={ARTIFACT_STORAGE_RUN_ID_KEY: parent.run_id},
    )
    store = (
        FileReportStore(tmp_path / "reports") if store_kind == "file" else ReportStore()
    )
    store.put(parent)
    store.put(
        _report(
            "ready",
            ended_at=now - timedelta(days=2),
            artifacts=(ArtifactResult("ready", "output", "durable"),),
        )
    )
    workspace = managed_artifact_workspace(ctx, parent.run_id, artifact_root=root)
    with artifact_workspace_lock(workspace):
        record_artifact_ownership(workspace, child)
    for index in range(4):
        result = cleanup_expired_run_artifacts(
            ctx,
            report_store=store,
            artifact_root=root,
            retention_seconds=86400,
            limit=1,
            now=now + timedelta(seconds=index),
        )
        assert result.deleted_artifacts <= 1 and result.failed_artifacts == 0
    assert not ready_path.exists() and all(path.is_file() for path in shared)
    persisted = store.get(parent.run_id)
    assert persisted is not None
    assert all(artifact.status == "expired" for artifact in persisted.artifacts)
    assert persisted.metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY]["attempts"] == 3
    assert (
        persisted.metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY]["retry_after"]
        == (now + timedelta(days=1)).isoformat()
    )
    # Deferred work survives restart and becomes eligible at its protecting
    # owner's expiry. No individual pass may exceed the shared file budget.
    if store_kind == "file":
        store = FileReportStore(tmp_path / "reports")
    deleted = 0
    remaining = True
    for _ in range(6):
        result = cleanup_expired_run_artifacts(
            ctx,
            report_store=store,
            artifact_root=root,
            retention_seconds=86400,
            limit=1,
            now=now + timedelta(days=2),
        )
        assert result.deleted_artifacts <= 1
        deleted += result.deleted_artifacts
        remaining = result.remaining_candidates
    assert deleted == 3 and not any(path.exists() for path in shared)
    assert not remaining


def _crash_during_coordination_write(workspace: Path, kind: str) -> None:
    import os

    import etlantic.io_policy as io
    from etlantic.runtime.artifact_coordination import (
        artifact_workspace_lock,
        expire_artifact_reference,
        record_artifact_ownership,
    )

    def crash_before_replace(*_args: Any) -> None:
        os._exit(7)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(io, "_replace_with_retry", crash_before_replace)
    with artifact_workspace_lock(workspace):
        if kind == "ownership":
            record_artifact_ownership(
                workspace,
                _report(
                    "crashed",
                    ended_at=datetime.now(UTC),
                    artifacts=(ArtifactResult("shared", "output", "durable"),),
                ),
            )
        else:
            expire_artifact_reference(workspace, "crashed", "shared")


@pytest.mark.parametrize("kind", ["ownership", "expiry"])
def test_coordination_writes_recover_after_process_death(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    import multiprocessing
    from dataclasses import replace

    import etlantic.runtime.artifact_coordination as coordination
    from etlantic.io_policy import SafeIoPolicy, write_text_safe

    workspace = managed_artifact_workspace(_ctx(), "crashed", artifact_root=tmp_path)
    process = multiprocessing.get_context("spawn").Process(
        target=_crash_during_coordination_write, args=(workspace, kind)
    )
    process.start()
    process.join(10)
    if process.is_alive():
        process.terminate()
        process.join(10)
    assert process.exitcode == 7

    def short_lock_write(
        path: str | Path, text: str, policy: SafeIoPolicy, *, run_id: str
    ) -> Any:
        return write_text_safe(
            path, text, replace(policy, lock_timeout_seconds=0.1), run_id=run_id
        )

    monkeypatch.setattr(coordination, "write_text_safe", short_lock_write)
    # Also tolerate an orphaned exclusive-create lock from the previous
    # implementation, rather than requiring operators to remove it manually.
    for temporary in workspace.rglob("*.tmp"):
        filename = temporary.name.removeprefix(".").split(".json.")[0] + ".json.lock"
        (temporary.parent / filename).write_text("dead-worker", encoding="utf-8")
    with coordination.artifact_workspace_lock(workspace, blocking=False) as acquired:
        assert acquired
        report = _report(
            "crashed",
            ended_at=datetime.now(UTC),
            artifacts=(ArtifactResult("shared", "output", "durable"),),
        )
        coordination.record_artifact_ownership(workspace, report)
        coordination.expire_artifact_reference(workspace, report.run_id, "shared")
        expired = coordination.apply_artifact_expiry(workspace, report)
        assert expired.artifacts[0].status == "expired"
        assert (
            coordination.retained_artifact_ownership(
                workspace, datetime.now(UTC) - timedelta(days=1), report_run_ids=set()
            )
            == set()
        )


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


@pytest.mark.parametrize("young_run", ["parent", "child"])
@pytest.mark.parametrize(
    "store_kind",
    ["memory", "file", pytest.param("sqlmodel", marks=pytest.mark.sqlmodel)],
)
def test_shared_artifacts_survive_until_the_last_retained_reference_expires(
    tmp_path: Path, young_run: str, store_kind: str
) -> None:
    from dataclasses import replace

    from etlantic.reports.file_store import FileReportStore
    from etlantic.reports.retention import ARTIFACT_STORAGE_RUN_ID_KEY

    ctx = _ctx()
    now = datetime(2026, 1, 2, tzinfo=UTC)
    reopen: Callable[[], Any] | None = None
    if store_kind == "sqlmodel":
        pytest.importorskip("sqlalchemy")
        pytest.importorskip("sqlmodel")
        from etlantic_sqlmodel.control_plane import (
            SqlModelRunReportStore,
            create_sqlite_engine,
        )
        from etlantic_sqlmodel.migrations import apply_migrations

        engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'reports.db'}")
        apply_migrations(engine)
        store = SqlModelRunReportStore(engine, ctx)

        def reopen_store() -> Any:
            return SqlModelRunReportStore(engine, ctx)

        reopen = reopen_store
    elif store_kind == "file":
        store = FileReportStore(tmp_path / "reports")
    else:
        store = ReportStore()
    root = tmp_path / "artifacts"
    shared = _write_artifact(ctx, root, "parent", "shared")
    unrelated = _write_artifact(ctx, root, "unrelated", "shared")
    for run_id in ("parent", "child", "unrelated"):
        report = _report(
            run_id,
            ended_at=now if run_id == young_run else now - timedelta(days=2),
            artifacts=(ArtifactResult("shared", "output", "durable"),),
        )
        if run_id == "child":
            report = replace(report, metadata={ARTIFACT_STORAGE_RUN_ID_KEY: "parent"})
        store.put(report)

    first = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=root,
        retention_seconds=60,
        limit=1,
        now=now,
    )
    assert first.completed_reports == 1
    assert shared.exists()
    # Complete the other old report, even with a one-artifact deletion budget.
    cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=root,
        retention_seconds=60,
        limit=1,
        now=now,
    )
    assert shared.exists() and not unrelated.exists()
    old_run = "child" if young_run == "parent" else "parent"
    expired = store.get(old_run)
    retained = store.get(young_run)
    assert expired is not None and expired.artifacts[0].status == "expired"
    assert retained is not None and retained.artifacts[0].status == "available"
    if store_kind == "file":
        store = FileReportStore(tmp_path / "reports")
    elif reopen is not None:
        store = reopen()
    last = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=root,
        retention_seconds=60,
        limit=1,
        now=now + timedelta(days=1),
    )
    assert last.deleted_artifacts == 1 and last.completed_reports == 1
    assert not shared.exists()
    assert last.remaining_candidates is False


def test_invalid_storage_identity_never_marks_files_cleaned(tmp_path: Path) -> None:
    from dataclasses import replace

    from etlantic.reports.retention import ARTIFACT_STORAGE_RUN_ID_KEY

    ctx = _ctx()
    now = datetime(2026, 1, 2, tzinfo=UTC)
    path = _write_artifact(ctx, tmp_path, "invalid", "result")
    report = replace(
        _report(
            "invalid",
            ended_at=now - timedelta(days=2),
            artifacts=(ArtifactResult("result", "output", "durable"),),
        ),
        metadata={ARTIFACT_STORAGE_RUN_ID_KEY: ""},
    )
    store = ReportStore()
    store.put(report)
    with pytest.raises(ValueError, match="storage run identity"):
        cleanup_expired_run_artifacts(
            ctx,
            report_store=store,
            artifact_root=tmp_path,
            retention_seconds=60,
            now=now,
        )
    assert path.exists()
    saved = store.get("invalid")
    assert saved is not None and saved.artifacts[0].status == "available"
    assert saved.metadata.get(RUN_ARTIFACT_RETENTION_STATE_KEY) != "complete"


def _publish_shared_child(
    artifact_root: str,
    report_root: str,
    report_json: str,
    ready: Any,
    release: Any,
    crash: bool = False,
) -> None:
    from etlantic.reports.file_store import FileReportStore
    from etlantic.reports.model import PipelineRunReport
    from etlantic.runtime.artifact_coordination import artifact_workspace_lock

    workspace = managed_artifact_workspace(
        _ctx(), "parent", artifact_root=artifact_root
    )
    with artifact_workspace_lock(workspace):
        ready.set()
        if crash:
            import os

            os._exit(7)
        if not release.wait(15):
            raise TimeoutError("Test publisher was not released")
        import json

        FileReportStore(Path(report_root)).put(
            PipelineRunReport.from_dict(json.loads(report_json))
        )


def test_cleanup_coordinates_with_another_process_and_refreshes_file_inventory(
    tmp_path: Path,
) -> None:
    import multiprocessing
    from dataclasses import replace

    from etlantic.reports.file_store import FileReportStore
    from etlantic.reports.retention import ARTIFACT_STORAGE_RUN_ID_KEY

    ctx = _ctx()
    now = datetime.now(UTC)
    root = tmp_path / "artifacts"
    reports = tmp_path / "reports"
    path = _write_artifact(ctx, root, "parent", "shared")
    parent = _report(
        "parent",
        ended_at=now - timedelta(days=2),
        artifacts=(ArtifactResult("shared", "output", "durable"),),
    )
    store = FileReportStore(reports)
    store.put(parent)
    child = replace(
        parent,
        run_id="child",
        ended_at=now,
        metadata={ARTIFACT_STORAGE_RUN_ID_KEY: "parent"},
    )
    process_context = multiprocessing.get_context("spawn")
    ready = process_context.Event()
    release = process_context.Event()
    publisher = process_context.Process(
        target=_publish_shared_child,
        args=(str(root), str(reports), child.to_json(), ready, release),
    )
    publisher.start()
    try:
        assert ready.wait(10)
        busy = cleanup_expired_run_artifacts(
            ctx, report_store=store, artifact_root=root, retention_seconds=60, now=now
        )
        assert busy.remaining_candidates and busy.processed_reports == 0
        assert path.is_file()
        release.set()
        publisher.join(10)
        assert publisher.exitcode == 0
        # This instance was opened before the other process wrote the child.
        assert store.get("child") is None
        finished = cleanup_expired_run_artifacts(
            ctx, report_store=store, artifact_root=root, retention_seconds=60, now=now
        )
        assert finished.completed_reports == 1 and finished.deleted_artifacts == 0
        fresh = FileReportStore(reports)
        old = fresh.get("parent")
        retained = fresh.get("child")
        assert old is not None and old.artifacts[0].status == "expired"
        assert retained is not None and retained.artifacts[0].status == "available"
        assert path.is_file()
        # An abruptly exited publisher must not leave a permanent reservation.
        ready.clear()
        release.clear()
        publisher = process_context.Process(
            target=_publish_shared_child,
            args=(str(root), str(reports), child.to_json(), ready, release, True),
        )
        publisher.start()
        assert ready.wait(10)
        publisher.join(10)
        assert publisher.exitcode == 7
        after_crash = cleanup_expired_run_artifacts(
            ctx,
            report_store=store,
            artifact_root=root,
            retention_seconds=60,
            now=now + timedelta(days=1),
        )
        assert after_crash.deleted_artifacts == 1 and not path.exists()
    finally:
        release.set()
        if publisher.is_alive():
            publisher.terminate()
        publisher.join(10)


@pytest.mark.parametrize("reconcile_parent", [False, True])
def test_unpublished_child_ownership_survives_and_eventually_expires(
    tmp_path: Path,
    reconcile_parent: bool,
) -> None:
    from dataclasses import replace

    from etlantic.reports.file_store import FileReportStore
    from etlantic.reports.retention import ARTIFACT_STORAGE_RUN_ID_KEY
    from etlantic.runtime.artifact_coordination import (
        artifact_workspace_lock,
        record_artifact_ownership,
    )

    ctx = _ctx()
    now = datetime.now(UTC)
    root = tmp_path / "artifacts"
    shared = _write_artifact(ctx, root, "parent", "shared")
    reports = tmp_path / "reports"
    store = FileReportStore(reports)
    parent = _report(
        "parent",
        ended_at=now - timedelta(days=2),
        artifacts=(ArtifactResult("shared", "output", "durable"),),
    )
    parent = replace(parent, metadata={ARTIFACT_STORAGE_RUN_ID_KEY: "parent"})
    store.put(parent)
    child = replace(
        parent,
        run_id="unpublished-child",
        ended_at=now,
        metadata={ARTIFACT_STORAGE_RUN_ID_KEY: "parent"},
    )
    workspace = managed_artifact_workspace(ctx, "parent", artifact_root=root)
    with artifact_workspace_lock(workspace):
        record_artifact_ownership(workspace, child)
    assert store.get(child.run_id) is None
    first = cleanup_expired_run_artifacts(
        ctx, report_store=store, artifact_root=root, retention_seconds=60, now=now
    )
    expired = store.get("parent")
    assert expired is not None and expired.artifacts[0].status == "expired"
    assert shared.is_file() and first.deleted_artifacts == 0
    assert first.remaining_candidates and first.completed_reports == 0
    if reconcile_parent:
        import hashlib

        from etlantic.control_plane.durable_models import ResultPublicationRecord
        from etlantic.runtime.managed_execution import ManagedExecutionAdapter

        snapshot = parent.to_json()
        publication = ResultPublicationRecord(
            submission_id="parent-submission",
            attempt_id="parent-attempt",
            run_id=parent.run_id,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            report_json=snapshot,
            report_sha256=hashlib.sha256(snapshot.encode()).hexdigest(),
            created_at=parent.ended_at.isoformat() if parent.ended_at else "",
        )
        from etlantic.runtime.managed_errors import ExecutionRejected

        with pytest.raises(ExecutionRejected, match="accepted submission"):
            ManagedExecutionAdapter(
                artifact_root=root,
                report_store_factory=lambda _: FileReportStore(reports),
            ).publish_result_publication(ctx, publication)
        reconciled = FileReportStore(reports).get(parent.run_id)
        assert reconciled is not None
        assert reconciled.metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] == "running"
        assert reconciled.metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY]["attempts"] == 1
        assert reconciled.metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY][
            "deferred_artifact_ids"
        ] == ["shared"]
    # Even if the provider never recovers, the deferred physical cleanup must
    # complete after the ownership window, including across process restarts.
    restarted = FileReportStore(reports)
    final = cleanup_expired_run_artifacts(
        ctx,
        report_store=restarted,
        artifact_root=root,
        retention_seconds=60,
        now=now + timedelta(days=1),
    )
    assert final.completed_reports == 1 and final.deleted_artifacts == 1
    assert not shared.exists() and not final.remaining_candidates


@pytest.mark.parametrize("intent", [RunIntent.STANDARD, RunIntent.RESUME])
def test_accepted_report_without_envelope_is_rejected_for_all_intents(
    intent: RunIntent,
) -> None:
    from dataclasses import replace

    from etlantic.control_plane.durable_models import SubmissionRecord
    from etlantic.runtime.managed_execution import resolve_managed_artifact_report

    now = datetime.now(UTC)
    report = replace(
        _report(
            "legacy",
            ended_at=now,
            artifacts=(ArtifactResult("result", "output", "durable"),),
        ),
        intent=intent,
    )
    ctx = _ctx()
    submission = SubmissionRecord(
        submission_id="legacy-submission",
        tenant_id=ctx.tenant.tenant_id,
        workspace_id=ctx.workspace.workspace_id,
        principal_subject=ctx.principal.subject,
        operation="run.submit",
        idempotency_key="legacy",
        created_at=now.isoformat(),
        plan_fingerprint=report.plan_fingerprint or "",
        run_id=report.run_id,
    )
    with pytest.raises(ValueError, match="canonical execution envelope"):
        resolve_managed_artifact_report(report, submission)


@pytest.mark.parametrize(
    "metadata",
    [
        (
            {
                "etlantic.control_plane.execution": {"submission_id": "accepted"},
                "etlantic.control_plane.artifact_storage_run_id": "another-run",
            }
        ),
        {"etlantic.control_plane.artifact_storage_run_id": "another-run"},
    ],
)
def test_managed_retention_defers_unverified_artifact_workspace(
    tmp_path: Path, metadata: dict[str, Any]
) -> None:
    from dataclasses import replace

    from etlantic.runtime.managed_execution import ManagedExecutionAdapter

    now = datetime.now(UTC)
    ctx = _ctx()
    reports = FileReportStore(tmp_path / "reports")
    report = replace(
        _report(
            "ordinary-run",
            ended_at=now - timedelta(days=2),
            artifacts=(ArtifactResult("result", "output", "durable"),),
        ),
        metadata=metadata,
    )
    reports.put(report)
    artifact_path = _write_artifact(
        ctx, tmp_path / "artifacts", "ordinary-run", "result"
    )
    adapter = ManagedExecutionAdapter(
        artifact_root=tmp_path / "artifacts",
        report_root=tmp_path / "reports",
        report_store_factory=lambda _: reports,
        run_artifact_retention_seconds=60,
    )

    result = adapter.cleanup_expired_run_artifacts(ctx, now=now)
    assert result.completed_reports == 0
    assert result.deleted_artifacts == 0
    assert artifact_path.exists()


def test_missing_submission_does_not_abort_retention_inventory(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    ctx = _ctx()
    reports = ReportStore()
    reports.put(
        _report(
            "missing-submission",
            ended_at=now - timedelta(days=2),
            artifacts=(ArtifactResult("result", "output", "durable"),),
        )
    )

    def missing_submission(_report: PipelineRunReport) -> PipelineRunReport:
        from etlantic.control_plane.errors import ControlPlaneError

        raise ControlPlaneError.not_found("Submission not found")

    result = cleanup_expired_run_artifacts(
        ctx,
        report_store=reports,
        artifact_root=tmp_path / "artifacts",
        retention_seconds=60,
        now=now,
        report_resolver=missing_submission,
    )
    assert result.completed_reports == 0
    assert result.deleted_artifacts == 0


def test_persisted_unverified_marker_does_not_suppress_cleanup(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    now = datetime.now(UTC)
    ctx = _ctx()
    reports = ReportStore()
    report = replace(
        _report(
            "forged-marker",
            ended_at=now - timedelta(days=2),
            artifacts=(ArtifactResult("result", "output", "durable"),),
        ),
        metadata={"etlantic.internal.artifact_retention_unverified": True},
    )
    reports.put(report)
    artifact_path = _write_artifact(
        ctx, tmp_path / "artifacts", "forged-marker", "result"
    )

    result = cleanup_expired_run_artifacts(
        ctx,
        report_store=reports,
        artifact_root=tmp_path / "artifacts",
        retention_seconds=60,
        now=now,
        report_resolver=lambda item: item,
    )

    assert result.completed_reports == 1
    assert result.deleted_artifacts == 1
    assert not artifact_path.exists()


def test_unverified_shared_reference_protects_artifact_file(tmp_path: Path) -> None:
    from dataclasses import replace

    now = datetime.now(UTC)
    ctx = _ctx()
    reports = ReportStore()
    artifact_root = tmp_path / "artifacts"
    storage_run_id = "parent-workspace"
    artifact = ArtifactResult("shared-output", "output", "durable")
    old_report = replace(
        _report(
            "expired-owner",
            ended_at=now - timedelta(days=2),
            artifacts=(artifact,),
        ),
        metadata={"etlantic.control_plane.artifact_storage_run_id": storage_run_id},
    )
    retained_reference = replace(
        _report(
            "retained-reference",
            ended_at=now,
            artifacts=(artifact,),
        ),
        metadata={"etlantic.control_plane.artifact_storage_run_id": storage_run_id},
    )
    reports.put(old_report)
    reports.put(retained_reference)
    artifact_path = _write_artifact(
        ctx, artifact_root, storage_run_id, artifact.identity
    )

    def reject_retained_reference(report: PipelineRunReport) -> PipelineRunReport:
        if report.run_id == retained_reference.run_id:
            raise ValueError("Unverified retained reference")
        return report

    result = cleanup_expired_run_artifacts(
        ctx,
        report_store=reports,
        artifact_root=artifact_root,
        retention_seconds=60,
        now=now,
        report_resolver=reject_retained_reference,
    )
    assert result.completed_reports == 1
    assert result.deleted_artifacts == 0
    assert artifact_path.exists()
