**Status: shipped in 0.8.0** via `etlantic-airflow`.

# Airflow

Future Airflow artifacts may carry tasks whose step logic was compiled from a
portable definition. The Airflow compiler consumes the resolved Pipeline Plan;
it does not reinterpret `etlantic.transform/1` or choose a different native
fallback.

The Airflow plugin enables ETLantic to execute validated **Pipeline Plans**
using Apache Airflow.

ETLantic does not generate Airflow DAGs directly from Python pipeline
definitions. Instead, it first validates and plans the pipeline, producing an
implementation-independent `PipelinePlan`. The Airflow plugin then translates
that plan into an Airflow DAG while preserving the semantics defined by DPCS.

## Goals

The Airflow plugin should:

- Preserve DPCS pipeline semantics.
- Generate deterministic Airflow DAGs.
- Integrate with execution profiles.
- Support retries, scheduling, and dependencies.
- Remain interchangeable with other orchestration plugins.

## Philosophy

Pipeline authors should never write Airflow-specific pipeline definitions.

Instead, they author portable pipelines:

```python
class CustomerPipeline(Pipeline):
    ...
```

The execution profile selects Airflow.

```python
production = Profile(
    orchestrator="airflow",
)
```

The Airflow plugin performs the translation.

## Why Airflow?

Airflow provides:

- Mature workflow orchestration
- Rich scheduling capabilities
- Dependency management
- Extensive operator ecosystem
- Strong enterprise adoption

It is an excellent backend for scheduled and batch-oriented data pipelines.

## Binding Process

Conceptually:

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
Airflow Plugin
    │
    ▼
Airflow DAG
```

The Pipeline Plan remains the source for orchestration binding.

## Scheduling

Pipeline scheduling intent is defined by DPCS and execution profiles.

The Airflow plugin maps those requirements to Airflow constructs such as:

- Cron schedules
- Manual execution
- Event triggers (where supported)
- Catch-up behavior
- Time zones

The plugin must preserve the declared scheduling semantics.

## Task Mapping

Each pipeline step typically becomes one or more Airflow tasks.

The plugin preserves:

- Step identities
- Dependencies
- Retry policies
- Timeouts
- Failure behavior
- Callback semantics

Observable pipeline behavior should remain unchanged.

## Capabilities

The Airflow plugin should advertise capabilities such as:

- Scheduling
- Parallel execution
- Retries
- Sensors
- Dynamic task mapping
- Deferrable operators
- Task groups

Planning validates required capabilities before binding.

## Resources

Resource, storage, and dataframe plugins continue to provide runtime services.

The Airflow plugin coordinates execution but does not replace those plugins.

## Diagnostics

Binding failures should produce structured diagnostics.

Examples include:

- Unsupported capability
- Missing resource binding
- Invalid scheduling configuration
- Unsupported execution requirement

## Best Practices

- Keep pipelines Airflow-independent.
- Select Airflow through execution profiles.
- Preserve DPCS semantics.
- Generate deterministic DAGs.
- Validate before binding.

## Anti-Patterns

Avoid:

- Embedding Airflow operators inside pipeline definitions.
- Using Airflow APIs in transformation contracts.
- Depending on Airflow-specific scheduling semantics.
- Modifying pipeline behavior during DAG generation.

## Key Principle

> Airflow is an orchestration backend for ETLantic, not a modeling
dependency. The Airflow plugin translates validated Pipeline Plans into Airflow
DAGs while preserving the logical semantics defined by DPCS.

## Next Step

Continue with [Local Python](LOCAL_PYTHON.md) to learn how Pipeline Plans can
execute directly without an external orchestrator.
