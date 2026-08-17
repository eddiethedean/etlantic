"""Engine-free stream semantic model (046-M)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from etlantic.streaming.diagnostics import str_diagnostic


class TimeDomain(StrEnum):
    """Clock used for watermarks and lateness."""

    EVENT_TIME = "event_time"
    PROCESSING_TIME = "processing_time"


class Boundedness(StrEnum):
    """Whether an input is a bounded snapshot or an unbounded stream."""

    BOUNDED = "bounded"
    UNBOUNDED = "unbounded"


class StreamTrigger(StrEnum):
    """When streaming work may emit results."""

    PROCESSING_TIME = "processing_time"
    AVAILABLE_NOW = "available_now"
    ONCE = "once"
    CONTINUOUS = "continuous"


class LatenessPolicy(StrEnum):
    """Policy for events past the watermark (not record-error DLQ)."""

    DROP = "drop"
    ACCEPT = "accept"
    QUARANTINE = "quarantine"
    SIDE_OUTPUT = "side_output"


@dataclass(frozen=True, slots=True)
class WatermarkSpec:
    """Event-time watermark configuration (core, not Spark)."""

    event_time_field: str
    delay: str
    late_policy: LatenessPolicy = LatenessPolicy.DROP

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_time_field": self.event_time_field,
            "delay": self.delay,
            "late_policy": self.late_policy.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WatermarkSpec:
        return cls(
            event_time_field=str(data["event_time_field"]),
            delay=str(data["delay"]),
            late_policy=LatenessPolicy(str(data.get("late_policy") or "drop")),
        )


@dataclass(frozen=True, slots=True)
class StreamSemantics:
    """Declared stream-time semantics for a source or region."""

    boundedness: Boundedness = Boundedness.BOUNDED
    time_domain: TimeDomain = TimeDomain.PROCESSING_TIME
    trigger: StreamTrigger = StreamTrigger.AVAILABLE_NOW
    trigger_interval: str | None = None
    watermark: WatermarkSpec | None = None
    ordering_required: bool = False
    deletes_required: bool = False
    transactions_required: bool = False
    required_extras: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "boundedness": self.boundedness.value,
            "time_domain": self.time_domain.value,
            "trigger": self.trigger.value,
            "trigger_interval": self.trigger_interval,
            "watermark": None if self.watermark is None else self.watermark.to_dict(),
            "ordering_required": self.ordering_required,
            "deletes_required": self.deletes_required,
            "transactions_required": self.transactions_required,
            "required_extras": list(self.required_extras),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StreamSemantics:
        water_raw = data.get("watermark")
        extras = tuple(str(x) for x in (data.get("required_extras") or ()))
        return cls(
            boundedness=Boundedness(str(data.get("boundedness") or "bounded")),
            time_domain=TimeDomain(str(data.get("time_domain") or "processing_time")),
            trigger=StreamTrigger(str(data.get("trigger") or "available_now")),
            trigger_interval=(
                None
                if data.get("trigger_interval") in (None, "")
                else str(data.get("trigger_interval"))
            ),
            watermark=(
                WatermarkSpec.from_dict(water_raw)
                if isinstance(water_raw, Mapping)
                else None
            ),
            ordering_required=bool(data.get("ordering_required", False)),
            deletes_required=bool(data.get("deletes_required", False)),
            transactions_required=bool(data.get("transactions_required", False)),
            required_extras=extras,
        )

    def unsupported_diagnostic(self, engine: str, missing: str) -> Any:
        """Fail closed when a provider cannot prove a required semantic."""
        return str_diagnostic(
            "unsupported_semantics",
            (
                f"Engine {engine!r} cannot prove required stream semantic "
                f"{missing!r}; refusing append-only degrade."
            ),
            path=("streaming", "semantics", missing),
            metadata={"engine": engine, "missing": missing},
        )
