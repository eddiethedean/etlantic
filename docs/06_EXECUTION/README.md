# Execution

!!! success "Available"
    Portable Polars + PySpark + Pandas relational compilation (shipped since
    0.14) plus SQL portable lowering (since 0.15) remain current. ETLantic
    executes registered native implementations and, when
    `Profile.portable_transform_policy` is `prefer` or `require`, can compile
    and run Polars/PySpark/Pandas [DTCS](https://etlantic.readthedocs.io/en/latest/04_TRANSFORMATIONS/DTCS/) plans through `etlantic-polars` /
    `etlantic-pyspark` / `etlantic-pandas` without a native
    `@implementation(...)` for the advertised kernel +
    `portable-relational/1` claim set. See
    [Portable Transformations](https://etlantic.readthedocs.io/en/latest/04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS/)
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

- **[ODCS](https://etlantic.readthedocs.io/en/latest/03_DATA_CONTRACTS/ODCS/)** validates data.
- **DTCS** defines transformation semantics.
- **[DPCS](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/DPCS/)** defines pipeline semantics.

Execution plugins preserve these semantics while mapping them onto runtime
capabilities.

## Documentation Roadmap

Start with a tutorial, then deepen:

1. [Reports and history](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/REPORTS_AND_HISTORY/)
2. Pick an engine tutorial (Polars / Pandas / SQL hello / PySpark / Airflow)
3. [Storage today](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/STORAGE_TODAY/)
4. [Execution Model](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/EXECUTION_MODEL/)
5. [Secrets Management](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/SECRETS_MANAGEMENT/)
6. Plugin reference pages only when you need API detail

!!! note "Future design (not in the 0.34 operator path)"
    [Lifecycle Extensions](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/LIFECYCLE_EXTENSIONS/),
    [Plugins overview](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PLUGINS/),
    [Storage Plugins](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/STORAGE_PLUGINS/), and
    [Resource Providers](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/RESOURCE_PLUGINS/) describe unshipped provider
    protocols. Prefer [Storage today](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/STORAGE_TODAY/) and
    [Capabilities](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/CAPABILITIES/).

### Operations and deployment

7. [Deployment](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/DEPLOYMENT/) — process model and adopter ownership
8. [Production readiness](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PRODUCTION_READINESS/) — what ETLantic claims vs what you own
9. [Production profiles](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PRODUCTION_PROFILES/) — fail-closed production template
10. [CI integration](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/CI_INTEGRATION/) — SARIF gates and pin matrix
11. [Pilot walkthrough](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/PILOT_WALKTHROUGH/) — controlled evaluation path
12. [Ops pilot](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/OPS_PILOT/) — pin matrix, failure ownership, Airflow handoff

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

Continue with the [Execution Model](https://etlantic.readthedocs.io/en/latest/06_EXECUTION/EXECUTION_MODEL/) to learn how every
runtime realizes a validated `PipelinePlan`.

When something fails, start with Getting Started
[Troubleshooting](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/TROUBLESHOOTING/) (including the M6
ops failure cookbook), then return to the engine tutorial for your backend.
