"""Workspace resource records, protocol, and safe-root helpers (CP2 / 040-W).

Stored records carry ``root_ref`` tokens only — never absolute filesystem
secrets. Runtime resolution rejects traversal and symlink escapes.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.redaction import redact_control_plane_payload

WORKSPACE_RESOURCE_RECORD_SCHEMA = "etlantic.control_plane.workspace_resource_record/1"


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def is_absolute_root_ref(root_ref: str) -> bool:
    """Return True when ``root_ref`` looks like an absolute or drive path."""
    text = str(root_ref).strip()
    if not text:
        return False
    if text.startswith(("/", "\\")):
        return True
    # Windows drive or UNC
    if len(text) >= 2 and text[1] == ":":
        return True
    if text.startswith("\\\\") or text.startswith("//"):
        return True
    return Path(text).is_absolute()


def reject_absolute_root_ref(root_ref: str) -> None:
    """Raise when a stored root_ref is absolute (records must be refs only)."""
    if is_absolute_root_ref(root_ref):
        raise ControlPlaneError.conflict(
            "Workspace resource safe_root_refs must be root_ref tokens, "
            "not absolute paths",
            extensions={"root_ref": root_ref},
        )
    parts = Path(root_ref).parts
    if ".." in parts:
        raise ControlPlaneError.conflict(
            "Workspace resource safe_root_refs must not contain '..' traversal",
            extensions={"root_ref": root_ref},
        )


def reject_symlink_or_traversal(
    candidate: Path,
    *,
    approved_root: Path,
) -> Path:
    """Resolve ``candidate`` under ``approved_root``; reject symlink/traversal.

    Returns the resolved path when it stays inside the approved root and is
    not a symlink (or symlink escape). Raises :class:`ControlPlaneError` with
    conflict (409) semantics on rejection.
    """
    root = approved_root.expanduser().resolve()

    raw = Path(candidate)
    if ".." in raw.parts:
        raise ControlPlaneError.conflict(
            "Path traversal rejected when resolving workspace root",
            extensions={"path": str(raw), "approved_root": str(root)},
        )

    raw_absolute = raw if raw.is_absolute() else root / raw
    if not _is_relative_to(raw_absolute, root):
        raise ControlPlaneError.conflict(
            "Path traversal rejected when resolving workspace root",
            extensions={"path": str(raw), "approved_root": str(root)},
        )

    # Inspect unresolved components before following links. Walking only the
    # resolved parents misses intermediate symlinks that land back in root.
    relative = raw_absolute.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ControlPlaneError.conflict(
                "Symlink rejected when resolving workspace root",
                extensions={"path": str(current)},
            )

    try:
        resolved = raw.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ControlPlaneError.conflict(
            "Failed to resolve workspace root path",
            extensions={"path": str(raw)},
        ) from exc

    if not _is_relative_to(resolved, root):
        raise ControlPlaneError.conflict(
            "Path traversal rejected when resolving workspace root",
            extensions={"path": str(raw), "approved_root": str(root)},
        )

    return resolved


def resolve_safe_root(
    root_ref: str,
    *,
    base: Path,
) -> Path:
    """Map a stored ``root_ref`` onto ``base`` with traversal/symlink rejection."""
    reject_absolute_root_ref(root_ref)
    base_resolved = Path(base).expanduser().resolve()
    candidate = base_resolved / root_ref
    return reject_symlink_or_traversal(candidate, approved_root=base_resolved)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_workspace_resource_record(record: WorkspaceResourceRecord) -> None:
    """Validate stored resource refs (no absolute roots; metadata redacted-safe)."""
    for root_ref in record.safe_root_refs:
        reject_absolute_root_ref(root_ref)
    for ref_name, value in (
        ("artifact_namespace", record.artifact_namespace),
        ("checkpoint_store_ref", record.checkpoint_store_ref),
        ("preview_namespace", record.preview_namespace),
    ):
        if value is not None and is_absolute_root_ref(value):
            raise ControlPlaneError.conflict(
                f"Workspace resource {ref_name} must not be an absolute path",
                extensions={ref_name: value},
            )


@dataclass(frozen=True, slots=True)
class WorkspaceResourceRecord:
    """Tenant/workspace resource bindings (refs and namespaces only)."""

    tenant_id: str
    workspace_id: str
    safe_root_refs: tuple[str, ...] = ()
    artifact_namespace: str | None = None
    checkpoint_store_ref: str | None = None
    preview_namespace: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": WORKSPACE_RESOURCE_RECORD_SCHEMA,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "safe_root_refs": list(self.safe_root_refs),
            "artifact_namespace": self.artifact_namespace,
            "checkpoint_store_ref": self.checkpoint_store_ref,
            "preview_namespace": self.preview_namespace,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkspaceResourceRecord:
        roots = data.get("safe_root_refs") or ()
        return cls(
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            safe_root_refs=tuple(str(r) for r in roots),
            artifact_namespace=(
                str(data["artifact_namespace"])
                if data.get("artifact_namespace") is not None
                else None
            ),
            checkpoint_store_ref=(
                str(data["checkpoint_store_ref"])
                if data.get("checkpoint_store_ref") is not None
                else None
            ),
            preview_namespace=(
                str(data["preview_namespace"])
                if data.get("preview_namespace") is not None
                else None
            ),
            created_at=(
                str(data["created_at"]) if data.get("created_at") is not None else None
            ),
            updated_at=(
                str(data["updated_at"]) if data.get("updated_at") is not None else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@runtime_checkable
class WorkspaceResourceStore(Protocol):
    """Scoped workspace resource store."""

    def get(self, ctx: ControlPlaneContext) -> WorkspaceResourceRecord:
        """Fetch resources for ``ctx`` tenant/workspace (404 / KeyError semantics)."""
        ...

    def put(
        self,
        ctx: ControlPlaneContext,
        record: WorkspaceResourceRecord,
    ) -> WorkspaceResourceRecord:
        """Create or replace resources inside ``ctx`` scope."""
        ...

    def delete(self, ctx: ControlPlaneContext) -> None:
        """Delete resources inside ``ctx`` scope (404 if missing)."""
        ...


@dataclass
class MemoryWorkspaceResourceStore:
    """In-memory workspace resources keyed by (tenant_id, workspace_id)."""

    _records: dict[tuple[str, str], WorkspaceResourceRecord] = field(
        default_factory=dict
    )
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def get(self, ctx: ControlPlaneContext) -> WorkspaceResourceRecord:
        key = ctx.scope_key
        with self._lock:
            record = self._records.get(key)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Workspace resources not found",
                    extensions={
                        "tenant_id": ctx.tenant.tenant_id,
                        "workspace_id": ctx.workspace.workspace_id,
                    },
                )
            return deepcopy(record)

    def put(
        self,
        ctx: ControlPlaneContext,
        record: WorkspaceResourceRecord,
    ) -> WorkspaceResourceRecord:
        if (
            record.tenant_id != ctx.tenant.tenant_id
            or record.workspace_id != ctx.workspace.workspace_id
        ):
            raise ControlPlaneError.not_found(
                "Workspace resources not found",
                extensions={
                    "tenant_id": record.tenant_id,
                    "workspace_id": record.workspace_id,
                },
            )
        validate_workspace_resource_record(record)
        key = ctx.scope_key
        with self._lock:
            existing = self._records.get(key)
            now = _utcnow_iso()
            meta = redact_control_plane_payload(dict(record.metadata))
            if not isinstance(meta, dict):
                meta = {}
            stored = replace(
                record,
                safe_root_refs=tuple(record.safe_root_refs),
                created_at=existing.created_at
                if existing
                else (record.created_at or now),
                updated_at=now,
                metadata=meta,
            )
            self._records[key] = stored
            return deepcopy(stored)

    def delete(self, ctx: ControlPlaneContext) -> None:
        key = ctx.scope_key
        with self._lock:
            if key not in self._records:
                raise ControlPlaneError.not_found(
                    "Workspace resources not found",
                    extensions={
                        "tenant_id": ctx.tenant.tenant_id,
                        "workspace_id": ctx.workspace.workspace_id,
                    },
                )
            del self._records[key]

    def list_keys(self) -> Sequence[tuple[str, str]]:
        """Internal: list stored scope keys (tests / admin)."""
        with self._lock:
            return sorted(self._records.keys())


__all__ = [
    "WORKSPACE_RESOURCE_RECORD_SCHEMA",
    "MemoryWorkspaceResourceStore",
    "WorkspaceResourceRecord",
    "WorkspaceResourceStore",
    "is_absolute_root_ref",
    "reject_absolute_root_ref",
    "reject_symlink_or_traversal",
    "resolve_safe_root",
    "validate_workspace_resource_record",
]
