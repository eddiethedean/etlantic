# Resource Provider

!!! warning "Future design—not a shipped 0.33 entry-point protocol"
    Resource providers are not a discoverable entry-point protocol in
    ETLantic 0.33. This page describes a proposed extension surface. Prefer
    the shipped dataframe / SQL / Spark / orchestration / secrets plugin
    categories for current work.

A **Resource Provider** implements the ETLantic Resource Provider API,
supplying runtime infrastructure services to execution plugins and
transformations.

Unlike storage plugins, which persist datasets, resource providers expose
operational services such as database connections, secret managers, HTTP
clients, caches, message brokers, ML endpoints, and compute resources.

Pipeline authors declare logical resource requirements. Resource providers
resolve those requirements into concrete runtime objects.

This is ETLantic's dependency-injection mechanism. The term resource
injection is preferred so it cannot be confused with pipeline graph
dependencies.

## Purpose

A resource provider is responsible for:

- Resolving logical resources
- Creating resource instances
- Managing authentication
- Managing lifecycle
- Pooling and reuse
- Health checks
- Structured diagnostics

It is **not** responsible for:

- Pipeline planning
- Pipeline orchestration
- Transformation semantics
- Data persistence
- Contract generation

## Architecture

```text
Pipeline Plan
      │
      ▼
Resource Provider API
      │
 ┌────┼───────────────────────────────┐
 ▼    ▼          ▼         ▼          ▼
SQL  Secrets    Redis     HTTP     Kafka
```

Resource providers supply services to other plugins while remaining independent
of the pipeline model.

## Declaring Resources

Conceptually:

```python
class NormalizeCustomers(Transformation):
    warehouse: Resource[SqlDatabase]
    cache: Resource[Redis]
```

The transformation depends on abstract resource types rather than vendor SDKs.

## Resolution

Execution profiles bind logical resources to implementations.

Development:

```text
warehouse -> SQLite
```

Production:

```text
warehouse -> PostgreSQL
```

No pipeline code changes are required.

An annotation-oriented form may also be used by implementation callables:

```python
from typing import Annotated

from etlantic.lifecycle import Inject

Warehouse = Annotated[SqlDatabase, Inject("warehouse")]


@NormalizeCustomers.implementation("python")
async def normalize(customers, warehouse: Warehouse):
    ...
```

## Provider Interface

Conceptually:

```python
class ResourceProvider:
    name: str
    version: str

    def resolve(self, resource_type, binding, context):
        ...
```

Providers may expose richer APIs, but all should resolve logical resources into
usable runtime objects.

## Lifecycle

Typical lifecycle:

```text
Discover
   │
Resolve
   │
Create
   │
Inject
   │
Use
   │
Dispose
```

Providers should clean up resources deterministically.

Provider acquisition may use `yield` or an async context manager so setup and
cleanup remain paired:

```python
async def provide_session(engine: DatabaseEngine):
    async with engine.session() as session:
        yield session
```

## Resource Graph

Providers may depend on other providers. ETLantic builds a resource graph
separate from the pipeline data-flow graph, validates cycles, resolves shared
sub-dependencies once per declared scope, and injects the final value.

## Scopes

Supported scopes should include:

- runtime
- run
- execution region
- step
- attempt

Resources are cached only within their declared scope.

## Overrides

Tests and debug sessions may replace a provider explicitly:

```python
runtime.override_resource(
    "warehouse",
    provider=provide_test_database,
)
```

Overrides affect runtime binding, not [ODCS](../03_DATA_CONTRACTS/ODCS.md), [DTCS](../04_TRANSFORMATIONS/DTCS.md), [DPCS](../05_PIPELINES/DPCS.md), or the logical pipeline
graph.

## Async Support

Providers should support both synchronous and asynchronous acquisition where
appropriate.

ETLantic normalizes invocation so users do not manage event loops or
resource wiring.

## Capabilities

Providers should advertise capabilities such as:

- Async support
- Connection pooling
- Transactions
- Health monitoring
- Retry support
- Streaming
- High availability

Planning validates mandatory capabilities before execution.

## Error Handling

Providers should translate infrastructure-specific exceptions into structured
ETLantic diagnostics containing:

- Resource identity
- Pipeline identity
- Step identity
- Provider details
- Original exception
- Suggested remediation

## Best Practices

- Depend on abstract resource types.
- Resolve resources through execution profiles.
- Keep credentials external and accept resolved values only from declared
  [Secret Providers](SECRET_PROVIDER.md).
- Reuse pooled resources.
- Dispose of resources predictably.

## Anti-Patterns

Avoid:

- Creating SDK clients directly inside transformations.
- Hard-coding credentials.
- Using global mutable singletons.
- Exposing provider-specific objects through public contracts.

## Key Principle

> A Resource Provider supplies runtime infrastructure services while keeping
> pipelines, transformations, and contracts independent of deployment
> environments and vendor SDKs.

## Next Step

Continue with [Testing Plugins](TESTING_PLUGINS.md) to learn how providers and
plugins prove lifecycle, capability, and failure behavior.
