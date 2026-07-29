"""Event consumer protocol for derived analytics (etlantic.event_consumer/1)."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from etlantic.reliability_providers import (
    QualityObservation,
    StatisticalObservation,
)
from etlantic.runtime.events import LifecycleEvent, SecurityEvent

EVENT_CONSUMER_PROTOCOL = "etlantic.event_consumer/1"


@dataclass(frozen=True, slots=True)
class EventConsumerCapabilities:
    """Declared event-consumer capabilities."""

    trend: bool = False
    quality: bool = False
    performance: bool = False
    anomaly: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "trend": self.trend,
            "quality": self.quality,
            "performance": self.performance,
            "anomaly": self.anomaly,
        }


@dataclass(frozen=True, slots=True)
class EventConsumerDescriptor:
    """Installed event-consumer metadata."""

    name: str
    engine: str
    version: str = "0.34.0"
    protocol: str = EVENT_CONSUMER_PROTOCOL
    capabilities: EventConsumerCapabilities = field(
        default_factory=EventConsumerCapabilities
    )


@runtime_checkable
class EventConsumer(Protocol):
    """Consumes redacted lifecycle events for derived analytics."""

    @property
    def descriptor(self) -> EventConsumerDescriptor: ...

    def consume(self, event: LifecycleEvent | SecurityEvent) -> None: ...

    def flush(self) -> None: ...


@dataclass
class InMemoryTrendConsumer:
    """Reference consumer tracking numeric samples for quality-trend CLI."""

    subject_id: str = "default"

    @property
    def descriptor(self) -> EventConsumerDescriptor:
        return EventConsumerDescriptor(
            name="memory-trend",
            engine="memory",
            capabilities=EventConsumerCapabilities(trend=True, quality=True),
        )

    _quality: list[QualityObservation] = field(default_factory=list)
    _stats: list[StatisticalObservation] = field(default_factory=list)
    _events: list[dict[str, Any]] = field(default_factory=list)
    _max_events: int = 10_000

    def consume(self, event: LifecycleEvent | SecurityEvent) -> None:
        payload = event.to_dict()
        if len(self._events) >= self._max_events:
            self._events.pop(0)
        self._events.append(payload)
        meta = getattr(event, "metadata", None) or {}
        annotations = getattr(event, "annotations", None) or {}
        merged = {**dict(meta), **dict(annotations)}
        metric = merged.get("quality_metric")
        value = merged.get("quality_value")
        if metric is not None and value is not None:
            with contextlib.suppress(TypeError, ValueError):
                self._quality.append(
                    QualityObservation(
                        subject_id=str(merged.get("subject_id") or self.subject_id),
                        metric=str(metric),
                        value=float(value),
                        metadata={
                            k: v
                            for k, v in merged.items()
                            if k not in {"quality_metric", "quality_value"}
                        },
                    )
                )

    def flush(self) -> None:
        return None

    def quality_history(
        self, subject_id: str | None = None
    ) -> list[QualityObservation]:
        sid = subject_id or self.subject_id
        return [o for o in self._quality if o.subject_id == sid]

    def trend_summary(self, subject_id: str | None = None) -> dict[str, Any]:
        obs = self.quality_history(subject_id)
        values = [o.value for o in obs]
        if not values:
            return {
                "subject_id": subject_id or self.subject_id,
                "n": 0,
                "mean": None,
                "min": None,
                "max": None,
            }
        return {
            "subject_id": subject_id or self.subject_id,
            "n": len(values),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }
