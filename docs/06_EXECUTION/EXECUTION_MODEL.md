# Execution Model

The execution model defines how a resolved `PipelinePlan` is realized while
preserving the observable semantics of the logical pipeline.

ETLantic coordinates execution through plugins. External libraries and
platforms perform reads, transformations, writes, scheduling, and distributed
computation.

## Lifecycle

```text
PipelinePlan
     │
     ▼
Orchestrator plugin or compiler
     │
     ├── Storage plugins
     ├── Dataframe / SQL / PySpark plugins
     ├── Resource providers
     └── Callback dispatch
     │
     ▼
External runtime
     │
     ▼
PipelineRunReport, diagnostics, events, and lineage
```

For portable steps, the planned implementation includes a portable IR
fingerprint and selected compiler. Compilation produces backend-native
expressions without placing live compiled objects in the serialized plan.

## Execution Responsibilities

ETLantic coordinates:

- Plan submission
- Logical identity propagation
- Common lifecycle states
- Sync and async invocation
- Callback policy
- Result normalization
- Diagnostics
- Cancellation and timeout intent

Plugins implement:

- Source reads
- Transformation execution
- Sink writes
- Runtime scheduling
- Resource acquisition
- Backend cancellation
- Artifact transfer
- Platform-specific observability
- Portable transformation compilation for capabilities they advertise

## Execution Units

A physical execution unit may represent:

- One logical step
- Several fused logical steps
- One source or sink operation
- An external job submission
- A compiled orchestrator task

Every physical unit must map back to the logical identities it realizes.

## State Model

The common state model should distinguish:

```text
pending
ready
running
succeeded
failed
retrying
skipped
cancelled
timed_out
abandoned
```

Plugins map backend-specific states into this model without discarding useful
backend metadata.

## Dependency and Concurrency Model

Execution order comes from the physical graph in the `PipelinePlan`.

Independent ready units may run concurrently within configured limits. The
runtime must respect:

- Dependency completion
- Resource scopes
- Backend concurrency limits
- Failure propagation
- Transaction boundaries
- Checkpoint and validation gates

Concurrency is not the same as CPU parallelism. Synchronous CPU-heavy Python
may require a process or external execution mode.

## Sync and Async Invocation

The framework is async-first internally:

```text
async def
    → awaited directly

def
    → managed worker thread by default

declared CPU-heavy callable
    → process or external mode

plugin-managed job
    → plugin submission and monitoring
```

Users should not configure event loops or thread pools for ordinary use.

The public API may expose:

```python
CustomerPipeline.run(profile="local")
await CustomerPipeline.arun(profile="local")
```

Calling `run()` from an active async context should produce a clear error
directing the user to `await arun()`.

## Runtime Data Artifacts

Physical units exchange runtime artifacts, not necessarily in-memory Python
objects.

Examples:

- Pandas or Polars dataframe
- Arrow table
- Database relation
- Parquet or Delta location
- Spark dataframe or table reference
- Opaque plugin-native handle

The planner validates artifact boundaries before execution where capabilities
allow it.

## Data Validation

Runtime validation occurs at configured boundaries:

- After a source read
- Before a transformation
- After a transformation
- Before a sink write

Invalid input data may be rejected, dropped, quarantined, partially accepted,
or treated as fatal according to declared policy.

Invalid output data normally indicates that an implementation violated its
declared output contract and should fail unless an explicit safe policy exists.

## Failure and Callback Model

Failures are categorized by stage:

```text
read
input_validation
transform
output_validation
write
resource
orchestrator
```

Callbacks receive typed context and may return declarative actions. The active
backend carries them out.

Retry decisions must account for idempotency, side effects, transaction scope,
and backend support.

## Resource Lifecycle

Resource providers may return:

- Ordinary values
- Sync context managers
- Async context managers
- Sync generator dependencies
- Async generator dependencies

The runtime coordinates acquisition and cleanup even when execution fails or is
cancelled.

## Cancellation and Timeouts

Cancellation behavior differs by mode:

- Async tasks can usually be cancelled cooperatively.
- Worker-thread operations may continue after cancellation.
- Processes require explicit termination policy.
- External jobs require plugin-specific cancellation.

Results must distinguish cancellation, timeout, failure, and abandonment.

## Observability

Execution should emit structured events with stable identities:

- Pipeline submitted, started, completed, failed
- Unit ready, started, completed, failed
- Retry scheduled
- Validation completed
- Artifact produced
- Resource acquired and released

Telemetry transports remain plugin or integration concerns. Lineage should
retain logical dataset and transformation identity even when physical units are
fused.

## Run Report

Every completed or partially completed run produces a structured
`PipelineRunReport`.

It contains:

- run identity, intent, profile, status, and timing
- normalized summary metrics
- one report for every logical step
- artifacts and previous-step result transfers
- validation and invalid-artifact outcomes
- retries and callback actions
- incremental state transitions
- diagnostics and recommendations
- links to external backend runs

The report is independent of its text, JSON, or HTML rendering. See
[Run Reports](RUN_REPORTS.md).

## Local and External Execution

The same plan may be:

- Executed directly by Local Python
- Compiled to Airflow
- Submitted to Spark
- Compiled into SQL
- Delegated to a remote execution service

The coordination mechanism changes; the logical contract does not.

## Backend Conformance

A backend is conformant only when it:

- Preserves dependencies and public outputs
- Implements required failure semantics
- Maps states accurately
- Retains logical identity
- Enforces required validation boundaries
- Reports unsupported capabilities during planning
- Cleans up resources
- Protects secrets

## Key Principle

> Execution is a realization of the `PipelinePlan`, not a reinterpretation of
> the Python pipeline. Backend freedom ends where portable semantics begin.

## Next Step

Continue with [Plugins](PLUGINS.md) to learn how backend implementations
participate in planning and execution.
