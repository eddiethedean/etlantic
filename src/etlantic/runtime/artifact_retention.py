"""Bounded retention for durable artifacts produced by managed runs."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from etlantic.control_plane.models import ControlPlaneContext
from etlantic.reports.file_store import FileReportStore
from etlantic.reports.model import PipelineRunReport
from etlantic.reports.retention import (
    ARTIFACT_STORAGE_RUN_ID_KEY,
    RUN_ARTIFACT_RETENTION_DETAILS_KEY,
    RUN_ARTIFACT_RETENTION_STATE_KEY,
    TERMINAL_RUN_STATUSES,
    ArtifactRetentionResult,
    artifact_storage_run_id,
)
from etlantic.runtime.artifact_coordination import (
    apply_artifact_expiry,
    artifact_workspace_lock,
    complete_unpublished_artifact,
    discover_artifact_workspaces,
    expire_artifact_reference,
    expire_unpublished_artifact,
    read_artifact_ownership,
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
    report_resolver: Callable[[PipelineRunReport], PipelineRunReport] | None = None,
    report_store_factory: Callable[[], Any] | None = None,
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

    def inventory() -> list[PipelineRunReport]:
        # File providers cache their inventory. Reopen inside the workspace
        # lock so a completed child published by another process is visible.
        if report_store_factory is not None:
            return report_store_factory().list()
        if isinstance(report_store, FileReportStore):
            return FileReportStore(report_store.root, policy=report_store.policy).list()
        return report_store.list()

    def normalize(report: PipelineRunReport) -> PipelineRunReport:
        missing = ARTIFACT_STORAGE_RUN_ID_KEY not in report.metadata
        resolved = report_resolver(report) if report_resolver is not None else report
        if (
            missing
            and report.intent.value in {"resume", "repair", "backfill"}
            and ARTIFACT_STORAGE_RUN_ID_KEY not in resolved.metadata
        ):
            raise ValueError(
                "Legacy lifecycle report requires accepted storage evidence"
            )
        if (
            missing
            and artifact_storage_run_id(resolved) != report.run_id
            and (
                report.metadata.get(RUN_ARTIFACT_RETENTION_STATE_KEY) == "complete"
                or any(
                    artifact.strategy == "durable" and artifact.status == "expired"
                    for artifact in report.artifacts
                )
            )
        ):
            # Old cleanup marked the child directory complete without touching
            # its actual files. Requeue those references during normalization.
            resolved = replace(
                resolved,
                artifacts=tuple(
                    replace(artifact, status="available")
                    if artifact.strategy == "durable"
                    else artifact
                    for artifact in resolved.artifacts
                ),
                metadata={
                    **resolved.metadata,
                    RUN_ARTIFACT_RETENTION_STATE_KEY: "pending",
                },
            )
        return resolved

    def pending(report: PipelineRunReport) -> bool:
        ended = report.ended_at
        if ended is not None and ended.tzinfo is None:
            ended = ended.replace(tzinfo=UTC)
        return (
            report.status.value in TERMINAL_RUN_STATUSES
            and ended is not None
            and ended <= cutoff
            and report.metadata.get(RUN_ARTIFACT_RETENTION_STATE_KEY) != "complete"
        )

    def eligible(report: PipelineRunReport) -> bool:
        if not pending(report):
            return False
        raw_details: object = report.metadata.get(RUN_ARTIFACT_RETENTION_DETAILS_KEY)
        if raw_details is not None and not isinstance(raw_details, dict):
            raise ValueError("Artifact cleanup details are invalid")
        details = cast(dict[str, Any], raw_details) if raw_details is not None else {}
        retry_after: object = details.get("retry_after")
        if retry_after is None:
            return True
        if not isinstance(retry_after, str):
            raise ValueError("Artifact cleanup retry time is invalid")
        retry = datetime.fromisoformat(retry_after)
        retry = retry.replace(tzinfo=UTC) if retry.tzinfo is None else retry
        return retry <= current

    def protected_references(
        reports: list[PipelineRunReport], workspace: Path
    ) -> set[str]:
        protected: set[str] = set()
        for retained in reports:
            ended = retained.ended_at
            if ended is not None and ended.tzinfo is None:
                ended = ended.replace(tzinfo=UTC)
            if (
                retained.status.value in TERMINAL_RUN_STATUSES
                and ended is not None
                and ended <= cutoff
            ):
                continue
            if (
                managed_artifact_workspace(
                    ctx, artifact_storage_run_id(retained), artifact_root=artifact_root
                )
                != workspace
            ):
                continue
            retained = apply_artifact_expiry(workspace, retained)
            protected.update(
                hashlib.sha256(artifact.identity.encode()).hexdigest()
                for artifact in retained.artifacts
                if artifact.strategy == "durable" and artifact.status != "expired"
            )
        return protected

    processed_reports = 0
    completed_reports = 0
    deleted_artifacts = 0
    failed_artifacts = 0
    touched_artifacts = 0

    busy = False
    orphan_remaining = False
    scope = managed_artifact_workspace(
        ctx, "discovery", artifact_root=artifact_root
    ).parent
    for workspace in discover_artifact_workspaces(scope):
        if touched_artifacts >= limit:
            orphan_remaining = True
            break
        with artifact_workspace_lock(workspace, blocking=False) as acquired:
            if not acquired:
                busy = True
                continue
            reports = [normalize(item) for item in inventory()]
            ownership = read_artifact_ownership(
                workspace,
                cutoff,
                report_run_ids={item.run_id for item in reports},
                retention_seconds=retention_seconds,
            )
            protected = protected_references(reports, workspace) | ownership.protected
            for reference in ownership.expired:
                if touched_artifacts >= limit:
                    orphan_remaining = True
                    break
                touched_artifacts += 1
                try:
                    expire_unpublished_artifact(workspace, reference)
                    if reference.identity not in protected and _remove_artifact_file(
                        workspace / f"{reference.identity}.json"
                    ):
                        deleted_artifacts += 1
                    complete_unpublished_artifact(workspace, reference)
                except (OSError, RuntimeError, ValueError):
                    failed_artifacts += 1
                    orphan_remaining = True

    # Fresh rows may have changed while orphan work was processed. Filter
    # deferred retry times before truncating, so they cannot hide ready rows.
    candidates = sorted(
        (
            report
            for report in (normalize(item) for item in inventory())
            if eligible(report)
        ),
        key=lambda report: (
            (report.ended_at or cutoff).replace(tzinfo=UTC)
            if (report.ended_at or cutoff).tzinfo is None
            else report.ended_at or cutoff,
            report.run_id,
        ),
    )[:limit]
    for report_index, candidate in enumerate(candidates):
        if touched_artifacts >= limit:
            break
        candidate = normalize(candidate)
        workspace = managed_artifact_workspace(
            ctx, artifact_storage_run_id(candidate), artifact_root=artifact_root
        )
        with artifact_workspace_lock(workspace, blocking=False) as acquired:
            if not acquired:
                busy = True
                continue
            reports = [normalize(item) for item in inventory()]
            report = next(
                (item for item in reports if item.run_id == candidate.run_id), None
            )
            if report is None or not eligible(report):
                continue
            if artifact_storage_run_id(report) != artifact_storage_run_id(candidate):
                raise ValueError("Artifact workspace changed during cleanup")
            protected = protected_references(reports, workspace)
            ownership = read_artifact_ownership(
                workspace,
                cutoff,
                report_run_ids={item.run_id for item in reports},
                retention_seconds=retention_seconds,
            )
            unpublished = ownership.protected

            metadata = dict(report.metadata)
            old_details: object = metadata.get(RUN_ARTIFACT_RETENTION_DETAILS_KEY)
            details: dict[str, Any] = (
                cast(dict[str, Any], old_details)
                if isinstance(old_details, dict)
                else {}
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
            details.pop("retry_after", None)
            metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] = "running"
            metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY] = details
            working = replace(report, metadata=metadata)
            report_store.put(working)
            processed_reports += 1

            report_failed = 0
            interrupted = False
            artifacts = list(working.artifacts)
            old_deferred = details.get("deferred_artifact_ids", [])
            deferred = (
                {str(item) for item in cast(list[object], old_deferred)}
                if isinstance(old_deferred, list)
                else set[str]()
            )
            for artifact_index, artifact in enumerate(artifacts):
                if artifact.strategy != "durable" or (
                    artifact.status == "expired" and artifact.identity not in deferred
                ):
                    continue
                identity_hash = hashlib.sha256(artifact.identity.encode()).hexdigest()
                if (
                    artifact.status == "expired"
                    and artifact.identity in deferred
                    and identity_hash in unpublished
                    and identity_hash not in protected
                ):
                    # No new expiry or deletion is possible for this reference.
                    # Keep the budget for unfinished references in this report.
                    continue
                if touched_artifacts >= limit:
                    interrupted = True
                    break

                touched_artifacts += 1
                path = artifact_storage_path(workspace, artifact.identity)
                try:
                    removed = (
                        False
                        if identity_hash in protected or identity_hash in unpublished
                        else _remove_artifact_file(path)
                    )
                    if removed:
                        deleted_artifacts += 1
                    expire_artifact_reference(
                        workspace, working.run_id, artifact.identity
                    )
                except (OSError, RuntimeError, ValueError):
                    report_failed += 1
                    failed_artifacts += 1
                    continue

                if identity_hash in unpublished and identity_hash not in protected:
                    deferred.add(artifact.identity)
                else:
                    deferred.discard(artifact.identity)
                artifacts[artifact_index] = replace(artifact, status="expired")
                metadata = dict(working.metadata)
                progress = dict(metadata.get(RUN_ARTIFACT_RETENTION_DETAILS_KEY) or {})
                progress["deferred_artifact_ids"] = sorted(deferred)
                metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY] = progress
                working = replace(
                    working, artifacts=tuple(artifacts), metadata=metadata
                )
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
            elif deferred:
                # An unpublished owner's files still need a later physical
                # cleanup if that owner never reaches the report provider.
                metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] = "running"
                retries = [
                    ownership.retry_after.get(
                        hashlib.sha256(identity.encode()).hexdigest()
                    )
                    for identity in deferred
                ]
                details["retry_after"] = min(
                    retry
                    if retry is not None
                    else current + timedelta(seconds=min(60, retention_seconds))
                    for retry in retries
                ).isoformat()
            else:
                metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] = "complete"
                completed_reports += 1
            report_store.put(replace(working, metadata=metadata))

            if touched_artifacts >= limit and report_index + 1 < len(candidates):
                break

    remaining_candidates = (
        busy
        or orphan_remaining
        or any(pending(normalize(report)) for report in inventory())
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
