"""Portable reliability and intent models (schemas in 0.3; enforcement in 0.4+)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class WriteMode(StrEnum):
    """Declared write semantics."""

    APPEND = "append"
    OVERWRITE = "overwrite"
    MERGE = "merge"
    UPSERT = "upsert"
    NO_WRITE = "no_write"


class MaterializationMode(StrEnum):
    """Declared materialization intent."""

    LAZY = "lazy"
    EAGER = "eager"
    CHECKPOINT = "checkpoint"
    PUBLISH = "publish"


@dataclass(frozen=True, slots=True)
class FreshnessExpectation:
    """Declared freshness expectation for a subject."""

    subject_id: str
    max_age_seconds: float | None = None
    time_basis: str = "event_time"
    grace_seconds: float = 0
    timezone: str = "UTC"
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Deterministic identity."""
        return f"freshness:{self.subject_id}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize expectation."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PartitionCompletenessExpectation:
    """Declared partition-completeness expectation."""

    subject_id: str
    partition_keys: tuple[str, ...]
    allowed_lateness_seconds: float = 0
    minimum_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Deterministic identity."""
        keys = ",".join(self.partition_keys)
        return f"partitions:{self.subject_id}:{keys}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize expectation."""
        data = asdict(self)
        data["partition_keys"] = list(self.partition_keys)
        return data


@dataclass(frozen=True, slots=True)
class WriteIntent:
    """Declared write intent for a sink or publication."""

    subject_id: str
    mode: WriteMode
    keys: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Deterministic identity."""
        return f"write:{self.subject_id}:{self.mode.value}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize intent."""
        return {
            "subject_id": self.subject_id,
            "mode": self.mode.value,
            "keys": list(self.keys),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class MaterializationIntent:
    """Declared materialization intent for an output."""

    subject_id: str
    mode: MaterializationMode
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Deterministic identity."""
        return f"materialize:{self.subject_id}:{self.mode.value}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize intent."""
        return {
            "subject_id": self.subject_id,
            "mode": self.mode.value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class IdempotencyDeclaration:
    """Conditional idempotency declaration."""

    subject_id: str
    keys: tuple[str, ...]
    conditions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Deterministic identity."""
        return f"idempotency:{self.subject_id}:{','.join(self.keys)}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize declaration."""
        return {
            "subject_id": self.subject_id,
            "keys": list(self.keys),
            "conditions": list(self.conditions),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class RetrySafetyDeclaration:
    """Retry-safety declaration for a step or region."""

    subject_id: str
    safe: bool
    max_attempts: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Deterministic identity."""
        return f"retry_safety:{self.subject_id}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize declaration."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReconciliationDeclaration:
    """Declared reconciliation check between subjects."""

    left_subject_id: str
    right_subject_id: str
    keys: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Deterministic identity."""
        return (
            f"reconcile:{self.left_subject_id}|{self.right_subject_id}:"
            f"{','.join(self.keys)}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize declaration."""
        return {
            "left_subject_id": self.left_subject_id,
            "right_subject_id": self.right_subject_id,
            "keys": list(self.keys),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class BackfillDeclaration:
    """Declared backfill scope (execution is 0.4+)."""

    subject_id: str
    start: str | None = None
    end: str | None = None
    partitions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Deterministic identity."""
        return f"backfill:{self.subject_id}:{self.start}:{self.end}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize declaration."""
        return {
            "subject_id": self.subject_id,
            "start": self.start,
            "end": self.end,
            "partitions": list(self.partitions),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class RepairDeclaration:
    """Declared repair scope (execution is 0.4+)."""

    subject_id: str
    reason: str
    affected_nodes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Deterministic identity."""
        return f"repair:{self.subject_id}:{self.reason}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize declaration."""
        return {
            "subject_id": self.subject_id,
            "reason": self.reason,
            "affected_nodes": list(self.affected_nodes),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ReliabilityEvidence:
    """Portable evidence schema (no secrets or raw rows)."""

    subject_id: str
    kind: str
    summary: str
    confidence: float | None = None
    fingerprint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def identity(self) -> str:
        """Deterministic identity."""
        return f"evidence:{self.kind}:{self.subject_id}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize evidence."""
        return asdict(self)


def environment_identity(
    *, profile: str, security_domain: str, workspace: str = ""
) -> str:
    """Deterministic identity for a resolved environment."""
    return f"env:{security_domain}/{profile}/{workspace or 'default'}"


def implementation_selection_identity(*, transformation_id: str, engine: str) -> str:
    """Deterministic identity for a selected implementation."""
    return f"impl:{transformation_id}::{engine}"


def quality_metric_identity(*, subject_id: str, metric: str) -> str:
    """Deterministic identity for a quality metric."""
    return f"metric:{subject_id}:{metric}"


def statistical_observation_identity(*, subject_id: str, feature: str) -> str:
    """Deterministic identity for a statistical observation."""
    return f"stat:{subject_id}:{feature}"


def fingerprint_mapping(data: dict[str, Any]) -> str:
    """Deterministic fingerprint for a mapping."""
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()
