# Loads

A `Load[T]` defines a typed exit point from an ETLantic pipeline.

Loads publish validated data to external systems. Like `Extract[T]`, a load
declares **what** data crosses the pipeline boundary while execution plugins
determine **how** that data is written.

> **0.15 note:** `Sink[T]` and `binding=` remain available as deprecated
> aliases and will be removed in **0.16**. Prefer `Load[T](..., asset=...)`.
> See [Migration 0.14 → 0.15](../11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md).

## Purpose

A load answers one question:

> Where does the pipeline publish its results?

Because every load is typed, ETLantic can validate publication boundaries,
generate DPCS artifacts, derive lineage, and plan execution without depending
on a specific storage technology.

## Basic Example

```python
from etlantic import Load

warehouse = Load[Customer](
    input=normalized.result,
    asset="warehouse.customers",
)
```

The load declares that it publishes `Customer` records.

## Relationship to Data Contracts

Every load references a published `Data`.

```python
warehouse: Load[Customer]
```

The contract defines the logical records being published.

Execution plugins decide whether those records are written to:

- SQL databases
- Data warehouses
- Object storage
- Parquet files
- CSV files
- REST APIs
- Message queues
- Streaming systems
- Other destinations

## Assets

Assets identify the logical destination.

```python
Load[Customer](
    input=normalized.result,
    asset="curated.customers",
)
```

Assets remain execution-neutral and are resolved by the active execution
profile or plugin. Serialized plans and DPCS retain the stable wire name
`binding` / `etlantic:binding`.

## Validation

Load inputs are the final validation boundary.

ETLantic may validate:

- Contract compatibility
- Required fields
- Nullability
- Constraints
- Version compatibility
- Publication policy

The recommended default is full validation before data leaves the pipeline.

## Planning

During planning ETLantic resolves:

- Destination asset
- Execution plugin
- Validation policy
- Runtime resources
- Authentication
- Write strategy

Missing or incompatible destinations should be reported before execution.

## Relationship to DPCS

Each load becomes part of the generated DPCS pipeline contract, including:

- Load identity (as a DPCS interface output)
- Input wiring
- Data contract
- Destination `etlantic:binding`
- Metadata

## Lineage

Loads form the terminal nodes of the lineage graph.

ETLantic can automatically derive:

- Published datasets
- Upstream dependencies
- Impact analysis
- Documentation

## Best Practices

- Publish typed data contracts.
- Validate before writing.
- Use stable logical asset names.
- Keep load definitions execution-neutral.
- Let plugins manage write semantics.

## Anti-Patterns

Avoid:

- Embedding SQL statements or SDK clients in load declarations.
- Publishing dataframe types instead of logical contracts.
- Skipping validation at publication boundaries.
- Coupling loads to a single execution engine.

## Key Principle

> A `Load[T]` defines the logical destination of data. Execution plugins decide
> how that data is written and committed.

## Next Step

Continue with [Subpipelines](SUBPIPELINES.md) to learn how complete pipeline
graphs can be composed from reusable pipeline definitions.
