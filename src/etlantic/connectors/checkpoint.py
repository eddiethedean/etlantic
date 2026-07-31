"""Landing checkpoint load/save and local exclusive lease."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from etlantic.connectors.errors import ConnectorCheckpointError
from etlantic.connectors.models import (
    LANDING_CHECKPOINT_SCHEMA,
    LandingCheckpoint,
    utc_now_iso,
)
from etlantic.io_policy import (
    SafeIoPolicy,
    read_text_safe,
    resolve_under_policy,
    write_text_safe,
)


def checkpoint_path_for(root: Path, checkpoint_name: str) -> Path:
    """Resolve a checkpoint file path under an approved root."""
    name = checkpoint_name.strip().replace("\\", "/")
    if not name or name.startswith("/") or ".." in name.split("/"):
        raise ConnectorCheckpointError(
            f"Invalid checkpoint name {checkpoint_name!r}",
            code="PMCONN601",
        )
    if not name.endswith(".json"):
        name = f"{name}.json"
    return root / ".etlantic" / "checkpoints" / name


def load_landing_checkpoint(
    path: str | Path,
    *,
    policy: SafeIoPolicy,
    run_id: str = "checkpoint",
) -> LandingCheckpoint | None:
    """Load ``etlantic.landing_checkpoint/1`` under Safe I/O, or None if missing."""
    resolved, _ = resolve_under_policy(path, policy, run_id=run_id, must_exist=False)
    if not resolved.exists():
        return None
    _path, text, _events = read_text_safe(resolved, policy, run_id=run_id)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConnectorCheckpointError(
            f"Corrupt landing checkpoint at {resolved.name}: {exc}",
            code="PMCONN602",
        ) from exc
    if not isinstance(data, dict):
        raise ConnectorCheckpointError(
            "Landing checkpoint must be a JSON object",
            code="PMCONN603",
        )
    schema = str(data.get("schema") or "")
    if schema and schema != LANDING_CHECKPOINT_SCHEMA:
        raise ConnectorCheckpointError(
            f"Unsupported checkpoint schema {schema!r}",
            code="PMCONN604",
        )
    return LandingCheckpoint.from_dict(data)


def save_landing_checkpoint(
    path: str | Path,
    checkpoint: LandingCheckpoint,
    *,
    policy: SafeIoPolicy,
    run_id: str = "checkpoint",
    expected_generation: int | None = None,
) -> LandingCheckpoint:
    """Atomically save a checkpoint; fail closed on stale on-disk generation.

    ``expected_generation`` is the generation currently on disk (or ``0`` when
    creating the first checkpoint). The payload being written may already carry
    ``expected_generation + 1``.
    """
    existing = load_landing_checkpoint(path, policy=policy, run_id=run_id)
    if expected_generation is not None:
        on_disk = existing.generation if existing is not None else 0
        if on_disk != expected_generation:
            raise ConnectorCheckpointError(
                "Concurrent landing checkpoint update detected",
                code="PMCONN606",
                details={
                    "expected": expected_generation,
                    "on_disk": on_disk,
                },
            )
    payload = checkpoint.to_dict()
    if not payload.get("updated_at"):
        payload["updated_at"] = utc_now_iso()
        checkpoint = LandingCheckpoint.from_dict(payload)
    text = json.dumps(checkpoint.to_dict(), indent=2, sort_keys=True) + "\n"
    write_text_safe(path, text, policy, run_id=run_id)
    return checkpoint


def advance_landing_checkpoint(
    path: str | Path,
    *,
    policy: SafeIoPolicy,
    base: LandingCheckpoint,
    new_identity_keys: tuple[str, ...],
    publication_id: str | None,
    manifest_fingerprint: str | None,
    run_id: str = "checkpoint",
) -> LandingCheckpoint:
    """Advance ledger only after a proven committed publication."""
    committed = tuple(sorted(set(base.committed_identities) | set(new_identity_keys)))
    updated = LandingCheckpoint(
        schema=LANDING_CHECKPOINT_SCHEMA,
        pipeline_id=base.pipeline_id,
        extract_id=base.extract_id,
        binding_id=base.binding_id,
        binding_fingerprint=base.binding_fingerprint,
        generation=base.generation + 1,
        committed_identities=committed,
        last_read_manifest_fingerprint=manifest_fingerprint,
        publication_id=publication_id,
        updated_at=utc_now_iso(),
        metadata=dict(base.metadata),
    )
    return save_landing_checkpoint(
        path,
        updated,
        policy=policy,
        run_id=run_id,
        expected_generation=base.generation,
    )


def _lease_path(checkpoint_file: Path) -> Path:
    return checkpoint_file.with_suffix(checkpoint_file.suffix + ".lease")


@contextmanager
def landing_checkpoint_lease(
    checkpoint_file: str | Path,
    *,
    policy: SafeIoPolicy,
    run_id: str = "checkpoint",
    timeout_seconds: float | None = None,
) -> Iterator[Path]:
    """Exclusive local lease for concurrent landing-zone runs (single-host)."""
    resolved, _ = resolve_under_policy(
        checkpoint_file, policy, run_id=run_id, must_exist=False
    )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    lease = _lease_path(resolved)
    timeout = (
        float(timeout_seconds)
        if timeout_seconds is not None
        else float(policy.lock_timeout_seconds)
    )
    deadline = time.monotonic() + timeout
    fd: int | None = None
    while True:
        try:
            fd = os.open(str(lease), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, f"{run_id}\n".encode())
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ConnectorCheckpointError(
                    f"Timed out acquiring landing checkpoint lease for {resolved.name}",
                    code="PMCONN607",
                ) from None
            time.sleep(0.05)
    try:
        yield resolved
    finally:
        if fd is not None:
            with suppress(OSError):
                os.close(fd)
        with suppress(OSError):
            lease.unlink(missing_ok=True)


def empty_checkpoint(
    *,
    pipeline_id: str = "",
    extract_id: str = "",
    binding_id: str = "",
    binding_fingerprint: str = "",
    metadata: dict[str, Any] | None = None,
) -> LandingCheckpoint:
    """Create an empty generation-0 checkpoint."""
    return LandingCheckpoint(
        pipeline_id=pipeline_id,
        extract_id=extract_id,
        binding_id=binding_id,
        binding_fingerprint=binding_fingerprint,
        generation=0,
        committed_identities=(),
        metadata=dict(metadata or {}),
    )


__all__ = [
    "advance_landing_checkpoint",
    "checkpoint_path_for",
    "empty_checkpoint",
    "landing_checkpoint_lease",
    "load_landing_checkpoint",
    "save_landing_checkpoint",
]
