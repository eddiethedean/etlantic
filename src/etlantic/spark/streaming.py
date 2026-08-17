"""Structured Streaming foundation types (experimental).

See :data:`~etlantic.spark.STREAMING_STABILITY` for stability expectations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from etlantic.spark.protocol import STREAMING_STABILITY


def project_core_watermark(core: Any) -> WatermarkSpec:
    """Project core :class:`etlantic.streaming.semantics.WatermarkSpec` onto Spark types."""
    event_time = getattr(core, "event_time_field", None) or getattr(
        core, "event_time_column", ""
    )
    late = getattr(core, "late_policy", LateEventPolicy.DROP)
    late_value = late.value if hasattr(late, "value") else str(late)
    return WatermarkSpec(
        event_time_column=str(event_time),
        delay=str(getattr(core, "delay", "0 seconds")),
        late_policy=LateEventPolicy(late_value),
    )


def project_core_semantics(core: Any) -> StreamingQuerySpec:
    """Project core :class:`etlantic.streaming.semantics.StreamSemantics` onto Spark types."""
    watermark = getattr(core, "watermark", None)
    trigger = getattr(core, "trigger", StreamingTrigger.AVAILABLE_NOW)
    trigger_value = trigger.value if hasattr(trigger, "value") else str(trigger)
    return StreamingQuerySpec(
        checkpoint_location="memory://spark-stream",
        trigger=StreamingTrigger(trigger_value),
        trigger_interval=getattr(core, "trigger_interval", None),
        watermark=project_core_watermark(watermark) if watermark is not None else None,
        metadata={"etlantic.streaming.projection": "spark"},
    )


class StreamingTrigger(StrEnum):
    """Supported Structured Streaming triggers."""

    PROCESSING_TIME = "processing_time"
    AVAILABLE_NOW = "available_now"
    ONCE = "once"
    CONTINUOUS = "continuous"


class StreamingOutputMode(StrEnum):
    """Streaming output modes."""

    APPEND = "append"
    UPDATE = "update"
    COMPLETE = "complete"


class LateEventPolicy(StrEnum):
    """Policy for events past the watermark."""

    DROP = "drop"
    ACCEPT = "accept"
    QUARANTINE = "quarantine"
    SIDE_OUTPUT = "side_output"


@dataclass(frozen=True, slots=True)
class WatermarkSpec:
    """Event-time watermark configuration."""

    event_time_column: str
    delay: str  # e.g. "10 minutes"
    late_policy: LateEventPolicy = LateEventPolicy.DROP

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_time_column": self.event_time_column,
            "delay": self.delay,
            "late_policy": self.late_policy.value,
        }


@dataclass(frozen=True, slots=True)
class StreamingQuerySpec:
    """Experimental streaming query declaration."""

    checkpoint_location: str
    trigger: StreamingTrigger = StreamingTrigger.AVAILABLE_NOW
    trigger_interval: str | None = None
    output_mode: StreamingOutputMode = StreamingOutputMode.APPEND
    watermark: WatermarkSpec | None = None
    query_name: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_location": self.checkpoint_location,
            "trigger": self.trigger.value,
            "trigger_interval": self.trigger_interval,
            "output_mode": self.output_mode.value,
            "watermark": self.watermark.to_dict() if self.watermark else None,
            "query_name": self.query_name,
            "metadata": dict(self.metadata),
            "stability": STREAMING_STABILITY,
        }


@dataclass
class StreamingProgress:
    """Normalized streaming progress evidence."""

    query_id: str
    batch_id: int | None = None
    input_rows: int | None = None
    status: str | None = None
    watermark: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "batch_id": self.batch_id,
            "input_rows": self.input_rows,
            "status": self.status,
            "watermark": self.watermark,
            "extras": dict(self.extras),
            "stability": STREAMING_STABILITY,
        }
