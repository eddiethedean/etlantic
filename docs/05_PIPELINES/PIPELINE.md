# Pipeline

A `Pipeline` defines the logical composition of a complete data workflow.

A pipeline connects typed extracts, transformations, and loads into a directed
graph. Like FastAPI's application object, a `Pipeline` is primarily declarative:
it describes the workflow, while execution is delegated to pluggable runtime
engines.

## Purpose

A pipeline answers one question:

> How are transformations connected to produce a complete workflow?

ETLantic uses pipeline definitions to:

- Validate graph structure
- Verify contract compatibility
- Generate DPCS artifacts
- Build resolved `PipelinePlan` objects
- Produce lineage
- Generate documentation

## Basic Example

```python
from etlantic import Extract, Load, Pipeline

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

The pipeline definition is the source of truth. It does not specify scheduling,
threading, orchestration, or execution engines.

## Building Blocks

A pipeline consists of:

- Extracts (read typed data into the graph)
- Transformations
- Loads (publish typed data out of the graph)

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

Each connection is typed through data contracts.

> **Migration note:** Public `Source` / `Sink` aliases were removed in 0.16.
> Use `Extract` / `Load`. See [SOURCES.md](SOURCES.md) and [SINKS.md](SINKS.md).

## Graph Semantics

Pipelines form directed acyclic graphs (DAGs).

ETLantic derives graph topology from typed references rather than requiring
developers to construct graph objects manually.

The planner identifies:

- Nodes
- Edges
- Dependencies
- Execution order
- Parallel opportunities

## Extracts

Extracts introduce data into the graph.

```python
customers: Extract[RawCustomer] = Extract(asset="customer_source")
```

Every extract declares the contract of the data it produces.

## Transformations

Transformations consume and produce typed contracts.

```python
normalized = NormalizeCustomers.step(
    customers=customers,
)
```

Each transformation becomes a graph node.

## Loads

Loads publish data outside the pipeline.

```python
warehouse: Load[Customer] = Load(
    input=normalized.result,
    asset="customer_sink",
)
```

ETLantic validates load compatibility before execution.

## Planning

Planning occurs before execution.

Planning resolves:

- Graph topology
- Contract compatibility
- Implementation selection
- Validation policy
- Execution profile
- Runtime bindings

Planning should fail before execution whenever possible.

## Execution Independence

Pipeline definitions never depend on a specific execution framework.

The same pipeline may execute using different plugins, including:

- Local Python
- Polars
- Pandas
- SQL
- PySpark
- Airflow (compile)
- Prefect (direct execution)
- Future execution engines

The logical pipeline remains unchanged.

## Relationship to DPCS

Every pipeline has a portable DPCS representation.

```text
Python Pipeline
      │
      ▼
DPCS Pipeline Contract
```

The Python class is the preferred authoring surface.

The generated DPCS artifact is the portable representation.

## Validation

ETLantic validates:

- Graph correctness
- Required extracts
- Required loads
- Contract compatibility
- Version compatibility
- Transformation implementations
- Execution profile capabilities

## Lineage

Because every node and edge is typed, ETLantic can automatically derive:

- End-to-end lineage
- Dataset dependencies
- Transformation dependencies
- Impact analysis
- Documentation

No additional lineage configuration is required.

## Reusability

Pipelines should be composable.

Future versions may support sub-pipelines and reusable pipeline modules while
preserving DPCS compatibility.

## Best Practices

- Keep pipelines declarative.
- Separate modeling from execution.
- Reuse transformations.
- Use explicit contracts at every boundary.
- Validate before execution.
- Generate DPCS artifacts in CI.

## Anti-Patterns

Avoid:

- Embedding execution logic in pipeline definitions.
- Depending on orchestrator-specific APIs.
- Bypassing contract validation.
- Hard-coding runtime implementations into pipeline classes.

## Key Principle

> A `Pipeline` describes the logical flow of data through typed transformations.
> Execution engines decide how that flow is carried out.

## Next Step

Continue with [EXTRACTS.md](EXTRACTS.md) to learn how typed extracts introduce
data into a pipeline.
