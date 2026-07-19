# Callbacks

!!! warning "Future design—not a ETLantic 0.14 API guide"
    This page is a design study. It may describe packages, commands, or
    interfaces beyond the shipped API surface. Prefer Current Capabilities,
    the runnable examples under `examples/`, the API reference, and the CLI
    reference for installable behavior.


This example demonstrates how ETLantic wires callback functions into a
typed pipeline for invalid data, source failures, transformation failures, sink
failures, retries, and final pipeline outcomes.

Callbacks are part of the execution policy around a pipeline. They observe or
respond to events without redefining the pipeline's core data contracts,
transformation semantics, or graph topology.

ETLantic supports both synchronous callbacks declared with `def` and
asynchronous callbacks declared with `async def`. The framework invokes each
callback correctly without requiring users to manage event loops, threads, or
worker pools manually.

## Goal

Build a pipeline that:

1. Reads customer data from CSV.
2. Normalizes valid customer records.
3. Routes invalid records to a quarantine sink.
4. Invokes callbacks for:
   - Invalid input data
   - Source read failures
   - Transformation failures
   - Sink write failures
   - Retries
   - Successful completion
   - Final pipeline failure
5. Supports both sync and async callbacks.
6. Preserves structured diagnostics and callback ordering.
7. Generates ODCS, DTCS, and DPCS artifacts.

## Architecture

```text
CSV Source
    │
    ▼
Input Validation
    │
    ├── valid ───────► NormalizeCustomers
    │                       │
    │                       ▼
    │                  Customer Sink
    │
    └── invalid ─────► Quarantine Sink

Execution events
    │
    ├── on_invalid_data
    ├── on_read_failure
    ├── on_transformation_failure
    ├── on_write_failure
    ├── on_retry
    ├── on_success
    └── on_failure
```

## Project Structure

```text
callbacks/
├── pyproject.toml
├── data/
│   └── customers.csv
├── output/
│   ├── curated/
│   └── quarantine/
├── src/
│   └── callbacks_example/
│       ├── __init__.py
│       ├── contracts.py
│       ├── transformations.py
│       ├── implementations.py
│       ├── callbacks.py
│       ├── pipeline.py
│       └── profiles.py
├── contracts/
├── docs/
└── tests/
    ├── test_callbacks.py
    └── test_failure_paths.py
```

## Step 1 — Define the Data Contracts

```python
# src/callbacks_example/contracts.py

from typing import Annotated, Literal

from pydantic import Field

from etlantic import DataContractModel


class RawCustomer(DataContractModel):
    customer_id: int
    first_name: str
    last_name: str
    email: str | None


class Customer(DataContractModel):
    customer_id: Annotated[
        int,
        Field(strict=True, gt=0),
    ]
    full_name: str
    email: str


class RejectedCustomer(DataContractModel):
    customer_id: int
    first_name: str
    last_name: str
    email: str | None

    reason_code: Literal[
        "INVALID_CUSTOMER_ID",
        "MISSING_EMAIL",
    ]
    reason: str
```

## Step 2 — Define the Transformation

```python
# src/callbacks_example/transformations.py

from etlantic import Input, Output, Transformation

from .contracts import Customer, RawCustomer


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]
```

## Step 3 — Add the Implementation

```python
# src/callbacks_example/implementations.py

import polars as pl

from .transformations import NormalizeCustomers


@NormalizeCustomers.implementation("polars")
def normalize_customers(
    customers: pl.LazyFrame,
) -> pl.LazyFrame:
    return customers.select(
        pl.col("customer_id"),
        pl.concat_str(
            [
                pl.col("first_name").str.strip_chars(),
                pl.col("last_name").str.strip_chars(),
            ],
            separator=" ",
        ).alias("full_name"),
        pl.col("email")
        .str.strip_chars()
        .str.to_lowercase()
        .alias("email"),
    )
```

## Step 4 — Understand Callback Contexts

Every callback should receive a typed context object appropriate to its event.

Conceptually:

```python
InvalidDataContext
ReadFailureContext
TransformationFailureContext
WriteFailureContext
RetryContext
PipelineSuccessContext
PipelineFailureContext
```

These contexts should expose structured fields rather than requiring users to
parse strings or backend-specific exceptions.

## Common Context Fields

Most callback contexts should include:

- Pipeline identity
- Pipeline version
- Run identity
- Step identity
- Attempt number
- Execution profile
- Diagnostic code
- Failure category
- Timestamp
- Structured metadata
- Redacted backend details

