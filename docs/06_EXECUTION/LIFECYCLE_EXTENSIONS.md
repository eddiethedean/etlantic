# Lifecycle Extension Mechanisms

!!! warning "Design study—not a runnable ETLantic 0.18 API guide. Prefer CAPABILITIES and examples/."
    Parts of this chapter describe intended lifespan / middleware / resource
    injection surfaces that are not fully shipped. Prefer
    [Callbacks](../04_TRANSFORMATIONS/CALLBACKS.md), run reports, and the
    local runtime APIs documented in the
    [API reference](../10_REFERENCE/API_REFERENCE.md) for 0.18 applications.

ETLantic provides four distinct mechanisms for inserting reusable behavior
at well-defined points in modeling and execution:

1. Runtime lifespan
2. Execution middleware
3. Resource injection
4. Lifecycle callbacks and outbound event declarations

These mechanisms are inspired by FastAPI's separation of lifespan,
middleware, dependencies, and OpenAPI callbacks or webhooks. ETLantic
adopts the architectural distinction, not the HTTP terminology or request
model.

## Why Separate Mechanisms?

A single universal hook system would be convenient initially but difficult to
reason about later.

Each mechanism answers a different question:

| Mechanism | Question |
|---|---|
| Lifespan | What must be initialized once and cleaned up once? |
| Middleware | What behavior wraps every selected run or step invocation? |
| Resource injection | What typed service does this callable require? |
| Callback | How should the framework respond to a lifecycle outcome? |
| Outbound event declaration | What external notification can this pipeline emit? |

The mechanisms should not be interchangeable.

## 1. Runtime Lifespan

A lifespan is an async context manager surrounding a runtime session.

```python
from contextlib import asynccontextmanager

from etlantic import PipelineRuntime


@asynccontextmanager
async def lifespan(runtime: PipelineRuntime):
    await warm_contract_cache()
    yield
    await flush_observability()


runtime = PipelineRuntime(lifespan=lifespan)
```

Code before `yield` runs before the runtime accepts pipeline runs. Code after
`yield` runs during shutdown after active work has completed or been cancelled.

### Appropriate uses

- initialize shared plugin registries
- warm immutable metadata or contract caches
- open shared pools through providers
- start observability exporters
- verify environment health
- flush and close shared services

### Scopes

ETLantic should support explicit scopes:

```text
Runtime lifespan
    Once for a PipelineRuntime instance.

Run lifespan
    Once around one pipeline run.

Execution-region lifespan
    Optional plugin-managed scope around a physical execution region.
```

Step-scoped resources normally use resource injection rather than a custom
lifespan.

### Composition

Multiple lifespan components should compose through an async exit stack.
Initialization occurs in registration order; cleanup occurs in reverse order.
Partially initialized lifespans must still clean up successfully acquired
resources.

## 2. Execution Middleware

Middleware wraps a run or step invocation before and after the delegated
operation:

```python
async def timing_middleware(context, call_next):
    started = monotonic()
    try:
        return await call_next(context)
    finally:
        context.metrics.observe(
            "execution.duration",
            monotonic() - started,
        )
```

Registration is explicit:

```python
runtime.add_run_middleware(timing_middleware)
runtime.add_step_middleware(tracing_middleware)
```

### Appropriate uses

- structured logging
- tracing
- timing and metrics
- policy enforcement
- context propagation
- bounded rate limiting
- exception normalization

### Scopes

ETLantic should distinguish:

```text
Run middleware
    Wraps an entire pipeline run.

Step middleware
    Wraps each logical step invocation.

Provider middleware
    Optional SDK mechanism around provider acquisition.
```

Physical backend operations remain plugin concerns. Core middleware observes
logical operations and must preserve their identities.

### Ordering

Middleware forms a stack:

```text
outer.before
    inner.before
        operation
    inner.after
outer.after
```

The ordering must be deterministic and visible through inspection.

### Restrictions

Middleware must not:

- mutate the logical pipeline graph
- silently replace input or output contracts
- hide mandatory failures
- acquire undeclared resources
- change plan identity after planning
- consume or duplicate large artifacts merely for inspection

Middleware may reject an operation through a structured policy result.
Transformation or artifact replacement requires an explicit, separately
planned extension point.

## 3. Resource Injection

FastAPI calls this dependency injection. ETLantic uses the term resource
injection to avoid confusion with edges in the pipeline dependency graph.

Transformation implementations and callbacks declare typed requirements:

