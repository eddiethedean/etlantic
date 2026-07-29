# Resource Providers

> **Status: planned design — not shipped in ETLantic 0.34.** Kubernetes and
> managed execution reference proof is assigned to 0.48; supported enterprise
> provider packs are assigned to 0.52. See the
> [Adoption, Connectivity, and Operations Plan](../11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md).

Resource providers give ETLantic access to runtime resources required
to execute a Pipeline Plan.

Unlike storage plugins, which persist data, resource providers expose reusable
services and infrastructure such as databases, secret managers, API clients,
message brokers, caches, and compute resources.

Resource providers allow transformations and execution plugins to request logical
resources without depending on vendor-specific SDKs.

## Goals

Resource providers should:

- Decouple pipelines from infrastructure.
- Provide typed resource interfaces.
- Support dependency injection.
- Be environment independent.
- Integrate with execution profiles.
- Expose capabilities during planning.

## Philosophy

Pipeline authors declare **what resource** they need.

Resource providers determine **how that resource is acquired**.

```text
Pipeline Plan
      │
      ▼
Resource Provider
      │
 ┌────┼───────────────┐
 ▼    ▼        ▼      ▼
SQL  Redis   Secrets  HTTP
```

## Responsibilities

Resource providers are responsible for:

- Resource discovery
- Authentication
- Connection management
- Lifecycle management
- Health checks
- Cleanup

They are not responsible for:

- Pipeline planning
- Transformation semantics
- Contract validation
- Orchestration

## Resource Types

Typical resources include:

- SQL databases
- Object stores
- Redis
- Kafka
- HTTP clients
- Secret managers
- ML model endpoints
- Vector databases
- Compute clusters

## Declaring Resources

Conceptually:

```python
class NormalizeCustomers(Transformation):
    warehouse: Resource[SqlDatabase]
```

The transformation depends on an abstract resource, not a concrete client.

## Profile Bindings

Profiles bind logical resources to physical implementations.

Development:

```text
warehouse -> SQLite
```

Production:

```text
warehouse -> PostgreSQL
```

The transformation remains unchanged.

## Lifecycle

Typical lifecycle:

```text
Resolve
   │
   ▼
Create
   │
   ▼
Inject
   │
   ▼
Use
   │
   ▼
Dispose
```

Execution plugins coordinate resource lifecycles.

## Async Support

Resources may expose synchronous or asynchronous interfaces.

ETLantic normalizes access so execution plugins invoke resources
consistently regardless of implementation style.

## Capabilities

Resource providers should publish capabilities such as:

- Transactions
- Connection pooling
- Async support
- Streaming
- Health monitoring
- Retry support

Planning can verify required capabilities before execution.

## Error Handling

Resource failures should produce structured diagnostics including:

- Resource identity
- Failure category
- Underlying exception
- Suggested remediation

## Best Practices

- Depend on abstract resources.
- Resolve resources through profiles.
- Keep credentials external.
- Reuse pooled resources.
- Dispose of resources cleanly.

## Anti-Patterns

Avoid:

- Creating SDK clients inside transformations.
- Hard-coding credentials.
- Passing global singleton resources.
- Coupling contracts to infrastructure APIs.

## Key Principle

> Resource providers supply infrastructure services to execution while keeping
pipeline models, contracts, and transformations independent of specific
deployment environments.

## Next Step

Continue with [Local Python](LOCAL_PYTHON.md) to see how resources, callbacks,
profiles, and runtime state are coordinated by the reference orchestrator.
