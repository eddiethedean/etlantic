"""File-backed schema history provider (no source rows)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

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

_SAFE_SUBJECT_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


def _observation_to_dict(observation: SchemaObservation) -> dict[str, Any]:
    return {
        "subject_id": observation.subject_id,
        "fingerprint": observation.schema.fingerprint(),
        "inspector": observation.inspector,
        "observed_at": observation.observed_at,
        "metadata": dict(observation.metadata),
        "schema": observation.schema.to_dict(),
    }


def _observation_from_dict(
    data: dict[str, Any], *, fail_closed: bool = True
) -> SchemaObservation:
    from etlantic.schema_drift import NormalizedSchema

    schema = NormalizedSchema.from_dict(data["schema"])
    stored_fp = data.get("fingerprint")
    live_fp = schema.fingerprint()
    if stored_fp is not None and str(stored_fp) != live_fp:
        message = (
            f"Schema history fingerprint mismatch for subject "
            f"{data.get('subject_id')!r}: stored={stored_fp!r} live={live_fp!r}"
        )
        if fail_closed:
            raise ValueError(message)
        _LOG.warning("%s; using recomputed fingerprint", message)
    observation = SchemaObservation(
        subject_id=str(data["subject_id"]),
        schema=schema,
        inspector=str(data.get("inspector") or "file"),
        observed_at=data.get("observed_at"),
        metadata=dict(data.get("metadata") or {}),
    )
    assert_no_row_payload(observation)
    return observation


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
        "examples",
        "source_data",
        "row",
        "table",
        "records_sample",
        "row_sample",
        "row_samples",
        "items",
        "values",
    }
)


_JSON_ROW_STRING_MIN = 32
_JSON_ARRAY_OR_OBJECT_RE = re.compile(r"^\s*[\[{]")


def _is_list_of_mappings(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, dict) for item in value)
    )


def _is_tabular_list(value: Any) -> bool:
    """True for non-empty lists that look like row/cell matrices."""
    if not isinstance(value, list) or not value:
        return False
    if _is_list_of_mappings(value):
        return True
    # List-of-lists / list-of-tuples (matrix / cells) — common row bypass.
    return all(isinstance(item, (list, tuple)) for item in value)


def _looks_like_json_row_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if len(text) < _JSON_ROW_STRING_MIN or not _JSON_ARRAY_OR_OBJECT_RE.match(text):
        return False
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    if isinstance(parsed, list) and parsed:
        return True
    return isinstance(parsed, dict) and _looks_like_row_payload(parsed)


def _looks_like_row_payload(metadata: dict[str, Any] | None) -> bool:
    """True when metadata keys/values look like stored source rows."""
    if not metadata:
        return False
    for key, value in metadata.items():
        key_l = str(key).lower()
        if key_l in _FORBIDDEN_ROW_KEYS:
            return True
        if (
            key_l.endswith("_rows")
            or "sample" in key_l
            or key_l
            in {
                "cells",
                "table_data",
                "export",
            }
        ):
            return True
        if _is_tabular_list(value) or _is_list_of_mappings(value):
            return True
        if _looks_like_json_row_string(value):
            return True
        if isinstance(value, dict) and _looks_like_row_payload(value):
            return True
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and _looks_like_row_payload(item):
                    return True
                if isinstance(item, (list, tuple)) and item:
                    return True
    return False


def assert_no_row_payload(observation: SchemaObservation) -> None:
    """Refuse observations that embed source-row-like payloads."""
    schema_meta = getattr(observation.schema, "metadata", None) or {}
    if _looks_like_row_payload(observation.metadata) or _looks_like_row_payload(
        dict(schema_meta)
    ):
        raise ValueError("Schema history must not store source rows; failing closed.")
    for field_obj in getattr(observation.schema, "fields", ()) or ():
        field_meta = getattr(field_obj, "metadata", None) or {}
        if _looks_like_row_payload(dict(field_meta)):
            raise ValueError(
                "Schema history must not store source rows; failing closed."
            )


def subject_history_filename(subject_id: str) -> str:
    """Return a collision-resistant filename for ``subject_id``.

    Safe alphanumeric subjects keep a readable name; all others use a stable
    hash so ``foo:bar`` and ``foo_bar`` never share a file.
    """
    text = str(subject_id)
    if _SAFE_SUBJECT_SEGMENT.fullmatch(text):
        return f"{text}.json"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
    # Keep a short percent-encoded hint for operators (not used for identity).
    hint = quote(text, safe="")[:40]
    return f"s_{digest}_{hint}.json"


@dataclass
class FileSchemaHistoryProvider:
    """Canonical-file schema history under a root directory.

    Observations are fingerprints and field metadata only — never source rows.
    Writes go through :class:`SafeIoPolicy` (0.20).
    """

    root: Path
    policy: SafeIoPolicy | None = None
    fail_closed: bool = True
    _memory: InMemorySchemaHistory = field(default_factory=InMemorySchemaHistory)

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if self.policy is None:
            self.policy = SafeIoPolicy.for_root(self.root)
        self._load()

    def _subject_path(self, subject_id: str) -> Path:
        return self.root / subject_history_filename(subject_id)

    def _ack_path(self, subject_id: str) -> Path:
        base = subject_history_filename(subject_id)
        if base.endswith(".json"):
            return self.root / f"{base[:-5]}.ack.json"
        return self.root / f"{base}.ack.json"

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
                if self.fail_closed:
                    raise RuntimeError(
                        f"Unreadable schema history file {path}; failing closed."
                    ) from exc
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
                    self._memory.record(
                        _observation_from_dict(item, fail_closed=self.fail_closed)
                    )
                except ValueError as exc:
                    if "must not store source rows" in str(exc):
                        raise
                    if self.fail_closed:
                        raise RuntimeError(
                            f"Invalid schema history item in {path}; failing closed."
                        ) from exc
                    _LOG.warning(
                        "Skipping invalid schema history item in %s: %s",
                        path,
                        exc,
                    )
                except Exception as exc:
                    if self.fail_closed:
                        raise RuntimeError(
                            f"Invalid schema history item in {path}; failing closed."
                        ) from exc
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
        ack_path = self._ack_path(subject_id)
        assert self.policy is not None
        write_json_safe(ack_path, ack, self.policy, run_id="schema-history-ack")
        return ack