```python
from typing import Annotated

from etlantic import Inject, Resource

Warehouse = Annotated[SqlDatabase, Inject("warehouse")]


@NormalizeCustomers.implementation("python")
async def normalize_customers(
    customers,
    warehouse: Warehouse,
):
    ...
```

ETLantic resolves the requirement through the selected profile and
resource provider.

### Hierarchical providers

Resources may depend on other resources:

```text
CustomerRepository
        ↓
DatabaseSession
        ↓
DatabaseEngine
        ↓
Secret reference
```

The resolver builds and validates a resource graph independently from the
pipeline data-flow graph.

### Yield-based cleanup

Provider functions may use `yield` or async context managers:

```python
async def provide_session(engine: DatabaseEngine):
    async with engine.session() as session:
        yield session
```

The value is injected before invocation and cleaned up after invocation,
including failure and cancellation paths.

### Scopes

```text
runtime
run
execution_region
step
attempt
```

Caching occurs only within the declared scope. Retry behavior must not reuse a
resource whose scope or safety policy forbids reuse.

### Overrides

Tests and local debugging need explicit overrides:

```python
runtime.override_resource(
    "warehouse",
    provider=provide_test_database,
)
```

Overrides are runtime configuration. They do not alter the portable pipeline
contract.

## 4. Lifecycle Callbacks

Callbacks respond to specific outcomes:

```python
@pipeline.on_step_failed
async def notify_failure(context: StepFailureContext) -> FailureAction:
    return FailureAction.fail()
```

Callbacks differ from middleware:

- middleware wraps every matching operation
- callbacks run only for declared lifecycle events
- callbacks may return declarative action objects
- callbacks do not control arbitrary continuation

Common callback points include:

```text
run_planned
run_started
run_completed
run_failed
step_started
step_completed
step_failed
validation_failed
artifact_materialized
state_committed
```

Callbacks are operational policy, not transformation logic.

## 5. Outbound Event Declarations

FastAPI's OpenAPI callbacks and webhooks primarily document requests an
application may send to another system. The ETLantic equivalent is a
typed outbound event declaration.

```python
class CustomerPipeline(Pipeline):
    customer_published = OutboundEvent[CustomerPublished](
        event="customer.published",
        delivery="customer_events",
    )
```

An event may be emitted by a callback:

```python
@CustomerPipeline.on_complete
def publish_completion(context):
    return Emit(
        CustomerPipeline.customer_published,
        CustomerPublished(
            pipeline_id=context.pipeline_id,
            run_id=context.run_id,
        ),
    )
```

The profile binds `customer_events` to an implementation:

```text
HTTP webhook
Kafka topic
cloud event bus
message queue
local test capture
```

### What ETLantic owns

- event name and payload type
- lifecycle association
- delivery requirements
- documentation metadata
- planning and capability validation
- normalized delivery results

### What providers own

- endpoint or topic resolution
- authentication
- serialization and transport
- retry and dead-letter behavior
- delivery receipts

### Not a fourth contract family

Outbound events are pipeline interface metadata and runtime configuration. They
do not create another top-level contract standard alongside ODCS, DTCS, and
DPCS.

HTTP-specific webhook descriptions may be generated from outbound event
declarations through a documentation plugin. The ETLantic core remains
transport-neutral.

## Selection Guide

Use:

- **lifespan** for once-per-scope setup and cleanup
- **middleware** for behavior surrounding every matching invocation
- **resource injection** for typed services required by a callable
- **callbacks** for outcome-specific operational policy
- **outbound events** for documented notifications to external consumers

## Combined Example

```python
runtime = PipelineRuntime(lifespan=project_lifespan)
runtime.add_run_middleware(logging_middleware)
runtime.add_step_middleware(tracing_middleware)


@NormalizeCustomers.implementation("python")
async def normalize(
    customers,
    warehouse: Annotated[SqlDatabase, Inject("warehouse")],
):
    ...


@CustomerPipeline.on_failure
async def report_failure(context):
    return Emit(CustomerPipeline.pipeline_failed, context.to_event())
```

Every mechanism remains independently inspectable, testable, and configurable.

## Key Principle

> Setup and cleanup belong to lifespan. Cross-cutting wrappers belong to
> middleware. Required services belong to resource injection. Outcome policy
> belongs to callbacks. External notifications belong to typed outbound event
> declarations.

## See Also

- [Callbacks](../04_TRANSFORMATIONS/CALLBACKS.md)
- [Resource Provider](../07_PLUGIN_SDK/RESOURCE_PROVIDER.md)
- [Logging](LOGGING.md)
- [Execution Model](EXECUTION_MODEL.md)
