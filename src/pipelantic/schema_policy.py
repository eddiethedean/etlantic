"""Schema drift policy decisions for local runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from pipelantic.schema_drift import (
    NormalizedSchema,
    SchemaChangeSet,
    SchemaObservation,
    diff_normalized_schemas,
    normalize_schema_from_model,
)


class DriftAction(StrEnum):
    """Profile-scoped schema drift policy actions."""

    RECORD = "record"
    WARN = "warn"
    NOTIFY = "notify"
    APPROVE = "approve"
    QUARANTINE = "quarantine"
    ADAPT = "adapt"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class SchemaDriftPolicy:
    """Policy controlling runtime response to schema drift."""

    default_action: DriftAction = DriftAction.RECORD
    overrides: dict[str, DriftAction] = field(default_factory=dict)
    production_fail_closed: bool = True

    def decide(
        self,
        *,
        subject_id: str,
        change_set: SchemaChangeSet | None,
        profile_name: str = "development",
    ) -> DriftAction:
        if change_set is None or not change_set.changes:
            return DriftAction.RECORD
        if subject_id in self.overrides:
            return self.overrides[subject_id]
        if (
            self.production_fail_closed
            and profile_name == "production"
            and any(c.impact.value == "breaking" for c in change_set.changes)
        ):
            return DriftAction.BLOCK
        return self.default_action


@dataclass(frozen=True, slots=True)
class DriftDecision:
    """Recorded drift-policy decision."""

    subject_id: str
    action: DriftAction
    declared_fingerprint: str | None
    previous_fingerprint: str | None
    current_fingerprint: str | None
    change_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "action": self.action.value,
            "declared_fingerprint": self.declared_fingerprint,
            "previous_fingerprint": self.previous_fingerprint,
            "current_fingerprint": self.current_fingerprint,
            "change_count": self.change_count,
            "metadata": dict(self.metadata),
        }


class SchemaHistoryProvider(Protocol):
    def record(self, observation: SchemaObservation) -> None: ...

    def latest(self, subject_id: str) -> SchemaObservation | None: ...


@dataclass
class InMemorySchemaHistory:
    """Process-local schema observation history."""

    _latest: dict[str, SchemaObservation] = field(default_factory=dict)
    _history: dict[str, list[SchemaObservation]] = field(default_factory=dict)

    def record(self, observation: SchemaObservation) -> None:
        self._latest[observation.subject_id] = observation
        self._history.setdefault(observation.subject_id, []).append(observation)

    def latest(self, subject_id: str) -> SchemaObservation | None:
        return self._latest.get(subject_id)

    def history(self, subject_id: str) -> list[SchemaObservation]:
        return list(self._history.get(subject_id, ()))


def observe_model_schema(
    subject_id: str,
    model: type[Any] | None,
    *,
    layer: str,
) -> SchemaObservation | None:
    if model is None:
        return None
    normalized = normalize_schema_from_model(model)
    return SchemaObservation(
        subject_id=subject_id,
        schema=normalized,
        inspector=layer,
        metadata={"layer": layer},
    )


def evaluate_drift(
    *,
    subject_id: str,
    declared: NormalizedSchema | None,
    previous: SchemaObservation | None,
    current: SchemaObservation | None,
    policy: SchemaDriftPolicy,
    profile_name: str,
) -> DriftDecision:
    change_set = None
    if previous is not None and current is not None:
        change_set = diff_normalized_schemas(previous.schema, current.schema)
    elif declared is not None and current is not None:
        change_set = diff_normalized_schemas(declared, current.schema)
    action = policy.decide(
        subject_id=subject_id, change_set=change_set, profile_name=profile_name
    )
    return DriftDecision(
        subject_id=subject_id,
        action=action,
        declared_fingerprint=declared.fingerprint() if declared else None,
        previous_fingerprint=(
            previous.schema.fingerprint() if previous is not None else None
        ),
        current_fingerprint=(
            current.schema.fingerprint() if current is not None else None
        ),
        change_count=len(change_set.changes) if change_set else 0,
    )
