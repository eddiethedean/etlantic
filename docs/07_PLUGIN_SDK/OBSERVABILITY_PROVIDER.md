# Observability Provider

> **Status: Available in ETLantic 0.47.0.** Async `/1` protocol with entry-point
> group `etlantic.observability_providers` and in-core reference providers.

An observability provider receives ETLantic lifecycle events, structured
logs, metrics, traces, and lineage signals and routes them to external systems.

It does not define pipeline semantics or determine whether execution succeeds.

## Responsibilities

An observability provider may:

- emit structured logs
- publish metrics
- create and propagate traces
- persist lifecycle events
- persist normalized run history
- emit lineage to OpenLineage-compatible systems
- attach backend links and identifiers

The provider must not:

- execute transformations
- alter the `PipelinePlan`
- hide execution failures
- receive unredacted secrets
- make storage-specific records the core result model

## Public protocol

```python
class ObservabilityProvider(Protocol):
    descriptor: ProviderDescriptor

    async def start(self, context: ObservabilityContext) -> None: ...

    async def emit_event(self, event: LifecycleEvent) -> None: ...

    async def emit_log(self, record: LogRecord) -> None: ...

    async def emit_metric(self, metric: MetricRecord) -> None: ...

    async def flush(self) -> None: ...

    async def close(self) -> None: ...
```

Capabilities should be explicit:

```python
ObservabilityCapabilities(
    logs=True,
    metrics=True,
    traces=True,
    lifecycle_events=True,
    durable_run_history=True,
    lineage=False,
    batching=True,
)
```

## Delivery Semantics

Providers should declare:

- best-effort or durable delivery
- batching behavior
- flush and shutdown guarantees
- backpressure handling
- maximum record size
- offline buffering
- retry behavior

Observability failure should normally produce a warning without changing a
successful data result. Profiles may require durable audit delivery, in which
case the policy must be explicit and planning must validate support.

## Implementations

Potential providers include:

- standard Python logging
- JSON console
- rotating files
- OpenTelemetry
- OpenLineage
- SQL or Delta run-history stores
- cloud logging services
- test capture provider

Multiple providers may subscribe to the same event stream.

The optional OpenLineage implementation and its stable identity/facet mapping
are assigned to the 0.40 metadata-interoperability gate in the
[Adoption, Connectivity, and Operations Plan](../11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md#metadata-and-catalog-interoperability).
It is not shipped merely because the general observability protocol is
available.

## Redaction

ETLantic should redact records before provider dispatch. Providers may add
further controls but must never weaken the core redaction policy.

## Conformance

Provider tests should verify:

- correct correlation context
- redaction
- lifecycle ordering
- async-safe batching
- bounded retry behavior
- reliable flush on clean shutdown
- graceful handling of provider outages

## See Also

- [Logging](../06_EXECUTION/LOGGING.md)
- [Testing Plugins](TESTING_PLUGINS.md)
- [Resource Provider](RESOURCE_PROVIDER.md)
