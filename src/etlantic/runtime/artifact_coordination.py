"""Process-safe coordination and reference expiry for managed artifact files."""

from __future__ import annotations

import errno
import hashlib
import os
from collections.abc import Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from etlantic.io_policy import (
    SafeIoPolicy,
    read_text_safe,
    resolve_under_policy,
    write_text_safe,
)
from etlantic.reports.model import ArtifactResult, PipelineRunReport
from etlantic.reports.retention import (
    RUN_ARTIFACT_RETENTION_DETAILS_KEY,
    RUN_ARTIFACT_RETENTION_STATE_KEY,
)


def _open_lock(workspace: Path) -> int:
    root = workspace.parents[3].resolve()
    root.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directory = os.open(root, flags)
        try:
            for part in workspace.relative_to(workspace.parents[3]).parts:
                with suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=directory)
                child = os.open(part, flags, dir_fd=directory)
                os.close(directory)
                directory = child
            return os.open(
                ".artifact.lock",
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
        finally:
            os.close(directory)
    for directory in (*reversed(workspace.parents[:3]), workspace):
        if directory.is_symlink():
            raise OSError("Artifact workspace contains a symbolic link")
        directory.mkdir(exist_ok=True)
    path = workspace / ".artifact.lock"
    if path.is_symlink():
        raise OSError("Artifact lock is a symbolic link")
    return os.open(path, os.O_RDWR | os.O_CREAT, 0o600)


@contextmanager
def artifact_workspace_lock(
    workspace: Path, *, blocking: bool = True
) -> Generator[bool]:
    """Serialize workspace execution/publication with cleanup across processes.

    Cleanup uses a nonblocking acquisition so a running child never stalls
    worker polling. OS ownership is released even if an execution process dies;
    the persistent lock file must never be unlinked or replaced.
    """
    descriptor = _open_lock(workspace)
    acquired = False
    try:
        if os.name == "posix":
            import fcntl

            try:
                fcntl.flock(
                    descriptor, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
                )
                acquired = True
            except BlockingIOError:
                pass
        else:
            import msvcrt

            # Windows locks a byte range, including a byte beyond EOF.
            try:
                msvcrt.locking(
                    descriptor, msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1
                )
                acquired = True
            except OSError as exc:
                if blocking or exc.errno not in (
                    errno.EACCES,
                    errno.EAGAIN,
                    errno.EDEADLK,
                ):
                    raise
        yield acquired
    finally:
        if acquired:
            if os.name == "posix":
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
            else:
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        os.close(descriptor)


def _expiry_path(workspace: Path, run_id: str, identity: str) -> Path:
    key = hashlib.sha256((run_id + "\0" + identity).encode()).hexdigest()
    return workspace / ".expired-references" / f"{key}.json"


def expire_artifact_reference(workspace: Path, run_id: str, identity: str) -> None:
    """Persist a tombstone before publishing reference expiry to report stores."""
    _write_expiry(workspace, _expiry_path(workspace, run_id, identity), run_id)


def _write_expiry(workspace: Path, path: Path, run_id: str) -> None:
    # Writers already hold the process-owned workspace lock. SafeIo's
    # exclusive-create locks survive crashes and would prevent later recovery.
    write_text_safe(
        path,
        '"expired"',
        replace(SafeIoPolicy.for_root(workspace.parents[3]), enable_locking=False),
        run_id=run_id,
    )


def apply_artifact_expiry(
    workspace: Path, report: PipelineRunReport
) -> PipelineRunReport:
    """Keep reference expiry authoritative over stale result-publication copies."""
    artifacts: list[ArtifactResult] = []
    changed = False
    expired: set[str] = set()
    policy = SafeIoPolicy.for_root(workspace.parents[3])
    for artifact in report.artifacts:
        path = _expiry_path(workspace, report.run_id, artifact.identity)
        if artifact.strategy == "durable" and (path.exists() or path.is_symlink()):
            _, value, _ = read_text_safe(path, policy, run_id=report.run_id)
            if value != '"expired"':
                raise ValueError("Artifact reference expiry record is invalid")
            if artifact.status != "expired":
                artifact = replace(artifact, status="expired")
                changed = True
                expired.add(artifact.identity)
        artifacts.append(artifact)
    if not changed:
        return report
    metadata = dict(report.metadata)
    if metadata.get(RUN_ARTIFACT_RETENTION_STATE_KEY) != "complete":
        # Tombstones prove reference expiry, not physical deletion. A stale
        # snapshot must leave these files eligible for a guarded cleanup pass.
        details = dict(metadata.get(RUN_ARTIFACT_RETENTION_DETAILS_KEY) or {})
        deferred = details.get("deferred_artifact_ids", [])
        if not isinstance(deferred, list):
            raise ValueError("Deferred artifact cleanup record is invalid")
        details["deferred_artifact_ids"] = sorted(
            {str(item) for item in cast(list[object], deferred)} | expired
        )
        metadata[RUN_ARTIFACT_RETENTION_DETAILS_KEY] = details
        metadata.setdefault(RUN_ARTIFACT_RETENTION_STATE_KEY, "pending")
    return replace(report, artifacts=tuple(artifacts), metadata=metadata)


def record_artifact_ownership(workspace: Path, report: PipelineRunReport) -> None:
    """Keep unexpired ownership visible even if report persistence falls back."""
    import json

    from etlantic.reports.retention import TERMINAL_RUN_STATUSES

    owner = hashlib.sha256(report.run_id.encode()).hexdigest()
    payload = {
        "ended_at": report.ended_at.isoformat()
        if report.ended_at is not None
        else None,
        "terminal": report.status.value in TERMINAL_RUN_STATUSES,
        "references": [
            {
                "identity": hashlib.sha256(artifact.identity.encode()).hexdigest(),
                "expiry": _expiry_path(
                    workspace, report.run_id, artifact.identity
                ).stem,
            }
            for artifact in report.artifacts
            if artifact.strategy == "durable" and artifact.status != "expired"
        ],
    }
    write_text_safe(
        workspace / ".artifact-owners" / f"{owner}.json",
        json.dumps(payload, sort_keys=True),
        replace(SafeIoPolicy.for_root(workspace.parents[3]), enable_locking=False),
        run_id=report.run_id,
    )


@dataclass(frozen=True)
class ExpiredArtifactOwnership:
    """One unpublished reference awaiting bounded expiry and physical cleanup."""

    identity: str
    expiry: str
    owner: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class ArtifactOwnershipInventory:
    """Protection and pending cleanup from scoped filesystem ownership records."""

    protected: set[str]
    expired: tuple[ExpiredArtifactOwnership, ...]
    retry_after: dict[str, datetime | None]


def discover_artifact_workspaces(scope: Path) -> list[Path]:
    """Discover managed workspace directories without relying on report rows."""
    if not scope.exists():
        return []
    resolve_under_policy(
        scope, SafeIoPolicy.for_root(scope.parents[2]), run_id="artifact-retention"
    )
    # Enumeration does not grant access: each workspace is subsequently opened
    # through the no-follow OS guard before ownership or artifact IO.
    return sorted(
        path
        for path in scope.iterdir()
        if len(path.name) == 24
        and all(ch in "0123456789abcdef" for ch in path.name)
        and path.is_dir()
        and not path.is_symlink()
        and (path / ".artifact-owners").exists()
    )


def _is_hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def read_artifact_ownership(
    workspace: Path,
    cutoff: datetime,
    *,
    report_run_ids: set[str],
    retention_seconds: int = 0,
) -> ArtifactOwnershipInventory:
    """Read unpublished protection and cleanup work while holding the guard."""
    import json

    known = {hashlib.sha256(run_id.encode()).hexdigest() for run_id in report_run_ids}
    protected: set[str] = set()
    expired_references: list[ExpiredArtifactOwnership] = []
    retry_after: dict[str, datetime | None] = {}
    policy = SafeIoPolicy.for_root(workspace.parents[3])
    for path in (workspace / ".artifact-owners").glob("*.json"):
        if path.stem in known:
            continue
        _, text, _ = read_text_safe(path, policy, run_id="artifact-retention")
        payload: object = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("Artifact ownership record is invalid")
        data = cast(dict[str, Any], payload)
        terminal = data.get("terminal")
        ended = data.get("ended_at")
        if type(terminal) is not bool or (
            ended is not None and not isinstance(ended, str)
        ):
            raise ValueError("Artifact ownership record is invalid")
        expired = False
        expires_at: datetime | None = None
        if terminal and isinstance(ended, str):
            ended_at = datetime.fromisoformat(ended)
            ended_at = (
                ended_at.replace(tzinfo=UTC) if ended_at.tzinfo is None else ended_at
            )
            expired = ended_at <= cutoff
            expires_at = ended_at + timedelta(seconds=retention_seconds)
        cleaned = data.get("cleaned_artifact_ids", [])
        if not isinstance(cleaned, list) or not all(
            _is_hash(item) for item in cast(list[object], cleaned)
        ):
            raise ValueError("Artifact ownership cleanup record is invalid")
        references = data.get("references")
        if not isinstance(references, list):
            raise ValueError("Artifact ownership references are invalid")
        for value in cast(list[object], references):
            if not isinstance(value, dict):
                raise ValueError("Artifact ownership reference is invalid")
            reference = cast(dict[str, object], value)
            identity, expiry = reference.get("identity"), reference.get("expiry")
            if not all(_is_hash(item) for item in (identity, expiry)):
                raise ValueError("Artifact ownership reference is invalid")
            identity, expiry = cast(str, identity), cast(str, expiry)
            marker = workspace / ".expired-references" / f"{expiry}.json"
            marked = marker.exists() or marker.is_symlink()
            if marked:
                _, status, _ = read_text_safe(
                    marker, policy, run_id="artifact-retention"
                )
                if status != '"expired"':
                    raise ValueError("Artifact reference expiry record is invalid")
            if expired:
                if identity not in cleaned:
                    expired_references.append(
                        ExpiredArtifactOwnership(identity, expiry, path, data)
                    )
                continue
            if marked:
                continue
            protected.add(identity)
            if identity not in retry_after:
                retry_after[identity] = expires_at
            else:
                previous = retry_after[identity]
                retry_after[identity] = (
                    max(previous, expires_at)
                    if previous is not None and expires_at is not None
                    else None
                )
    return ArtifactOwnershipInventory(protected, tuple(expired_references), retry_after)


def expire_unpublished_artifact(
    workspace: Path, reference: ExpiredArtifactOwnership
) -> None:
    """Make one fallback reference unavailable before physical cleanup."""
    _write_expiry(
        workspace,
        workspace / ".expired-references" / f"{reference.expiry}.json",
        "artifact-retention",
    )


def complete_unpublished_artifact(
    workspace: Path, reference: ExpiredArtifactOwnership
) -> None:
    """Persist successful cleanup or transfer to another retained owner."""
    import json

    cleaned = reference.payload.setdefault("cleaned_artifact_ids", [])
    if reference.identity not in cleaned:
        cleaned.append(reference.identity)
    write_text_safe(
        reference.owner,
        json.dumps(reference.payload, sort_keys=True),
        replace(SafeIoPolicy.for_root(workspace.parents[3]), enable_locking=False),
        run_id="artifact-retention",
    )


def retained_artifact_ownership(
    workspace: Path, cutoff: datetime, *, report_run_ids: set[str]
) -> set[str]:
    """Read protection and expire unpublished references under the guard."""
    inventory = read_artifact_ownership(
        workspace, cutoff, report_run_ids=report_run_ids
    )
    for reference in inventory.expired:
        expire_unpublished_artifact(workspace, reference)
    return inventory.protected
