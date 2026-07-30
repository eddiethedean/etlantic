# Event Consumer

> **Status: Available in ETLantic 0.35.0.** Optional analytics over normalized
> lifecycle events.

Event consumers derive trend, quality, performance, or anomaly signals from
redacted lifecycle events. They do not alter pipeline semantics.

## Protocol

```python
class EventConsumer(Protocol):
    @property
    def descriptor(self) -> EventConsumerDescriptor: ...

    def consume(self, event: LifecycleEvent | SecurityEvent) -> None: ...
    def flush(self) -> None: ...
```

Entry-point group: `etlantic.event_consumers`.

## Reference implementation

`InMemoryTrendConsumer` aggregates `quality_metric` / `quality_value` annotations
for `etlantic reliability quality-trends`.

## Conformance

```python
from etlantic.testing import run_event_consumer_conformance_suite

run_event_consumer_conformance_suite(consumer)
```

## See also

- [Observability Provider](OBSERVABILITY_PROVIDER.md)
- [Run History Provider](RUN_HISTORY_PROVIDER.md)
