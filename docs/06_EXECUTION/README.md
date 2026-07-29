# Execution

!!! success "Available in ETLantic 0.34.0"
    Portable Polars + PySpark + Pandas relational compilation (shipped since
    0.14) plus SQL portable lowering (since 0.15) remain current. ETLantic
    executes registered native implementations and, when
    `Profile.portable_transform_policy` is `prefer` or `require`, can compile
    and run Polars/PySpark/Pandas [DTCS](../04_TRANSFORMATIONS/DTCS.md) plans through `etlantic-polars` /
    `etlantic-pyspark` / `etlantic-pandas` without a native
    `@implementation(...)` for the advertised kernel +
    `portable-relational/1` claim set. See
    [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
    and
    [`examples/portable_polars_kernel.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/portable_polars_kernel.py).

Execution is the final stage of the ETLantic lifecycle.

After a pipeline has been modeled, validated, and planned, an execution plugin
realizes the resulting **Pipeline Plan** using a specific runtime such as local
Python, Polars, Airflow, Prefect (direct scheduler), or another supported
backend. Dagster and Prefect **orchestrator compilers** are not shipped; their
first-class brownfield bridges are assigned to 0.50. `etlantic-prefect` ships
today as a local MVP direct-execution scheduler.

ETLantic intentionally separates execution from modeling. The core library
coordinates execution from a resolved `PipelinePlan`, while plugins and
external systems perform backend-specific work.

## What This Section Covers

This section explains **shipped** operator paths:

- Execute Pipeline Plans (local, Polars, Pandas, SQL, PySpark)
- Select execution engines and register native / portable implementations
- Resolve secrets through shipped providers
- Handle retries and failures where documented
- Report diagnostics and run reports
- Emit structured logs (today’s logging guidance)
- Preserve pipeline semantics across runtimes

Lifecycle extensions, general storage plugins, and resource-provider protocols
remain **Future design** — see the note under Reading Order below.

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

ETLantic owns:

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

ETLantic still owns the common execution state model, diagnostics,
logical-identity propagation, callback policy, and result normalization.

This separation allows the same pipeline to execute on multiple runtimes while
preserving identical observable semantics.

## Supported Execution Models

ETLantic is designed to support:

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

- **[ODCS](../03_DATA_CONTRACTS/ODCS.md)** validates data.
- **DTCS** defines transformation semantics.
- **[DPCS](../05_PIPELINES/DPCS.md)** defines pipeline semantics.

Execution plugins preserve these semantics while mapping them onto runtime
capabilities.

## Documentation Roadmap

Start with a tutorial, then deepen:

1. [Reports and history](REPORTS_AND_HISTORY.md)
2. Pick an engine tutorial (Polars / Pandas / SQL hello / PySpark / Airflow)
3. [Storage today](STORAGE_TODAY.md)
4. [Execution Model](EXECUTION_MODEL.md)
5. [Secrets Management](SECRETS_MANAGEMENT.md)
6. Plugin reference pages only when you need API detail

!!! note "Future design (not in the 0.34 operator path)"
    [Lifecycle Extensions](LIFECYCLE_EXTENSIONS.md),
    [Plugins overview](PLUGINS.md),
    [Storage Plugins](STORAGE_PLUGINS.md), and
    [Resource Providers](RESOURCE_PLUGINS.md) describe unshipped provider
    protocols. Prefer [Storage today](STORAGE_TODAY.md) and
    [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md).

### Operations and deployment

7. [Deployment](DEPLOYMENT.md) — process model and adopter ownership
8. [Production readiness](PRODUCTION_READINESS.md) — what ETLantic claims vs what you own
9. [Production profiles](PRODUCTION_PROFILES.md) — fail-closed production template
10. [CI integration](CI_INTEGRATION.md) — SARIF gates and pin matrix
11. [Pilot walkthrough](PILOT_WALKTHROUGH.md) — controlled evaluation path
12. [Ops pilot](OPS_PILOT.md) — pin matrix, failure ownership, Airflow handoff

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
