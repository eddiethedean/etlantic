# Pipelines

Pipelines connect typed transformations into complete, executable data workflows.

If **Data Contracts** define *what* data looks like and **Transformations**
define *how* data changes, then **Pipelines** define *how those transformations
are connected*.

ETLantic models pipelines using the **Data Pipeline Contract Standard
(DPCS)** while remaining independent of any execution engine.

## What This Section Covers

This section explains how to:

- Define pipelines with Python classes
- Connect transformations using typed inputs and outputs
- Declare extracts and loads (`asset=`)
- Configure execution profiles
- Validate pipeline graphs
- Generate DPCS artifacts
- Plan execution
- Produce lineage and documentation

## The Authoring Model

A pipeline is declared using ordinary Python.

!!! note "Functional and JSON authoring are planned for 0.24"
    ETLantic 0.23 uses the class API shown below. Version 0.24 plans equivalent
    functional builders and an authoring-complete `PipelineDefinition` that
    round-trips through canonical `etlantic.pipeline/1` JSON. A GUI or FastAPI
    service will be able to build the same definition without generating a
    Python class. See the
    [0.24 plan](../11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24.md).

```python
from etlantic import Extract, Load, Pipeline

# Recommended 0.22+ style (equivalent objects):
# import etlantic as etl
# class MyPipeline(etl.Pipeline): ...


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")

    normalized = NormalizeCustomers.step(
        customers=raw,
        minimum_age=18,
    )

    warehouse: Load[Customer] = Load(
        input=normalized.result,
        asset="customer_sink",
    )
```

The declaration focuses on logical data flow. Profiles bind
`customer_source` and `customer_sink` to files, tables, APIs, or other
environment-specific implementations.

## Relationship to DPCS

Every pipeline has a portable representation.

```text
Python Pipeline
       │
       ▼
ETLantic
       │
       ▼
DPCS Pipeline Contract
```

Python is the preferred authoring experience.

DPCS is the portable artifact.

## Planning vs. Execution

ETLantic separates planning from execution.

Planning determines:

- Graph topology
- Contract compatibility
- Implementation selection
- Validation policy
- Execution profile
- Runtime bindings

Execution plugins perform the actual work.

## Extracts and Loads

Pipelines begin with typed extracts and end with typed loads. Prefer
`Extract[T](asset=...)` and `Load[T](..., asset=...)`.

```text
Extract
   │
   ▼
Transformation
   │
   ▼
Transformation
   │
   ▼
Load
```

Every connection is validated through data contracts.

> **Migration note:** Public `Source` / `Sink` aliases were removed in 0.16.
> See [SOURCES.md](SOURCES.md) and [SINKS.md](SINKS.md) only for the rename
> pointers; author against [Extracts](EXTRACTS.md) and [Loads](LOADS.md).

## Validation

Before execution, ETLantic validates:

- Graph structure
- Contract compatibility
- Required bindings
- Transformation implementations
- Execution profile
- Plugin capabilities

Planning should fail before execution whenever possible.

## Generated Artifacts

A pipeline can generate:

- DPCS contracts
- Documentation
- Mermaid diagrams
- Graphviz diagrams
- Lineage graphs
- Execution plans

Generated artifacts are deterministic and suitable for version control.

## Documentation Roadmap

Read this section in the following order:

1. [Pipeline](PIPELINE.md)
2. [Extracts](EXTRACTS.md)
3. [Steps](STEPS.md)
4. [Loads](LOADS.md)
5. [Subpipelines](SUBPIPELINES.md)
6. [DPCS](DPCS.md)
7. [Pipeline Validation](PIPELINE_VALIDATION.md)
8. [Planning](PLANNING.md)
9. [Profiles](PROFILES.md)
10. [Contract Generation](CONTRACT_GENERATION.md)
11. [Contract Loading](CONTRACT_LOADING.md)

## Key Principles

- Pipelines connect transformations.
- Data contracts validate every connection.
- Planning precedes execution.
- Execution belongs to plugins.
- DPCS is the canonical portable representation.
- Python classes are the preferred authoring experience in 0.23.
- In 0.24, classes, functional builders, JSON, and visual editors converge on
  one canonical definition without changing DPCS's standards role.

## Next Step

Continue with [Pipeline](PIPELINE.md) to learn how to define typed pipeline
classes and compose transformations into complete workflows.