## Step 5 — Define an Invalid-Data Callback

A synchronous invalid-data callback:

```python
# src/callbacks_example/callbacks.py

from etlantic.callbacks import InvalidDataContext


def record_invalid_customer(
    context: InvalidDataContext,
) -> None:
    print(
        f"Rejected {context.invalid_count} customer records "
        f"at step {context.step_id}"
    )
```

This callback observes the invalid-data event.

It does not decide whether invalid records are accepted unless the callback API
explicitly supports returning an action.

## Action-Returning Callback

Some callbacks may return a typed action.

```python
from etlantic.callbacks import (
    InvalidDataAction,
    InvalidDataContext,
)


def handle_invalid_customers(
    context: InvalidDataContext,
) -> InvalidDataAction:
    if context.invalid_count == 0:
        return InvalidDataAction.continue_()

    return InvalidDataAction.quarantine(
        binding="customer_quarantine",
    )
```

Typed actions are safer than returning strings such as `"continue"` or
`"quarantine"`.

## Step 6 — Define an Async Notification Callback

```python
from etlantic.callbacks import WriteFailureContext


async def notify_write_failure(
    context: WriteFailureContext,
) -> None:
    await context.notifications.send(
        channel="data-operations",
        message=(
            f"Write failed for pipeline {context.pipeline_id}, "
            f"sink {context.sink_id}, "
            f"diagnostic {context.diagnostic_code}"
        ),
    )
```

ETLantic detects `async def` automatically and awaits it.

The user does not manage an event loop.

## Step 7 — Define a Retry Callback

```python
from etlantic.callbacks import RetryContext


def log_retry(
    context: RetryContext,
) -> None:
    print(
        f"Retrying {context.step_id}: "
        f"attempt {context.next_attempt} of "
        f"{context.maximum_attempts}"
    )
```

A retry callback should observe a retry decision that has already been made by
the execution policy.

It should not mutate the attempt counter or sleep manually.

## Step 8 — Define a Transformation Failure Callback

```python
from etlantic.callbacks import (
    FailureAction,
    TransformationFailureContext,
)


async def handle_transformation_failure(
    context: TransformationFailureContext,
) -> FailureAction:
    await context.notifications.send(
        channel="pipeline-alerts",
        message=(
            f"Transformation {context.transformation_id} failed "
            f"with {context.failure_category}"
        ),
    )

    if context.retryable:
        return FailureAction.retry()

    return FailureAction.fail()
```

The action must still be compatible with:

- Retry limits
- Idempotency
- Orchestrator capabilities
- Failure policy
- Sink semantics

A callback cannot force an unsafe retry.

## Step 9 — Define a Read Failure Callback

```python
from etlantic.callbacks import (
    FailureAction,
    ReadFailureContext,
)


def handle_source_failure(
    context: ReadFailureContext,
) -> FailureAction:
    if context.failure_category == "transient-network":
        return FailureAction.retry()

    return FailureAction.fail()
```

The execution layer validates the returned action against the active policy.

## Step 10 — Define Pipeline Outcome Callbacks

```python
from etlantic.callbacks import (
    PipelineFailureContext,
    PipelineSuccessContext,
)


async def report_pipeline_success(
    context: PipelineSuccessContext,
) -> None:
    await context.metrics.publish(
        "pipeline.completed",
        tags={
            "pipeline": context.pipeline_id,
            "profile": context.profile_name,
        },
    )


async def report_pipeline_failure(
    context: PipelineFailureContext,
) -> None:
    await context.notifications.send(
        channel="pipeline-alerts",
        message=(
            f"Pipeline {context.pipeline_id} failed "
            f"after {context.duration_seconds} seconds"
        ),
    )
```

## Step 11 — Define the Pipeline

```python
# src/callbacks_example/pipeline.py

from etlantic import Pipeline, Sink, Source

from .callbacks import (
    handle_invalid_customers,
    handle_source_failure,
    handle_transformation_failure,
    log_retry,
    notify_write_failure,
    report_pipeline_failure,
    report_pipeline_success,
)
from .contracts import Customer, RawCustomer, RejectedCustomer
from .transformations import NormalizeCustomers


class CustomerCallbackPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(
        binding="customers_input",
        on_read_failure=handle_source_failure,
        on_invalid_data=handle_invalid_customers,
    )

    normalized = NormalizeCustomers.step(
        customers=raw.valid,
        on_failure=handle_transformation_failure,
        on_retry=log_retry,
    )

    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customers_output",
        on_write_failure=notify_write_failure,
    )

    quarantine: Sink[RejectedCustomer] = Sink(
        input=raw.invalid,
        binding="customer_quarantine",
    )

    callbacks = {
        "on_success": report_pipeline_success,
        "on_failure": report_pipeline_failure,
    }
```

