"""Reliability ops provider protocols (0.9)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from etlantic.io_policy import SafeIoPolicy, read_text_safe, write_json_safe


@dataclass(frozen=True, slots=True)
class QualityObservation:
    subject_id: str
    metric: str
    value: float
    observed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "metric": self.metric,
            "value": self.value,
            "observed_at": self.observed_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class StatisticalObservation:
    subject_id: str
    statistic: str
    value: float
    baseline: float | None = None
    drift_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "statistic": self.statistic,
            "value": self.value,
            "baseline": self.baseline,
            "drift_score": self.drift_score,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ReconciliationEvidence:
    subject_id: str
    left_count: int | None = None
    right_count: int | None = None
    matched: int | None = None
    mismatched: int | None = None
    status: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "left_count": self.left_count,
            "right_count": self.right_count,
            "matched": self.matched,
            "mismatched": self.mismatched,
            "status": self.status,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class EnvironmentInventoryItem:
    name: str
    kind: str
    version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "version": self.version,
            "metadata": dict(self.metadata),
        }


@runtime_checkable
class QualityHistoryProvider(Protocol):
    def record(self, observation: QualityObservation) -> None: ...

    def history(self, subject_id: str) -> list[QualityObservation]: ...


@runtime_checkable
class StatisticalObservationProvider(Protocol):
    def record(self, observation: StatisticalObservation) -> None: ...

    def latest(self, subject_id: str) -> StatisticalObservation | None: ...


@runtime_checkable
class ReconciliationEvidenceProvider(Protocol):
    def put(self, evidence: ReconciliationEvidence) -> None: ...

    def get(self, subject_id: str) -> ReconciliationEvidence | None: ...


@runtime_checkable
class EnvironmentInventoryProvider(Protocol):
    def list_items(self) -> list[EnvironmentInventoryItem]: ...


@dataclass
class InMemoryQualityHistory:
    _history: dict[str, list[QualityObservation]] = field(default_factory=dict)

    def record(self, observation: QualityObservation) -> None:
        self._history.setdefault(observation.subject_id, []).append(observation)

    def history(self, subject_id: str) -> list[QualityObservation]:
        return list(self._history.get(subject_id, ()))


@dataclass
class InMemoryStatisticalObservations:
    _latest: dict[str, StatisticalObservation] = field(default_factory=dict)

    def record(self, observation: StatisticalObservation) -> None:
        self._latest[observation.subject_id] = observation

    def latest(self, subject_id: str) -> StatisticalObservation | None:
        return self._latest.get(subject_id)


@dataclass
class InMemoryReconciliationEvidence:
    _items: dict[str, ReconciliationEvidence] = field(default_factory=dict)

    def put(self, evidence: ReconciliationEvidence) -> None:
        self._items[evidence.subject_id] = evidence

    def get(self, subject_id: str) -> ReconciliationEvidence | None:
        return self._items.get(subject_id)


@dataclass
class InMemoryEnvironmentInventory:
    items: list[EnvironmentInventoryItem] = field(default_factory=list)

    def list_items(self) -> list[EnvironmentInventoryItem]:
        return list(self.items)


@dataclass
class FileRefProvider:
    """JSON file reference for reliability evidence (not a full remote store)."""

    path: Path
    policy: SafeIoPolicy | None = None

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        if self.policy is None:
            self.policy = SafeIoPolicy.for_root(self.path.parent)
        _resolved, text, _events = read_text_safe(
            self.path, self.policy, run_id="reliability-read"
        )
        return json.loads(text)

    def write(self, data: dict[str, Any]) -> None:
        if self.policy is None:
            self.policy = SafeIoPolicy.for_root(self.path.parent)
        write_json_safe(self.path, data, self.policy, run_id="reliability-write")
