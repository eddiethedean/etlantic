"""File-backed schema history provider (no source rows)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from etlantic.schema_drift import SchemaObservation
from etlantic.schema_policy import InMemorySchemaHistory


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


_FORBIDDEN_ROW_KEYS = frozenset({"rows", "sample_rows", "source_rows", "records"})


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
        if (
            isinstance(value, list)
            and value
            and isinstance(value[0], dict)
            and (key_l.endswith("rows") or "sample" in key_l)
        ):
            return True
    return False


@dataclass
class FileSchemaHistoryProvider:
    """Canonical-file schema history under a root directory.

    Observations are fingerprints and field metadata only — never source rows.
    """

    root: Path
    _memory: InMemorySchemaHistory = field(default_factory=InMemorySchemaHistory)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._load()

    def _subject_path(self, subject_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in subject_id)
        return self.root / f"{safe}.json"

    def _load(self) -> None:
        for path in sorted(self.root.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data.get("history") or []:
                if isinstance(item, dict):
                    obs = _observation_from_dict(item)
                    self._memory.record(obs)

    def record(self, observation: SchemaObservation) -> None:
        # Refuse payloads that look like row samples (key-based, not substrings).
        if _looks_like_row_payload(observation.metadata):
            raise ValueError(
                "Schema history must not store source rows; failing closed."
            )
        self._memory.record(observation)
        path = self._subject_path(observation.subject_id)
        history = [
            _observation_to_dict(o)
            for o in self._memory.history(observation.subject_id)
        ]
        path.write_text(
            json.dumps(
                {
                    "subject_id": observation.subject_id,
                    "latest": _observation_to_dict(observation),
                    "history": history,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

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
        ack_path.write_text(
            json.dumps(ack, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return ack
