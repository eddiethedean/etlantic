# Async

ETLantic is asynchronous by design, but it strives to make asynchronous
execution nearly invisible to application developers.

Like FastAPI, ETLantic allows authors to write either synchronous (`def`)
or asynchronous (`async def`) code. The framework detects the implementation
style and invokes it correctly, allowing developers to focus on business logic
instead of concurrency primitives.

## Goals

ETLantic's async model should:

- Support both synchronous and asynchronous implementations.
- Hide event-loop management from users.
- Provide a consistent programming model.
- Enable efficient concurrent execution.
- Keep transformation contracts independent of execution strategy.

## Philosophy

Authors describe *what* a transformation does.

ETLantic decides *how* to invoke it.

```python
@NormalizeCustomers.implementation("polars")
def normalize(customers):
    ...
```

```python
@NormalizeCustomers.implementation("remote")
async def normalize(customers):
    ...
```

Both implementations satisfy the same transformation contract.

## Pipeline async execution

Use `Pipeline.arun()` when calling from code that already runs inside an event
loop (for example FastAPI handlers or notebook kernels). `Pipeline.run()` is
the synchronous entry point and refuses to block an active loop (`PMEXEC100`).

```python
import asyncio

from pipeline import SamplePipeline


async def main() -> None:
    report = await SamplePipeline.arun(profile="development")
    report.raise_for_errors()
    print(report.status)


asyncio.run(main())
```

Register async implementations with `@Transformation.implementation(...)` on an
`async def` function—the invocation layer awaits them automatically.

## Internal Execution Model

Conceptually:

```text
Transformation Contract
          │
          ▼
Execution Planner
          │
          ▼
Async Invocation Layer
          │
          ├── Sync implementation
          └── Async implementation
```

The invocation layer normalizes execution so callers do not need separate APIs.

## Async Callbacks

Callbacks follow the same pattern.

```python
@on_failure
def notify(context):
    ...
```

```python
@on_failure
async def notify(context):
    ...
```

ETLantic awaits asynchronous callbacks automatically.

## Resources

Execution plugins may expose asynchronous resources such as:

- Database connections
- Object storage clients
- HTTP clients
- Message queues

Profiles bind these resources to transformations without changing the
transformation contract.

## Concurrency

Execution plugins determine how work is parallelized.

Examples include:

- Task scheduling
- Thread pools
- Async I/O
- Distributed execution
- Vectorized dataframe operations

ETLantic plans execution but does not dictate a concurrency strategy.

## Cancellation

Long-running executions should support cooperative cancellation where the
selected execution backend allows it.

Cancellation should propagate through typed execution contexts and callbacks.

## Error Handling

Exceptions raised by synchronous and asynchronous implementations should be
translated into the same structured ETLantic diagnostics.

Users should not need separate error-handling paths.

## Best Practices

- Prefer `async def` for naturally asynchronous operations.
- Use `def` for CPU-bound or synchronous libraries.
- Let ETLantic manage invocation.
- Keep contracts independent of concurrency concerns.
- Avoid manual event-loop management.

## Anti-Patterns

Avoid:

- Calling `asyncio.run()` inside implementations.
- Mixing event-loop management with business logic.
- Writing separate transformation contracts for sync and async execution.
- Exposing backend-specific concurrency primitives in public APIs.

## Key Principle

> ETLantic treats synchronous and asynchronous implementations as
equivalent ways of satisfying the same transformation contract. Concurrency is
an execution concern, not a modeling concern.

## Next Step

Continue with [DTCS](DTCS.md) to learn how synchronous and asynchronous
implementations remain separate from portable transformation semantics.
