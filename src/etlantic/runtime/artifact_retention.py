"""Bounded retention for durable artifacts produced by managed runs."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from etlantic.control_plane.models import ControlPlaneContext
from etlantic.reports.model import PipelineRunReport
from etlantic.reports.retention import (
    RUN_ARTIFACT_RETENTION_DETAILS_KEY,
    RUN_ARTIFACT_RETENTION_STATE_KEY,
    TERMINAL_RUN_STATUSES,
    ArtifactRetentionResult,
    artifact_storage_run_id,
)
from etlantic.runtime.artifacts import artifact_storage_path
from etlantic.runtime.managed_execution import managed_artifact_workspace

_MAX_BATCH = 1000


def cleanup_expired_run_artifacts(
    ctx: ControlPlaneContext,
    *,
    report_store: Any,
    artifact_root: str | Path | None,
    retention_seconds: int | None,
    limit: int = 100,
    now: datetime | None = None,
) -> ArtifactRetentionResult:
    """Expire old artifact references and remove files without retained owners.

    The report's run status remains an execution result. Cleanup progresses in
    its own metadata state machine (running, failed, complete), and each
    removed artifact is recorded before the next file is touched. Missing
    files are treated as already-cleaned work, making process recovery safe.
    Shared files remain available through their unexpired report references.
    """
    if retention_seconds is not None and (
        type(retention_seconds) is not int or retention_seconds < 1
    ):
        raise ValueError("retention_seconds must be a positive integer or None")
    if type(limit) is not int or not 1 <= limit <= _MAX_BATCH:
        raise ValueError(f"limit must be between 1 and {_MAX_BATCH}")
    if retention_seconds is None:
        return ArtifactRetentionResult(enabled=False)

    current = now or datetime.now(UTC)
    current = (
        current.replace(tzinfo=UTC)
        if current.tzinfo is None
        else current.astimezone(UTC)
    )
    cutoff = current - timedelta(seconds=retention_seconds)
    candidates: list[PipelineRunReport] = report_store.list_expired_artifact_reports(
        cutoff=cutoff, limit=limit
    )
    if not candidates:
        return ArtifactRetentionResult(enabled=True)
    # A child and its parent can name the same physical file. Retire an old
    # report's reference while leaving bytes owned by a still-retained report.
    protected: set[tuple[str, str]] = set()
    for retained in report_store.list():
        ended = retained.ended_at
        if ended is not None:
            ended = ended.replace(tzinfo=UTC) if ended.tzinfo is None else ended
        if (
            retained.status.value in TERMINAL_RUN_STATUSES
            and ended is not None
            and ended <= cutoff
        ):
            continue
        storage_id = artifact_storage_run_id(retained)
        protected.update(
            (storage_id, artifact.identity)
            for artifact in retained.artifacts
            if artifact.strategy == "durable" and artifact.status != "expired"
        )

    processed_reports = 0
    completed_reports = 0
    deleted_artifacts = 0
    failed_artifacts = 0
    touched_artifacts = 0

    for report_index, report in enumerate(candidates):
        if report.metadata.get(RUN_ARTIFACT_RETENTION_STATE_KEY) == "complete":
            continue

        metadata = dict(report.metadata)
        old_details: object = metadata.get(RUN_ARTIFACT_RETENTION_DETAILS_KEY)
        details: dict[str, Any] = (
            cast(dict[str, Any], old_details) if isinstance(old_details, dict) else {}
        )
        attempts: object = details.get("attempts", 0)
        attempts = attempts + 1 if type(attempts) is int and attempts >= 0 else 1
        details.update(
            {
                "attempts": attempts,
                "updated_at": current.isoformat(),
                "failure_code": None,
                "failed_artifacts": 0,
            }
        )
        metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] = "running"
        metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY] = details
        working = replace(report, metadata=metadata)
        report_store.put(working)
        processed_reports += 1

        report_failed = 0
        interrupted = False
        artifacts = list(working.artifacts)
        for artifact_index, artifact in enumerate(artifacts):
            if artifact.strategy != "durable" or artifact.status == "expired":
                continue
            if touched_artifacts >= limit:
                interrupted = True
                break

            touched_artifacts += 1
            workspace = managed_artifact_workspace(
                ctx, artifact_storage_run_id(working), artifact_root=artifact_root
            )
            path = artifact_storage_path(workspace, artifact.identity)
            try:
                removed = (
                    False
                    if (artifact_storage_run_id(working), artifact.identity)
                    in protected
                    else _remove_artifact_file(path)
                )
            except (OSError, RuntimeError, ValueError):
                report_failed += 1
                failed_artifacts += 1
                continue

            if removed:
                deleted_artifacts += 1
            artifacts[artifact_index] = replace(artifact, status="expired")
            working = replace(working, artifacts=tuple(artifacts))
            report_store.put(working)

        if interrupted:
            # Keep the durable running marker so the next bounded pass resumes.
            break

        metadata = dict(working.metadata)
        details = dict(metadata.get(RUN_ARTIFACT_RETENTION_DETAILS_KEY) or {})
        details.update(
            {
                "updated_at": current.isoformat(),
                "failed_artifacts": report_failed,
                "failure_code": (
                    "filesystem_cleanup_failed" if report_failed else None
                ),
            }
        )
        metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY] = details
        if report_failed:
            metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] = "failed"
        else:
            metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] = "complete"
            completed_reports += 1
        report_store.put(replace(working, metadata=metadata))

        if touched_artifacts >= limit and report_index + 1 < len(candidates):
            break

    remaining_candidates = bool(
        report_store.list_expired_artifact_reports(cutoff=cutoff, limit=1)
    )

    return ArtifactRetentionResult(
        enabled=True,
        processed_reports=processed_reports,
        completed_reports=completed_reports,
        deleted_artifacts=deleted_artifacts,
        failed_artifacts=failed_artifacts,
        remaining_candidates=remaining_candidates,
    )


def _remove_artifact_file(path: Path) -> bool:
    """Unlink one path under its trusted run workspace without following it."""
    workspace = path.parent
    root = workspace.parents[3]
    relative_directories = workspace.relative_to(root).parts
    resolved_root = root.resolve()

    if (
        os.name == "posix"
        and hasattr(os, "O_DIRECTORY")
        and hasattr(os, "O_NOFOLLOW")
        and os.open in os.supports_dir_fd
        and os.unlink in os.supports_dir_fd
    ):
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            root_fd = os.open(resolved_root, flags)
        except FileNotFoundError:
            return False
        directory_fd = root_fd
        try:
            for part in relative_directories:
                next_fd = os.open(part, flags, dir_fd=directory_fd)
                if directory_fd != root_fd:
                    os.close(directory_fd)
                directory_fd = next_fd
            try:
                os.unlink(path.name, dir_fd=directory_fd)
            except FileNotFoundError:
                return False
            return True
        except FileNotFoundError:
            return False
        finally:
            if directory_fd != root_fd:
                os.close(directory_fd)
            os.close(root_fd)

    for directory in (*reversed(workspace.parents[:3]), workspace):
        if directory.is_symlink():
            raise OSError("artifact path contains a symbolic link")
    resolved_workspace = workspace.resolve()
    if not resolved_workspace.is_relative_to(resolved_root):
        raise OSError("artifact workspace escaped its configured root")

    # unlink() removes a symlink entry itself and never follows its target.
    if not path.exists() and not path.is_symlink():
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


__all__ = ["ArtifactRetentionResult", "cleanup_expired_run_artifacts"]