The exact declaration API may evolve.

The important design goals are:

- Callback attachment is explicit.
- Callback signatures are typed.
- Sync and async callbacks use the same registration model.
- Data flow remains distinct from callback flow.
- Invalid records are first-class data, not hidden callback arguments.

## Step 12 — Define the Profile

```python
# src/callbacks_example/profiles.py

from etlantic import Profile


local = Profile(
    name="local",
    orchestrator="local-python",
    dataframe_engine="polars",
    execution={
        "maximum_attempts": 3,
        "retry_delay_seconds": 2,
        "callback_failure_policy": "fail-closed",
    },
    bindings={
        "customers_input": {
            "plugin": "csv",
            "path": "data/customers.csv",
            "lazy": True,
        },
        "customers_output": {
            "plugin": "parquet",
            "path": "output/curated/",
            "write_mode": "overwrite",
        },
        "customer_quarantine": {
            "plugin": "parquet",
            "path": "output/quarantine/",
            "write_mode": "overwrite",
        },
    },
    resources={
        "notifications": {
            "provider": "console-notifications",
        },
        "metrics": {
            "provider": "in-memory-metrics",
        },
    },
)
```

Callbacks may receive resources through the callback context.

They should not construct infrastructure clients directly.

## Callback Resource Injection

ETLantic may inject typed resources:

```python
async def notify_write_failure(
    context: WriteFailureContext,
    notifier: Resource[NotificationClient],
) -> None:
    await notifier.send(...)
```

This mirrors the framework's general dependency-injection philosophy.

## Step 13 — Validate the Pipeline

```python
from callbacks_example.pipeline import CustomerCallbackPipeline


report = CustomerCallbackPipeline.validate()
report.raise_for_errors()
```

Validation should verify:

- Callback signatures are supported.
- Required context types match the event.
- Returned action types are valid.
- Async callbacks are accepted.
- Callback resources resolve.
- Callback event names are valid.
- The invalid-data branch satisfies its sink contract.

## Invalid Callback Signature

This should fail validation:

```python
def bad_callback(
    message: str,
    count: int,
) -> None:
    ...
```

The framework cannot reliably infer how to populate arbitrary parameters.

## Valid Dependency-Injected Signature

```python
async def valid_callback(
    context: WriteFailureContext,
    notifier: Resource[NotificationClient],
) -> None:
    ...
```

The framework can resolve both parameters through type annotations.

## Step 14 — Build the Pipeline Plan

```python
from callbacks_example.profiles import local


plan = CustomerCallbackPipeline.plan(
    profile=local,
)
```

The plan should include callback bindings as execution metadata.

Conceptually:

```text
read-customers
    ├── on_read_failure: handle_source_failure
    └── on_invalid_data: handle_invalid_customers

normalize-customers
    ├── on_failure: handle_transformation_failure
    └── on_retry: log_retry

write-customers
    └── on_write_failure: notify_write_failure

pipeline
    ├── on_success: report_pipeline_success
    └── on_failure: report_pipeline_failure
```

## Step 15 — Execute

```python
result = CustomerCallbackPipeline.run(
    profile=local,
)
```

Asynchronous execution:

```python
result = await CustomerCallbackPipeline.arun(
    profile=local,
)
```

Both paths invoke sync and async callbacks correctly.

## Sync and Async Invocation

Conceptually, the execution layer determines:

```text
Callback declared with def
        │
        ▼
Invoke through supported sync strategy

Callback declared with async def
        │
        ▼
Await directly
```

Users should never need to write:

```python
asyncio.run(callback(...))
```

inside pipeline code.

## Callback Ordering

A deterministic event order should be defined.

For a failed transformation with retry:

```text
Transformation attempt starts
        │
        ▼
Transformation fails
        │
        ▼
Failure classified
        │
        ▼
on_failure callback
        │
        ▼
Retry decision validated
        │
        ▼
on_retry callback
        │
        ▼
Next attempt starts
```

Pipeline outcome callbacks run only after the pipeline reaches a terminal state.

## Before and After Callbacks

ETLantic may support lifecycle callbacks such as:

