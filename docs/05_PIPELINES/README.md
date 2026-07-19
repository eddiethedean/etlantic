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
- Declare sources and sinks
- Configure execution profiles
- Validate pipeline graphs
- Generate DPCS artifacts
- Plan execution
- Produce lineage and documentation

## The Authoring Model

A pipeline is declared using ordinary Python.

```python
from etlantic import Pipeline, Sink, Source


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

## Sources and Sinks

Pipelines begin with typed sources and end with typed sinks.

```text
Source
   │
   ▼
Transformation
   │
   ▼
Transformation
   │
   ▼
Sink
```

Every connection is validated through data contracts.

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
2. [Sources](EXTRACTS.md)
3. [Steps](STEPS.md)
4. [Sinks](LOADS.md)
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
- Python remains the preferred authoring experience.

## Next Step

Continue with [Pipeline](PIPELINE.md) to learn how to define typed pipeline
classes and compose transformations into complete workflows.
