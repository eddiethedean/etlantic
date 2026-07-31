**Status: shipped in 0.8.0** via `etlantic-airflow`.

# Orchestration Plugins

Orchestration plugins bind a validated **Pipeline Plan** to a workflow
orchestration platform.

ETLantic does not embed Airflow, Dagster, Prefect, or any other scheduler
into its core. Instead, **orchestration plugins** translate the
implementation-independent Pipeline Plan into runtime-specific workflow
*artifacts* (for example Airflow DAGs) while preserving the pipeline's
declared semantics.

Direct in-process or Python-native coordination uses the separate
`ExecutionScheduler` boundary (`LocalScheduler` and the optional
`etlantic-prefect` local MVP). Prefect is not modeled as an
Airflow-style `compile_plan` target.

## Goals

Orchestration plugins should:

- Preserve [DPCS](../05_PIPELINES/DPCS.md) semantics.
- Remain independent of pipeline modeling.
- Support multiple orchestration platforms.
- Declare capabilities explicitly.
- Generate deterministic orchestration artifacts.
- Fail when mandatory semantics cannot be preserved.

## Philosophy

ETLantic defines **what** the pipeline means.

Orchestration plugins define **where and how** it is coordinated.

```text
Pipeline Plan
      │
      ├──────────────────────────────┐
      ▼                              ▼
Orchestration Plugin           ExecutionScheduler
(compile / submit)             (direct execution)
      │                              │
 ┌────┼────────┐              ┌──────┼────────┐
 ▼    ▼        ▼              ▼               ▼
Airflow Dagster  …        LocalScheduler   Prefect
```

Compile plugins produce platform artifacts. Scheduler plugins coordinate
already-resolved physical/logical work without re-planning.

## Why Plugins?

Separating orchestration from modeling provides:

- Vendor independence
- Easier testing
- Cleaner APIs
- Multiple deployment targets
- Future extensibility

Pipeline definitions never depend on orchestrator APIs.

## Supported Platforms

ETLantic is designed to support:

- Local execution via built-in `LocalScheduler`
- Airflow via `etlantic-airflow` (`OrchestratorPlugin` / `compile_plan`)
- Prefect via shipped `etlantic-prefect` (`ExecutionScheduler`, local MVP)
- Planned 0.49 compile or scheduler adapters (Dagster, expanded Prefect, and
  Argo) behind the matching protocol; additional cloud workflow services remain
  candidates

Do not assume every platform is a compile target. Prefect's shipped path is
local direct execution, not DAG artifact generation.

## Capability Matching

Each orchestration plugin publishes the capabilities it supports.

Examples include:

- Scheduling
- Parallel execution
- Retries
- Checkpoints
- Event triggers
- Approval workflows
- Compensation
- Dynamic branching

During planning, ETLantic compares pipeline requirements against plugin
capabilities.

Planning or binding should fail if a required capability is unavailable.

## Binding

Binding converts a Pipeline Plan into a platform-specific representation.

Examples include:

- Airflow DAG
- Dagster Definitions
- Argo Workflow
- Deployment manifests

Prefect Flow / task mapping for the shipped local MVP belongs to the
`ExecutionScheduler` path, not this compile binding list.

Bindings must preserve:

- Graph topology
- Step identities
- Dependencies
- Scheduling intent
- Failure semantics
- Quality gates
- Lineage
- Contract references

## Scheduling

Scheduling is part of the orchestration layer—not the pipeline definition.

Profiles may select:

- Manual execution
- Cron schedules
- Event-driven execution
- Dependency-triggered execution

The orchestration plugin maps these requirements to the target platform.

## Resource Management

Plugins coordinate runtime resources such as:

- Worker pools
- Queues
- Compute resources
- Secrets
- External services

Resources are resolved through profiles and bindings rather than embedded in
pipeline contracts.

## Observability

Plugins should expose execution events including:

- Pipeline started
- Step started
- Step completed
- Step failed
- Retry
- Pipeline completed

Events should reference stable pipeline and step identities.

## Best Practices

- Preserve observable semantics.
- Declare capabilities explicitly.
- Keep orchestrator-specific configuration out of pipelines.
- Validate bindings before deployment.
- Generate deterministic artifacts.

## Anti-Patterns

Avoid:

- Writing Airflow-specific pipeline definitions.
- Encoding scheduler logic in transformation contracts.
- Silently ignoring unsupported features.
- Changing graph semantics during binding.

## Key Principle

> Orchestration plugins coordinate execution of a Pipeline Plan on a specific
platform while preserving the portable semantics defined by DPCS.

## Next Step

Continue with [Resource Providers](RESOURCE_PLUGINS.md) to learn how execution
plugins acquire and manage runtime resources.