- `before_pipeline`
- `after_pipeline`
- `before_step`
- `after_step`
- `before_read`
- `after_read`
- `before_write`
- `after_write`

These callbacks should observe execution rather than replace the operation.

## Event-Specific Callbacks

Recommended event categories include:

### Pipeline

- `on_start`
- `on_success`
- `on_failure`
- `on_cancel`

### Source

- `before_read`
- `after_read`
- `on_read_failure`
- `on_invalid_data`

### Transformation

- `before_transform`
- `after_transform`
- `on_failure`
- `on_retry`

### Sink

- `before_write`
- `after_write`
- `on_write_failure`

### Validation

- `on_validation_failure`
- `on_quarantine`
- `on_quality_gate_failure`

## Callback Return Values

Observer callbacks return `None`.

Decision callbacks return typed actions.

Examples:

```python
None
FailureAction
InvalidDataAction
QualityGateAction
```

Arbitrary booleans or strings should not be accepted.

## Callback Failure Policy

Callbacks may fail too.

Possible policies include:

- `fail-closed`
- `fail-open`
- `warn`
- `retry-callback`

### Fail closed

The callback failure causes the related step or pipeline to fail.

Use when the callback is part of a required governance process.

### Fail open

Execution continues and records a callback diagnostic.

Use only when the callback is non-critical.

### Warn

Execution continues with a warning.

### Retry callback

Retry only the callback when safe and supported.

The profile should define callback failure behavior explicitly.

## Callback Isolation

Callbacks should not receive mutable access to internal execution state.

Contexts should expose:

- Immutable metadata
- Typed actions
- Approved resources
- Read-only diagnostics
- Controlled artifact references

Callbacks should not be able to rewrite the Pipeline Plan.

## Callback Timeouts

Profiles may configure callback timeouts:

```python
execution={
    "callback_timeout_seconds": 30,
}
```

A timed-out callback should produce a structured diagnostic.

## Callback Concurrency

Callbacks for independent branches may run concurrently when the execution model
allows it.

Ordering guarantees should apply only where declared.

## Idempotency

Callbacks may run more than once because of retries, orchestrator replays, or
worker recovery.

Side-effecting callbacks should use:

- Stable event identities
- Idempotency keys
- Deduplication
- Upsert semantics
- At-least-once-safe behavior

Conceptually:

```python
context.event_id
```

may serve as an idempotency key.

## Callback Event Identity

A stable event identity may derive from:

- Pipeline run identity
- Step identity
- Event type
- Attempt number
- Output identity

This helps external systems deduplicate callback effects.

## Retrying Callbacks

A callback retry should not imply retrying the transformation.

These are separate decisions:

```text
Transformation succeeded
      │
      ▼
Success callback failed
      │
      ├── retry callback only
      └── fail or warn according to policy
```

## Orchestrator Mapping

Orchestration plugins may map callbacks to native mechanisms.

For Airflow:

- Task callbacks
- DAG callbacks
- Retry callbacks

For Local Python:

- Direct invocation

For remote Spark:

- Driver-side event handling
- External event relay

The observable callback semantics should remain portable.

## Callback Portability

Not every backend supports every callback timing guarantee.

Plugins should declare capabilities such as:

- Pre-step callbacks
- Post-step callbacks
- Retry callbacks
- Cancellation callbacks
- Streaming callbacks
- Output-specific callbacks

Planning should fail when a mandatory callback cannot be preserved.

## Streaming Callbacks

Streaming callbacks require special care.

Possible events include:

- Query started
- Micro-batch completed
- Watermark advanced
- Streaming query failed
- Query terminated

Per-record callbacks should generally be avoided for high-volume streams.

Use typed side outputs or metrics instead.

## Invalid Data Is Still Data

Callbacks should not replace typed invalid-data outputs.

Prefer:

```text
invalid rows ───► RejectedCustomer sink
```

with a callback that reports the event.

Avoid passing complete rejected datasets into notification callbacks.

## Large Callback Payloads

Callback contexts should use references for large artifacts.

Prefer:

```python
context.invalid_data_reference
```

instead of embedding millions of rows.

## Security

Callbacks should follow secure defaults:

- Secrets injected through Resource Providers
- Sensitive values redacted
- No complete row dumps in diagnostics
- No arbitrary code from contract files
- Restricted callback imports
- Controlled network access where required
- Stable audit identities

## Diagnostics

A callback diagnostic should identify:

- Pipeline
- Step
- Event
- Callback identity
- Attempt
- Failure category
- Timeout status
- Returned action
- Backend mapping
- Suggested remediation

