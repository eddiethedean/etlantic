"""File-backed schema history provider (no source rows)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from etlantic.io_policy import (
    SafeIoPolicy,
    read_modify_write_json_safe,
    read_text_safe,
    write_json_safe,
)
from etlantic.schema_drift import SchemaObservation
from etlantic.schema_policy import InMemorySchemaHistory
from etlantic.serialization_policy import assert_safe_load_path

_LOG = logging.getLogger(__name__)


def _observation_to_dict(observation: SchemaObservation) -> dict[str, Any]:
    return {
        "subject_id": observation.subject_id,
        "fingerprint": observation.schema.fingerprint(),
        "inspector": observation.inspector,
        "observed_at": observation.observed_at,
        "metadata": dict(observation.metadata),
        "schema": observation.schema.to_dict(),
    }


def _observation_from_dict(data: dict[str, Any]) -> SchemaObservation:
    from etlantic.schema_drift import NormalizedSchema

    return SchemaObservation(
        subject_id=str(data["subject_id"]),
        schema=NormalizedSchema.from_dict(data["schema"]),
        inspector=str(data.get("inspector") or "file"),
        observed_at=data.get("observed_at"),
        metadata=dict(data.get("metadata") or {}),
    )


_FORBIDDEN_ROW_KEYS = frozenset(
    {
        "rows",
        "sample_rows",
        "source_rows",
        "records",
        "preview",
        "data",
        "samples",
        "row_data",
        "payload",
        "payload_rows",
    }
)


def _looks_like_row_payload(metadata: dict[str, Any] | None) -> bool:
    """True when metadata keys/values look like stored source rows."""
    if not metadata:
        return False
    for key, value in metadata.items():
        key_l = str(key).lower()
        if key_l in _FORBIDDEN_ROW_KEYS:
            return True
        if key_l.endswith("_rows") or key_l in {"row_sample", "row_samples"}:
            return True
        if isinstance(value, dict) and _looks_like_row_payload(value):
            return True
        if (
            isinstance(value, list)
            and value
            and isinstance(value[0], dict)
            and (
                key_l.endswith("rows")
                or "sample" in key_l
                or key_l in {"preview", "data", "payload"}
            )
        ):
            return True
    return False


def assert_no_row_payload(observation: SchemaObservation) -> None:
    """Refuse observations that embed source-row-like payloads."""
    schema_meta = getattr(observation.schema, "metadata", None) or {}
    if _looks_like_row_payload(observation.metadata) or _looks_like_row_payload(
        dict(schema_meta)
    ):
        raise ValueError("Schema history must not store source rows; failing closed.")


@dataclass
class FileSchemaHistoryProvider:
    """Canonical-file schema history under a root directory.

    Observations are fingerprints and field metadata only — never source rows.
    Writes go through :class:`SafeIoPolicy` (0.20).
    """

    root: Path
    policy: SafeIoPolicy | None = None
    _memory: InMemorySchemaHistory = field(default_factory=InMemorySchemaHistory)

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if self.policy is None:
            self.policy = SafeIoPolicy.for_root(self.root)
        self._load()

    def _subject_path(self, subject_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in subject_id)
        return self.root / f"{safe}.json"

    def _load(self) -> None:
        assert self.policy is not None
        for path in sorted(self.root.glob("*.json")):
            if (
                path.name.endswith(".ack.json")
                or path.name.endswith(".lock")
                or path.name.endswith(".tmp")
            ):
                continue
            try:
                assert_safe_load_path(path)
                _resolved, text, _events = read_text_safe(
                    path, self.policy, run_id="schema-history-load"
                )
                data = json.loads(text)
            except Exception as exc:
                _LOG.warning(
                    "Skipping schema history file %s: %s",
                    path,
                    exc,
                )
                continue
            for item in data.get("history") or []:
                if not isinstance(item, dict):
                    continue
                try:
                    self._memory.record(_observation_from_dict(item))
                except ValueError as exc:
                    if "must not store source rows" in str(exc):
                        raise
                    _LOG.warning(
                        "Skipping invalid schema history item in %s: %s",
                        path,
                        exc,
                    )
                except Exception as exc:
                    _LOG.warning(
                        "Skipping invalid schema history item in %s: %s",
                        path,
                        exc,
                    )

    def record(self, observation: SchemaObservation) -> None:
        assert_no_row_payload(observation)
        fp = observation.schema.fingerprint()
        if any(
            o.schema.fingerprint() == fp
            for o in self._memory.history(observation.subject_id)
        ):
            return
        assert self.policy is not None
        path = self._subject_path(observation.subject_id)
        obs_dict = _observation_to_dict(observation)

        def _merge(data: dict[str, Any]) -> dict[str, Any]:
            history = list(data.get("history") or [])
            if any(
                isinstance(item, dict) and item.get("fingerprint") == fp
                for item in history
            ):
                return data
            history.append(obs_dict)
            return {
                "subject_id": observation.subject_id,
                "latest": obs_dict,
                "history": history,
            }

        read_modify_write_json_safe(path, self.policy, _merge, run_id="schema-history")
        self._memory.record(observation)

    def latest(self, subject_id: str) -> SchemaObservation | None:
        return self._memory.latest(subject_id)

    def history(self, subject_id: str) -> list[SchemaObservation]:
        return self._memory.history(subject_id)

    def acknowledge(
        self, subject_id: str, *, note: str | None = None
    ) -> dict[str, Any]:
        """Record an acknowledgment without mutating the contract."""
        latest = self.latest(subject_id)
        ack = {
            "subject_id": subject_id,
            "acknowledged_fingerprint": (
                latest.schema.fingerprint() if latest is not None else None
            ),
            "note": note,
            "action": "acknowledge",
        }
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in subject_id)
        ack_path = self.root / f"{safe}.ack.json"
        assert self.policy is not None
        write_json_safe(ack_path, ack, self.policy, run_id="schema-history-ack")
        return ack
