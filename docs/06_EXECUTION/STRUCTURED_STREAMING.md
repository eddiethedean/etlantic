# Structured Streaming

**Status: Experimental in ETLantic 0.40.0.** Batch Spark is the production path;
streaming APIs may change without a major version bump.

Structured Streaming is ETLantic's execution model for unbounded data using
Apache Spark Structured Streaming. It allows the same validated Pipeline Plans
used for batch execution to process continuously arriving events while
preserving contracts, transformation semantics, lineage, and validation.

Streaming is an execution strategy—not a different pipeline model.

## Goals

Structured Streaming should:

- Preserve [ODCS](../03_DATA_CONTRACTS/ODCS.md), [DTCS](../04_TRANSFORMATIONS/DTCS.md), and [DPCS](../05_PIPELINES/DPCS.md) semantics.
- Support event-time processing.
- Support stateful and stateless transformations.
- Preserve contract validation.
- Make streaming behavior explicit and inspectable.
- Remain portable across Spark-supported streaming environments.

## Architecture

```text
Pipeline
    │
    ▼
Validation
    │
    ▼
Planning
    │
    ▼
Streaming-Capable Region
    │
    ▼
Spark Structured Streaming
    │
    ▼
Streaming Query
    │
    ▼
Streaming Sink
```

## Streaming Semantics

Pipeline authors define logical transformations exactly as they do for batch
pipelines.

A transformation may provide a PySpark streaming implementation when its
semantics support unbounded input.

## Event Time

Event time should be preferred over processing time whenever correctness depends
on when events actually occurred.

Typical event-time metadata includes:

- Event timestamp
- Watermark delay
- Allowed lateness
- Time zone

## Watermarks

Watermarks bound how long late data may arrive.

Conceptually:

```text
Events
  │
  ▼
Watermark
  │
  ▼
State Cleanup
```

Late-event policy should be explicit and may include:

- Accept
- Drop
- Quarantine
- Route to a side output

## Stateful Operations

Supported stateful operations include:

- Windowed aggregations
- Session windows
- Streaming joins
- Deduplication
- Stateful custom processing (where supported)

State must be backed by reliable checkpoints.

## Stateless Operations

Stateless operations include:

- Projection
- Filtering
- Mapping
- Simple enrichment
- Type conversion

These generally require no persistent state.

## Checkpoints

Streaming queries must use checkpoint storage to support:

- Recovery
- Exactly-once semantics where supported
- Stateful processing
- Watermark progress

Checkpoint locations belong in execution profiles or Resource Providers.

## Trigger Modes

Typical trigger modes include:

- Processing time
- Available-now
- Once
- Continuous (where supported)

The selected trigger is operational configuration rather than pipeline
semantics.

## Sources

Common streaming sources include:

- Kafka
- Delta Change Data Feed
- Cloud object storage
- File streams
- Custom Spark connectors

Logical pipeline bindings remain backend-independent.

## Sinks

Common sinks include:

- Delta Lake
- Kafka
- Iceberg
- Console (development)
- `foreachBatch`
- JDBC (batch-style publishing)

Sink guarantees depend on the selected connector.

## Delivery Guarantees

A plugin should declare supported guarantees such as:

- At-most-once
- At-least-once
- Exactly-once (when supported)

Guarantees must be documented per source and sink combination.

## Validation

Validation may occur:

- Per record
- Per micro-batch
- Per event-time window
- During sink publication

Unsupported contract rules should trigger an explicit fallback strategy.

## Hybrid Pipelines

Streaming regions may transition to other execution backends when required.

```text
Kafka
   │
   ▼
Spark Streaming
   │
   ▼
Validation
   │
   ▼
SQL Sink
```

Backend transitions should remain explicit in the `PipelinePlan`.

## Diagnostics

Streaming diagnostics should include:

- Query ID
- Application ID
- Watermark
- Trigger duration
- Input rows
- Output rows
- State size
- Checkpoint location
- Sink status

## Recovery

On restart, the runtime should recover from checkpoints whenever possible.

Recovery should preserve declared delivery guarantees.

## Testing

Recommended tests include:

- Watermark handling
- Late events
- Stateful aggregation
- Checkpoint recovery
- Trigger behavior
- Source and sink compatibility
- Contract validation
- Backend equivalence

## Best Practices

- Prefer event time over processing time.
- Keep contracts backend-independent.
- Configure reliable checkpoints.
- Make late-data behavior explicit.
- Test restart and recovery paths.
- Separate operational configuration from pipeline semantics.

## Anti-Patterns

Avoid:

- Relying on processing time for business correctness.
- Disabling checkpoints.
- Assuming every batch transformation is streaming-compatible.
- Ignoring late data.
- Embedding cluster configuration in pipeline definitions.

## Key Principle

> Structured Streaming extends ETLantic's execution model to unbounded
> datasets while preserving portable contracts, validation, lineage,
> diagnostics, and transformation semantics.

## Next Step

Continue with the [PySpark Plugin](../07_PLUGIN_SDK/PYSPARK_PLUGIN.md) guide to
implement Spark backends that support batch and Structured Streaming workloads.
