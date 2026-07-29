**Status: shipped in 0.8.0** via `etlantic-airflow`.

# Orchestrator Plugin

An **Orchestrator Plugin** implements the ETLantic Orchestrator Plugin API
for a workflow orchestration platform.

Orchestrator plugins are responsible for coordinating execution of a validated
**Pipeline Plan**. They schedule work, honor dependencies, manage execution
lifecycles, and preserve the semantics defined by [DPCS](../05_PIPELINES/DPCS.md) without requiring
pipeline authors to write orchestrator-specific code.

## Purpose

An orchestrator plugin is responsible for:

- Executing Pipeline Plans
- Scheduling pipeline steps
- Managing dependency ordering
- Coordinating retries and failures
- Emitting execution events
- Preserving pipeline semantics

It is **not** responsible for:

- Pipeline modeling
- Contract generation
- Contract loading
- Transformation execution
- Dataframe operations

Transformation execution is delegated to dataframe plugins.

## Architecture

```text
Pipeline Plan
      │
      ▼
Orchestrator Plugin API
      │
 ┌────┼──────────────┐
 ▼    ▼              ▼
Local Airflow    Dagster
Python           Prefect
```

Every orchestrator consumes the same Pipeline Plan.

## Responsibilities

Every orchestrator plugin should:

- Load a validated Pipeline Plan
- Respect graph dependencies
- Schedule executable steps
- Coordinate callbacks
- Manage retries
- Collect execution results
- Publish structured diagnostics

Observable pipeline behavior must remain identical regardless of the selected
orchestrator.

## Plugin Interface

Conceptually:

```python
class OrchestratorPlugin:
    name: str
    version: str

    def execute(
        self,
        plan,
        profile,
    ):
        ...
```

The public SDK may evolve, but orchestrator plugins should expose a consistent
execution interface.

## Dependency Management

The plugin must execute steps only after all required upstream dependencies have
completed successfully.

Independent branches may execute concurrently when supported by the runtime.

## Capability Declaration

Plugins should advertise capabilities such as:

- Scheduling
- Parallel execution
- Retries
- Timeouts
- Event triggers
- Streaming
- Checkpoints
- Compensation
- Approval workflows

Planning verifies these capabilities before execution.

## Compilation

Many orchestrator plugins compile the Pipeline Plan into a platform-specific
artifact before execution.

Examples include:

- Airflow DAGs
- Dagster Definitions
- Argo Workflows

Prefect Flow / task mapping belongs to the shipped `ExecutionScheduler` local
MVP (`etlantic-prefect`), not this compile-oriented SDK surface.

Compilation must preserve pipeline semantics.

## Resource Coordination

Orchestrator plugins coordinate:

- Dataframe plugins
- Storage plugins
- Resource plugins
- Callback execution

Each specialized plugin retains ownership of its own responsibilities.

## Diagnostics

Plugins should emit structured events including:

- Pipeline started
- Step started
- Step completed
- Step failed
- Retry
- Pipeline completed

Events should reference stable pipeline and step identities.

## Error Handling

Backend-specific exceptions should be translated into ETLantic diagnostics.

Diagnostics should preserve:

- Pipeline identity
- Step identity
- Execution phase
- Backend details
- Original exception

## Best Practices

- Preserve DPCS semantics.
- Respect declared dependencies.
- Advertise capabilities accurately.
- Keep backend details behind the SDK.
- Produce deterministic execution behavior.

## Anti-Patterns

Avoid:

- Modifying pipeline semantics.
- Executing transformations directly.
- Embedding dataframe logic.
- Ignoring unsupported capabilities.
- Exposing orchestrator APIs through public ETLantic interfaces.

## Key Principle

> An orchestrator plugin coordinates execution of a validated Pipeline Plan on a
> specific runtime while preserving the portable semantics defined by DPCS. It
> schedules work; it does not redefine it.

## Next Step

Continue with **STORAGE_PLUGIN.md** to learn how ETLantic integrates with
persistent storage systems through the Plugin SDK.