Example:

```text
PMCALLBACK204

Pipeline: customer-callback-pipeline
Step: write-customers
Event: on_write_failure
Callback: notify_write_failure

The callback exceeded its 30-second timeout.
The callback failure policy is "warn", so pipeline failure handling continued.
```

## Observability

ETLantic should emit callback events such as:

- Callback scheduled
- Callback started
- Callback completed
- Callback failed
- Callback timed out
- Callback retried
- Callback action accepted
- Callback action rejected

## Step 16 — Test Callback Invocation

```python
def test_invalid_data_callback_is_called(
    callback_recorder,
    invalid_input_profile,
) -> None:
    CustomerCallbackPipeline.run(
        profile=invalid_input_profile,
    )

    assert callback_recorder.events == [
        "on_invalid_data",
        "on_success",
    ]
```

## Test Async Callback Invocation

```python
async def test_async_write_failure_callback(
    async_callback_recorder,
    failing_sink_profile,
) -> None:
    result = await CustomerCallbackPipeline.arun(
        profile=failing_sink_profile,
        raise_on_failure=False,
    )

    assert not result.success
    assert async_callback_recorder.was_awaited(
        "on_write_failure"
    )
```

## Test Retry Ordering

```python
def test_retry_callback_order(
    callback_recorder,
    transient_failure_profile,
) -> None:
    CustomerCallbackPipeline.run(
        profile=transient_failure_profile,
    )

    assert callback_recorder.events == [
        "on_failure",
        "on_retry",
        "on_success",
    ]
```

## Test Unsafe Retry Rejection

```python
def test_unsafe_retry_action_is_rejected(
    non_idempotent_sink_profile,
) -> None:
    result = CustomerCallbackPipeline.run(
        profile=non_idempotent_sink_profile,
        raise_on_failure=False,
    )

    assert result.has_diagnostic(
        "PMCALLBACK_RETRY_UNSAFE",
    )
```

## Test Callback Failure Policy

```python
def test_noncritical_callback_failure_warns(
    failing_metrics_callback_profile,
) -> None:
    result = CustomerCallbackPipeline.run(
        profile=failing_metrics_callback_profile,
    )

    assert result.success
    assert result.has_warning(
        "PMCALLBACK204",
    )
```

## Generate Contracts

```python
CustomerCallbackPipeline.write_contracts(
    "contracts/",
)
```

Callbacks that affect portable execution semantics may appear in DPCS as
references or declared policies.

Environment-specific callback implementation details should remain outside the
portable contract.

## Generate Documentation

```python
plan.write_html(
    "docs/customer-callback-pipeline.html",
    self_contained=True,
)
```

Documentation should include:

- Registered callback events
- Callback identities
- Sync or async classification
- Required resources
- Returned action types
- Failure policy
- Timeout
- Portability requirements
- Security and redaction behavior

## Generate Mermaid

```python
plan.write_mermaid(
    "docs/customer-callback-pipeline.mmd",
)
```

The primary diagram should show data flow.

Callback flow may appear in a separate event diagram to avoid confusing control
events with datasets.

## Best Practices

- Type every callback context.
- Use typed actions for decisions.
- Keep callback registration explicit.
- Let ETLantic invoke sync and async callbacks.
- Inject infrastructure through Resource Providers.
- Keep invalid data in typed outputs.
- Use stable event IDs for idempotency.
- Define callback timeout and failure policies.
- Keep callbacks small and focused.
- Test failure paths and ordering.
- Avoid passing large datasets into callbacks.
- Preserve portability requirements in planning.

## Anti-Patterns

Avoid:

- Calling `asyncio.run()` inside callbacks.
- Returning arbitrary strings or booleans.
- Mutating Pipeline Plans from callbacks.
- Creating SDK clients directly inside callback functions.
- Using callbacks as the only record of invalid data.
- Sending large datasets through callback payloads.
- Assuming callbacks execute exactly once.
- Retrying non-idempotent side effects blindly.
- Hiding required governance callbacks as optional notifications.
- Allowing callback failures to disappear silently.

## Key Principle

> Callbacks extend ETLantic's execution lifecycle with typed, observable,
> sync-or-async behavior while leaving pipeline data flow, contracts, and
> transformation semantics unchanged.

## Next Step

Continue with [Async Pipelines](ASYNC_PIPELINES.md) to combine synchronous and
asynchronous sources, transformations, resources, callbacks, and sinks.
