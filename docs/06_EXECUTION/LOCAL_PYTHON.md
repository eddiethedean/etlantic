# Local Python

> **Status: Available in Pipelantic 0.6.0.** Process-local execution of a
> `PipelinePlan` with registered Python and dataframe implementations.

The local runtime executes validated **Pipeline Plans** in-process. It is the
reference execution environment for development, testing, experimentation, and
CI.

It is **not** a multi-tenant production orchestrator. Prefer an external
scheduler (future Airflow/orchestration plugins) when you need durable
scheduling, cross-process isolation, or fleet-scale coordination.

## Known limitations (0.5)

- Run reports and the default report store are process-scoped
- In-memory storage does not survive process restart
- No multi-tenant artifact isolation between concurrent apps in one process
- Alpha: APIs may change in 0.x releases

## Goals

The local runtime should:

- Execute Pipeline Plans without external infrastructure
- Preserve DPCS semantics
- Support synchronous and asynchronous implementations
- Provide deterministic execution for a given plan and bindings
- Serve as the reference execution backend
- Enable rapid local development

## Philosophy

Local execution should never bypass the Pipelantic lifecycle.

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
Pipeline Plan
    │
    ▼
Local runtime
```

Unlike orchestration platforms, Local Python requires no external scheduler. It
executes the same Pipeline Plan while preserving identical pipeline semantics.

The only difference between local execution and orchestration is the execution
plugin.

## Why Local Execution?

Local execution is useful for:

- Unit testing
- Integration testing
- Interactive development
- Jupyter notebooks
- Command-line tools
- CI pipelines

Developers can validate pipeline behavior before deploying to larger execution
platforms.

## Execution Model

The Local Python plugin executes steps according to the dependency graph.

Execution preserves:

- Step ordering
- Parallel opportunities
- Failure semantics
- Retry policies
- Callback behavior
- Resource lifecycles

The implementation should never change observable pipeline behavior.

## Sync and Async

The Local Python plugin supports both:

```python
def normalize(...):
    ...
```

and

```python
async def normalize(...):
    ...
```

Pipelantic automatically invokes the correct implementation style.

Developers should not manage event loops directly.

## Concurrency

Where possible, the plugin may execute independent branches concurrently.

Concurrency should always respect:

- Dependency ordering
- Resource constraints
- Failure semantics
- Callback ordering

Optimization must never alter pipeline meaning.

## Resources

The Local Python plugin coordinates:

- Resource plugins
- Storage plugins
- Dataframe plugins
- Callback execution

It acquires resources during execution and releases them when no longer needed.

## Diagnostics

The plugin should emit structured execution events including:

- Pipeline started
- Step started
- Step completed
- Step failed
- Retry
- Pipeline completed

Events should reference stable pipeline and step identities.

## Relationship to Other Plugins

Local execution is one orchestration backend among many.

The same Pipeline Plan may also execute using:

- Airflow
- Dagster
- Prefect
- Future orchestration plugins

Observable pipeline semantics should remain identical.

## Best Practices

- Use Local Python during development.
- Validate before execution.
- Test pipelines locally before deployment.
- Keep execution profiles environment-specific.
- Preserve deterministic behavior.

## Anti-Patterns

Avoid:

- Executing Python pipeline definitions directly.
- Skipping validation or planning.
- Embedding local-only behavior into pipeline contracts.
- Treating Local Python as a separate execution model.

## Key Principle

> Local Python is the reference execution backend for Pipelantic. It executes
validated Pipeline Plans directly within Python while preserving the same
portable semantics expected from every orchestration plugin.

## Next Step

Continue with [Compilation](COMPILATION.md) to compare direct local execution
with generation of backend-specific artifacts.
