# Pipelines

Pipelines connect typed transformations into complete, executable data workflows.

If **Data Contracts** define *what* data looks like and **Transformations**
define *how* data changes, then **Pipelines** define *how those transformations
are connected*.

ETLantic models pipelines using the **Data Pipeline Contract Standard
([DPCS](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/DPCS/))** while remaining independent of any execution engine.

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

A pipeline is declared using ordinary Python — or, since 0.24, with functional
builders / `PipelineDefinition` JSON that normalize to the same immutable
definition. See [Programmatic authoring](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PROGRAMMATIC_AUTHORING/).

!!! success "Functional and JSON authoring are Available in 0.24"
    Class, functional, and JSON paths share `PipelineDefinition` and
    `etlantic.pipeline/1`. GUI hosts use the authoring catalog, edit commands,
    and optional `etlantic-fastapi` reference adapter. See
    [What's New in 0.24](https://etlantic.readthedocs.io/en/latest/01_GETTING_STARTED/WHATS_NEW_0_24/).

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

Class, functional, and JSON authoring share one `PipelineDefinition`.

DPCS is the portable interchange artifact.

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
> See [SOURCES.md](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/SOURCES/) and [SINKS.md](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/SINKS/) only for the rename
> pointers; author against [Extracts](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/EXTRACTS/) and [Loads](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/LOADS/).

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

1. [Pipeline](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PIPELINE/)
2. [Programmatic authoring](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PROGRAMMATIC_AUTHORING/) — builders + JSON (0.24)
3. [Extracts](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/EXTRACTS/)
4. [Steps](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/STEPS/)
5. [Loads](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/LOADS/)
6. [Subpipelines](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/SUBPIPELINES/)
7. [DPCS](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/DPCS/)
8. [Pipeline Validation](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PIPELINE_VALIDATION/)
9. [Planning](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PLANNING/)
10. [Profiles](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PROFILES/)
11. [Contract Generation](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/CONTRACT_GENERATION/)
12. [Contract Loading](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/CONTRACT_LOADING/)

## Key Principles

- Pipelines connect transformations.
- Data contracts validate every connection.
- Planning precedes execution.
- Execution belongs to plugins.
- DPCS is the canonical portable representation.
- Classes, functional builders, and JSON share one canonical
  `PipelineDefinition` (Available in 0.24) without changing DPCS's standards
  role.

## Next Step

Continue with [Pipeline](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PIPELINE/) to learn how to define typed pipeline
classes and compose transformations into complete workflows.
