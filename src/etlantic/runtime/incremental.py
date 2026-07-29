"""Domain-neutral incremental strategies and atomic state stores (0.31)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from etlantic.reports.model import StateTransitionResult
from etlantic.runtime.request import RunIntent


class IncrementalKind(StrEnum):
    """Declared incremental strategy kind."""

    WATERMARK = "watermark"
    CURSOR = "cursor"
    CHANGE_FEED = "change_feed"
    SNAPSHOT_DIFF = "snapshot_diff"


@dataclass(frozen=True, slots=True)
class IncrementalStrategy:
    """Portable incremental / watermark strategy declaration."""

    kind: IncrementalKind
    subject_id: str
    column: str | None = None
    ordering: str = "ascending"
    overlap: str | None = None
    keys: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def watermark(
        cls,
        *,
        subject_id: str,
        field: str,
        ordering: str = "ascending",
        overlap: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> IncrementalStrategy:
        return cls(
            kind=IncrementalKind.WATERMARK,
            subject_id=subject_id,
            column=field,
            ordering=ordering,
            overlap=overlap,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def cursor(
        cls,
        *,
        subject_id: str,
        key: str,
        metadata: dict[str, Any] | None = None,
    ) -> IncrementalStrategy:
        return cls(
            kind=IncrementalKind.CURSOR,
            subject_id=subject_id,
            column=key,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def change_feed(
        cls,
        *,
        subject_id: str,
        version_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> IncrementalStrategy:
        return cls(
            kind=IncrementalKind.CHANGE_FEED,
            subject_id=subject_id,
            column=version_key,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def snapshot_diff(
        cls,
        *,
        subject_id: str,
        keys: tuple[str, ...] | list[str],
        metadata: dict[str, Any] | None = None,
    ) -> IncrementalStrategy:
        return cls(
            kind=IncrementalKind.SNAPSHOT_DIFF,
            subject_id=subject_id,
            keys=tuple(str(k) for k in keys),
            metadata=dict(metadata or {}),
        )

    def identity(self) -> str:
        return f"incremental:{self.kind.value}:{self.subject_id}:{self.column or ''}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "subject_id": self.subject_id,
            "field": self.column,
            "column": self.column,
            "ordering": self.ordering,
            "overlap": self.overlap,
            "keys": list(self.keys),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IncrementalStrategy:
        return cls(
            kind=IncrementalKind(str(data.get("kind") or "watermark")),
            subject_id=str(data.get("subject_id") or ""),
            column=data.get("column") or data.get("field"),
            ordering=str(data.get("ordering") or "ascending"),
            overlap=data.get("overlap"),
            keys=tuple(str(k) for k in (data.get("keys") or ())),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class StateCursor:
    """Committed cursor / watermark value for a subject."""

    subject_id: str
    value: str | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": dict(self.metadata),
        }


@runtime_checkable
class StateStore(Protocol):
    """Atomic state provider for incremental cursors / watermarks."""

    def get(self, subject_id: str) -> StateCursor | None:
        """Return the committed cursor for ``subject_id``, if any."""

    def propose(self, subject_id: str, value: str | None) -> StateCursor:
        """Stage a candidate value without committing."""

    def commit(
        self,
        subject_id: str,
        value: str | None,
        *,
        reason: str | None = None,
    ) -> StateTransitionResult:
        """Atomically commit a new cursor value."""

    def rollback(self, subject_id: str) -> None:
        """Discard any staged candidate for ``subject_id``."""


def may_advance_state(*, intent: RunIntent, no_write: bool, succeeded: bool) -> bool:
    """Return whether a run is allowed to commit incremental state."""
    if not succeeded:
        return False
    return not (no_write or intent is RunIntent.VALIDATE)


class MemoryStateStore:
    """In-memory state store for tests and ephemeral local runs."""

    def __init__(self) -> None:
        self._committed: dict[str, StateCursor] = {}
        self._proposed: dict[str, StateCursor] = {}

    def get(self, subject_id: str) -> StateCursor | None:
        return self._committed.get(subject_id)

    def propose(self, subject_id: str, value: str | None) -> StateCursor:
        cursor = StateCursor(
            subject_id=subject_id,
            value=value,
            updated_at=datetime.now(UTC),
        )
        self._proposed[subject_id] = cursor
        return cursor

    def commit(
        self,
        subject_id: str,
        value: str | None,
        *,
        reason: str | None = None,
    ) -> StateTransitionResult:
        previous = self._committed.get(subject_id)
        now = datetime.now(UTC)
        self._committed[subject_id] = StateCursor(
            subject_id=subject_id,
            value=value,
            updated_at=now,
        )
        self._proposed.pop(subject_id, None)
        return StateTransitionResult(
            subject=subject_id,
            from_status=previous.value
            if previous and previous.value is not None
            else "",
            to_status=value if value is not None else "",
            at=now,
            reason=reason or "commit",
        )

    def rollback(self, subject_id: str) -> None:
        self._proposed.pop(subject_id, None)


class FileStateStore:
    """JSON file-backed state store for durable local workspaces."""

    def __init__(self, path: str | Path) -> None:
        from etlantic.io_policy import SafeIoPolicy, read_modify_write_json_safe

        self.path = Path(path)
        self._proposed: dict[str, StateCursor] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._policy = SafeIoPolicy.for_root(self.path.parent)
        self._rmw = read_modify_write_json_safe
        if not self.path.exists():
            self._rmw(
                self.path,
                self._policy,
                lambda _current: {},
                run_id="state-store-init",
            )

    def _load(self) -> dict[str, Any]:
        from etlantic.io_policy import read_text_safe

        try:
            _resolved, text, _events = read_text_safe(
                self.path, self._policy, run_id="state-store-load"
            )
            data = json.loads(text)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(
                f"Unreadable FileStateStore at {self.path}; failing closed."
            ) from exc
        if not isinstance(data, dict):
            raise RuntimeError(
                f"Invalid FileStateStore payload at {self.path}; failing closed."
            )
        return data

    def _save(self, data: dict[str, Any]) -> None:
        def _replace(_current: dict[str, Any]) -> dict[str, Any]:
            return dict(data)

        self._rmw(self.path, self._policy, _replace, run_id="state-store-save")

    def get(self, subject_id: str) -> StateCursor | None:
        raw = self._load().get(subject_id)
        if not isinstance(raw, dict):
            return None
        updated = raw.get("updated_at")
        at = None
        if isinstance(updated, str) and updated:
            try:
                at = datetime.fromisoformat(updated)
            except ValueError:
                at = None
        return StateCursor(
            subject_id=subject_id,
            value=raw.get("value"),
            updated_at=at,
            metadata=dict(raw.get("metadata") or {}),
        )

    def propose(self, subject_id: str, value: str | None) -> StateCursor:
        cursor = StateCursor(
            subject_id=subject_id,
            value=value,
            updated_at=datetime.now(UTC),
        )
        self._proposed[subject_id] = cursor
        return cursor

    def commit(
        self,
        subject_id: str,
        value: str | None,
        *,
        reason: str | None = None,
    ) -> StateTransitionResult:
        now = datetime.now(UTC)
        previous_value: str | None = None

        def _merge(current: dict[str, Any]) -> dict[str, Any]:
            nonlocal previous_value
            data = dict(current)
            raw_previous = data.get(subject_id)
            if isinstance(raw_previous, dict):
                previous_value = raw_previous.get("value")
            data[subject_id] = {
                "value": value,
                "updated_at": now.isoformat(),
                "metadata": {},
            }
            return data

        self._rmw(self.path, self._policy, _merge, run_id="state-store-commit")
        self._proposed.pop(subject_id, None)
        return StateTransitionResult(
            subject=subject_id,
            from_status=previous_value if previous_value is not None else "",
            to_status=value if value is not None else "",
            at=now,
            reason=reason or "commit",
        )

    def rollback(self, subject_id: str) -> None:
        self._proposed.pop(subject_id, None)
