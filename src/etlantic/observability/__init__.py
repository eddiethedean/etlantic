"""Observability, run history, and event consumer protocols (0.34)."""

from etlantic.observability.consumers import (
    EVENT_CONSUMER_PROTOCOL,
    EventConsumer,
    EventConsumerCapabilities,
    EventConsumerDescriptor,
    InMemoryTrendConsumer,
)
from etlantic.observability.history import (
    RUN_HISTORY_PROTOCOL,
    FileRunHistoryProvider,
    InMemoryRunHistoryProvider,
    RunHistoryCapabilities,
    RunHistoryEntry,
    RunHistoryProvider,
    RunHistoryProviderDescriptor,
    RunHistoryQuery,
)
from etlantic.observability.protocol import (
    OBSERVABILITY_PROTOCOL,
    JsonConsoleLogger,
    JsonConsoleObservabilityProvider,
    MetricRecord,
    NotificationProvider,
    ObservabilityCapabilities,
    ObservabilityContext,
    ObservabilityEvent,
    ObservabilityProvider,
    ObservabilityProviderDescriptor,
    OpenTelemetryAdapter,
)
from etlantic.runtime.events import RunHistoryRecord

__all__ = [
    "EVENT_CONSUMER_PROTOCOL",
    "OBSERVABILITY_PROTOCOL",
    "RUN_HISTORY_PROTOCOL",
    "EventConsumer",
    "EventConsumerCapabilities",
    "EventConsumerDescriptor",
    "FileRunHistoryProvider",
    "InMemoryRunHistoryProvider",
    "InMemoryTrendConsumer",
    "JsonConsoleLogger",
    "JsonConsoleObservabilityProvider",
    "MetricRecord",
    "NotificationProvider",
    "ObservabilityCapabilities",
    "ObservabilityContext",
    "ObservabilityEvent",
    "ObservabilityProvider",
    "ObservabilityProviderDescriptor",
    "OpenTelemetryAdapter",
    "RunHistoryCapabilities",
    "RunHistoryEntry",
    "RunHistoryProvider",
    "RunHistoryProviderDescriptor",
    "RunHistoryQuery",
    "RunHistoryRecord",
]
