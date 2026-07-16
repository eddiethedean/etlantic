# Execution

Execution is the final stage of the Pipelantic lifecycle.

After a pipeline has been modeled, validated, and planned, an execution plugin
realizes the resulting **Pipeline Plan** using a specific runtime such as local
Python, Polars, Airflow, Dagster, Prefect, or another supported backend.

Pipelantic intentionally separates execution from modeling. The core library
coordinates execution from a resolved `PipelinePlan`, while plugins and
external systems perform backend-specific work.

## What This Section Covers

This section explains how to:

- Execute Pipeline Plans
- Build execution plugins
- Select execution engines
- Support synchronous and asynchronous execution
- Manage resources
- Resolve secrets through external providers
- Handle retries and failures
- Integrate callbacks
- Report diagnostics
- Emit structured, correlated logs
- Extend execution through lifespan, middleware, resources, and callbacks
- Preserve pipeline semantics across runtimes

## Execution Lifecycle

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
Execution Plugin
    │
    ▼
Runtime
```

Execution plugins consume `PipelinePlan` objects—they do not interpret Python
pipeline definitions directly.

## Core Philosophy

Pipelantic owns:

- Modeling
- Validation
- Planning
- Contract generation
- Contract loading

Plugins and external runtimes own:

- Reading data
- Writing data
- Running transformations
- Scheduling work
- Managing concurrency
- Resource allocation
- Runtime integration

Pipelantic still owns the common execution state model, diagnostics,
logical-identity propagation, callback policy, and result normalization.

This separation allows the same pipeline to execute on multiple runtimes while
preserving identical observable semantics.

## Supported Execution Models

Pipelantic is designed to support:

- Local execution
- Batch execution
- Distributed execution
- Orchestrated workflows
- Streaming execution
- Hybrid execution
- Remote execution

Execution engines may vary. Different profiles may produce different physical
plans, but those plans preserve the same logical pipeline contract.

## Relationship to Standards

Execution is informed by all three standards:

- **ODCS** validates data.
- **DTCS** defines transformation semantics.
- **DPCS** defines pipeline semantics.

Execution plugins preserve these semantics while mapping them onto runtime
capabilities.

## Documentation Roadmap

Start with the common runtime model, then choose the backend topics relevant to
your project:

1. [Execution Model](EXECUTION_MODEL.md)
2. [Run Reports](RUN_REPORTS.md)
3. [Lifecycle Extensions](LIFECYCLE_EXTENSIONS.md)
4. [Logging](LOGGING.md)
5. [Secrets Management](SECRETS_MANAGEMENT.md)
6. [Local Python](LOCAL_PYTHON.md)
7. [Dataframe Plugins](DATAFRAME_PLUGINS.md)
8. [SQL](SQL.md)
9. [Plugins](PLUGINS.md) (future design overview)
10. [Orchestration Plugins](ORCHESTRATION_PLUGINS.md)
11. [Storage Plugins](STORAGE_PLUGINS.md)
12. [Resource Providers](RESOURCE_PLUGINS.md)
13. [Compilation](COMPILATION.md)
14. [PySpark](PYSPARK.md)

## Key Principles

- Execution follows planning.
- Plugins execute plans, not Python models.
- Contracts remain runtime-independent.
- Execution engines preserve DPCS semantics.
- Modeling and execution evolve independently.
- Physical optimization preserves logical identities.
- Unsupported capabilities fail during planning.
- Resolved secrets never enter portable plans.

## Next Step

Continue with the [Execution Model](EXECUTION_MODEL.md) to learn how every
runtime realizes a validated `PipelinePlan`.
