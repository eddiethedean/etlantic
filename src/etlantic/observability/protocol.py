"""Observability provider protocol (etlantic.observability/1)."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from etlantic.runtime.events import LifecycleEvent, SecurityEvent
from etlantic.runtime.logging import LogRecord

OBSERVABILITY_PROTOCOL = "etlantic.observability/1"


@dataclass(frozen=True, slots=True)
class ObservabilityCapabilities:
    """Declared observability-provider capabilities."""

    logs: bool = True
    metrics: bool = False
    traces: bool = False
    lifecycle_events: bool = True
    durable_run_history: bool = False
    lineage: bool = False
    batching: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "logs": self.logs,
            "metrics": self.metrics,
            "traces": self.traces,
            "lifecycle_events": self.lifecycle_events,
            "durable_run_history": self.durable_run_history,
            "lineage": self.lineage,
            "batching": self.batching,
        }


@dataclass(frozen=True, slots=True)
class ObservabilityProviderDescriptor:
    """Installed observability provider metadata."""

    name: str
    engine: str
    version: str = "0.34.0"
    protocol: str = OBSERVABILITY_PROTOCOL
    capabilities: ObservabilityCapabilities = field(
        default_factory=ObservabilityCapabilities
    )


@dataclass(frozen=True, slots=True)
class ObservabilityContext:
    """Correlation context for observability dispatch."""

    run_id: str
    pipeline_id: str
    plan_id: str | None = None
    profile: str | None = None
    correlation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MetricRecord:
    """Secret-free metric sample."""

    name: str
    value: float
    unit: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ObservabilityEvent:
    """Legacy structured observability event (secret-free attributes only)."""

    name: str
    severity: str = "info"
    message: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "severity": self.severity,
            "message": self.message,
            "attributes": dict(self.attributes),
        }


@runtime_checkable
class ObservabilityProvider(Protocol):
    """Async observability provider protocol (/1)."""

    @property
    def descriptor(self) -> ObservabilityProviderDescriptor: ...

    def lifespan(self, context: ObservabilityContext) -> AsyncIterator[None]: ...

    async def emit_event(self, event: LifecycleEvent | SecurityEvent) -> None: ...

    async def emit_log(self, record: LogRecord) -> None: ...

    async def emit_metric(self, metric: MetricRecord) -> None: ...

    async def flush(self) -> None: ...

    async def close(self) -> None: ...


@runtime_checkable
class NotificationProvider(Protocol):
    def notify(
        self, subject: str, message: str, *, dedupe_key: str | None = None
    ) -> None: ...


@dataclass
class JsonConsoleObservabilityProvider:
    """Reference JSON console observability provider."""

    stream: Any = field(default_factory=lambda: sys.stdout)
    _seen: set[str] = field(default_factory=set)

    @property
    def descriptor(self) -> ObservabilityProviderDescriptor:
        return ObservabilityProviderDescriptor(
            name="json-console",
            engine="console",
            capabilities=ObservabilityCapabilities(
                logs=True,
                lifecycle_events=True,
                batching=False,
            ),
        )

    def lifespan(self, context: ObservabilityContext) -> AsyncIterator[None]:
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _cm() -> AsyncIterator[None]:
            yield

        return _cm()

    async def emit_event(self, event: LifecycleEvent | SecurityEvent) -> None:
        payload = event.to_dict()
        self.stream.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
        self.stream.flush()

    async def emit_log(self, record: LogRecord) -> None:
        self.stream.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
        self.stream.flush()

    async def emit_metric(self, metric: MetricRecord) -> None:
        payload = {
            "type": "metric",
            "name": metric.name,
            "value": metric.value,
            "unit": metric.unit,
            "attributes": dict(metric.attributes),
        }
        self.stream.write(json.dumps(payload, sort_keys=True) + "\n")
        self.stream.flush()

    async def flush(self) -> None:
        if hasattr(self.stream, "flush"):
            self.stream.flush()

    async def close(self) -> None:
        await self.flush()

    def notify(
        self, subject: str, message: str, *, dedupe_key: str | None = None
    ) -> None:
        key = dedupe_key or f"{subject}:{message}"
        if key in self._seen:
            return
        self._seen.add(key)
        self.stream.write(
            json.dumps(
                {
                    "name": "notification",
                    "severity": "info",
                    "message": message,
                    "attributes": {"subject": subject},
                },
                sort_keys=True,
            )
            + "\n"
        )
        self.stream.flush()


# Backward-compatible alias
JsonConsoleLogger = JsonConsoleObservabilityProvider


@dataclass
class OpenTelemetryAdapter:
    """Optional OpenTelemetry bridge (requires ``etlantic[otel]``)."""

    service_name: str = "etlantic"

    @property
    def descriptor(self) -> ObservabilityProviderDescriptor:
        return ObservabilityProviderDescriptor(
            name="opentelemetry",
            engine="otel",
            capabilities=ObservabilityCapabilities(
                logs=True,
                traces=True,
                lifecycle_events=True,
            ),
        )

    def lifespan(self, context: ObservabilityContext) -> AsyncIterator[None]:
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _cm() -> AsyncIterator[None]:
            yield

        return _cm()

    async def emit_event(self, event: LifecycleEvent | SecurityEvent) -> None:
        self.emit(
            ObservabilityEvent(
                name=event.kind if hasattr(event, "kind") else "security",
                attributes=event.to_dict(),
            )
        )

    async def emit_log(self, record: LogRecord) -> None:
        logging.getLogger("etlantic.otel").info("%s", record.message)

    async def emit_metric(self, metric: MetricRecord) -> None:
        logging.getLogger("etlantic.otel").info(
            "metric %s=%s", metric.name, metric.value
        )

    async def flush(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def emit(self, event: ObservabilityEvent) -> None:
        try:
            from opentelemetry import trace  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "OpenTelemetry support requires installing etlantic[otel]"
            ) from exc
        tracer = trace.get_tracer(self.service_name)
        with tracer.start_as_current_span(event.name) as span:
            for key, value in event.attributes.items():
                span.set_attribute(str(key), str(value))
            if event.message:
                span.add_event(event.message)
        logging.getLogger("etlantic.otel").info(
            "%s %s", event.name, event.message or ""
        )
