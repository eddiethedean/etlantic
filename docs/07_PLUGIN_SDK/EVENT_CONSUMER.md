# Event Consumer

> **Status: Available in ETLantic 0.43.0.** Optional analytics over normalized
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
for programmatic trend summaries. The CLI
`etlantic reliability quality-trends` surface is **preview-only** and requires
inline `--values` samples (it does not load a live consumer store).

## Conformance

```python
from etlantic.testing import run_event_consumer_conformance_suite

run_event_consumer_conformance_suite(consumer)
```

## See also

- [Observability Provider](OBSERVABILITY_PROVIDER.md)
- [Run History Provider](RUN_HISTORY_PROVIDER.md)
