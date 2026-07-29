"""Lifecycle events and breakpoint bus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

LIFECYCLE_EVENT_SCHEMA = "etlantic.lifecycle_event/1"
SECURITY_EVENT_SCHEMA = "etlantic.security_event/1"
RUN_HISTORY_RECORD_SCHEMA = "etlantic.run_history_record/1"

RunHistoryRecordKind = Literal["lifecycle_event", "security_event", "report_summary"]


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    """Immutable lifecycle event (secret-free)."""

    kind: str
    run_id: str
    pipeline_id: str
    at: datetime = field(default_factory=lambda: datetime.now(UTC))
    step_name: str | None = None
    attempt: int | None = None
    status: str | None = None
    message: str | None = None
    plan_id: str | None = None
    region_id: str | None = None
    physical_unit: str | None = None
    backend: str | None = None
    correlation_id: str | None = None
    annotations: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = LIFECYCLE_EVENT_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema_version,
            "kind": self.kind,
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "plan_id": self.plan_id,
            "region_id": self.region_id,
            "physical_unit": self.physical_unit,
            "backend": self.backend,
            "correlation_id": self.correlation_id,
            "at": self.at.isoformat(),
            "step_name": self.step_name,
            "attempt": self.attempt,
            "status": self.status,
            "message": self.message,
            "annotations": dict(self.annotations),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LifecycleEvent:
        at_raw = data.get("at")
        at = (
            datetime.fromisoformat(at_raw)
            if isinstance(at_raw, str)
            else datetime.now(UTC)
        )
        return cls(
            kind=str(data["kind"]),
            run_id=str(data["run_id"]),
            pipeline_id=str(data["pipeline_id"]),
            at=at,
            step_name=data.get("step_name"),
            attempt=data.get("attempt"),
            status=data.get("status"),
            message=data.get("message"),
            plan_id=data.get("plan_id"),
            region_id=data.get("region_id"),
            physical_unit=data.get("physical_unit"),
            backend=data.get("backend"),
            correlation_id=data.get("correlation_id"),
            annotations=dict(data.get("annotations") or {}),
            metadata=dict(data.get("metadata") or {}),
            schema_version=str(data.get("schema") or LIFECYCLE_EVENT_SCHEMA),
        )


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    """Immutable security audit event (never includes secret values or rows)."""

    kind: str
    run_id: str
    provider: str
    secret_identity: str = ""
    outcome: str = "unknown"
    at: datetime = field(default_factory=lambda: datetime.now(UTC))
    step_name: str | None = None
    message: str | None = None
    schema_version: str = SECURITY_EVENT_SCHEMA
    subject: str | None = None
    plan_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema_version,
            "kind": self.kind,
            "run_id": self.run_id,
            "provider": self.provider,
            "secret_identity": self.secret_identity,
            "outcome": self.outcome,
            "at": self.at.isoformat(),
            "step_name": self.step_name,
            "message": self.message,
            "subject": self.subject,
            "plan_id": self.plan_id,
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class RunHistoryRecord:
    """Normalized append unit for durable run-history providers."""

    run_id: str
    pipeline_id: str
    record_kind: RunHistoryRecordKind
    payload: dict[str, Any]
    at: datetime = field(default_factory=lambda: datetime.now(UTC))
    plan_id: str | None = None
    schema_version: str = RUN_HISTORY_RECORD_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema_version,
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "plan_id": self.plan_id,
            "record_kind": self.record_kind,
            "at": self.at.isoformat(),
            "payload": dict(self.payload),
        }


EventListener = Callable[[LifecycleEvent | SecurityEvent], None]


@dataclass
class EventBus:
    """Simple in-process event / breakpoint bus."""

    _listeners: list[EventListener] = field(default_factory=list)
    _events: list[LifecycleEvent | SecurityEvent] = field(default_factory=list)

    def subscribe(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    def emit(self, event: LifecycleEvent | SecurityEvent) -> None:
        self._events.append(event)
        for listener in list(self._listeners):
            listener(event)

    @property
    def events(self) -> list[LifecycleEvent | SecurityEvent]:
        return list(self._events)
