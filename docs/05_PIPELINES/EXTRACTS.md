# Extracts

An `Extract[T]` defines a typed entry point into an ETLantic pipeline.

Extracts introduce data from external systems into the pipeline while declaring
the logical contract of the records they produce. Like every other modeling
primitive in ETLantic, an extract describes **what** data enters the
pipeline—not **how** it is retrieved.

Execution plugins perform the actual reads.

> **0.15 note:** `Source[T]` and `binding=` remain available as deprecated
> aliases and will be removed in **0.16**. Prefer `Extract[T](asset=...)`.
> See [Migration 0.14 → 0.15](../11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md).

## Purpose

An extract answers one question:

> Where does pipeline data begin?

By declaring an extract with a data contract, ETLantic can:

- Validate incoming data
- Build the pipeline graph
- Generate DPCS artifacts
- Produce lineage
- Generate documentation
- Plan execution

## Basic Example

```python
from etlantic import Extract

customers = Extract[RawCustomer](
    asset="customers_csv",
)
```

The extract declares that it produces `RawCustomer` records.

## Relationship to Data Contracts

Every extract is typed with a `Data`.

```python
customers: Extract[Customer]
```

The contract defines the logical records.

Execution plugins determine whether those records originate from:

- CSV files
- Parquet
- SQL queries
- Object storage
- REST APIs
- Kafka
- Message queues
- Streaming systems
- Other external systems

## Assets

Extracts identify *what* to read through a logical asset name.

```python
customers = Extract[Customer](
    asset="warehouse.customers",
)
```

Asset names are intentionally execution-neutral.

A profile or plugin resolves the asset into runtime-specific details. In plans,
DPCS, and plugin protocols the resolved name is still stored under the stable
wire field `binding` / `etlantic:binding`.

## Validation

Extract validation is typically the first runtime validation boundary.

ETLantic may validate:

- Contract compatibility
- Required fields
- Nullability
- Types
- Constraints
- Extract metadata

Plugins may perform native validation or delegate to ContractModel.

## Planning

During planning, ETLantic resolves:

- Extract assets
- Execution plugin
- Validation policy
- Runtime resources
- Authentication requirements

Planning should detect missing or incompatible assets before execution.

## Execution Independence

The same extract definition should work across multiple runtimes.

```python
customers = Extract[Customer](
    asset="customers",
)
```

Different execution profiles may map that asset to:

- Local files
- Cloud storage
- SQL databases
- Data lake tables
- Streaming topics

The pipeline definition remains unchanged.

## Relationship to DPCS

Every extract becomes part of the generated DPCS pipeline contract.

The generated artifact records:

- Extract identity (as a DPCS interface input)
- Data contract
- `etlantic:binding` (wire name for the logical asset)
- Metadata
- Relationships

## Lineage

Extracts form the roots of the pipeline lineage graph.

ETLantic can automatically derive:

- Origin datasets
- Downstream dependencies
- Impact analysis
- Documentation

## Best Practices

- Type every extract with a published data contract.
- Use stable logical asset names.
- Keep assets execution-neutral.
- Validate extract data before downstream processing.
- Let execution profiles resolve runtime details.

## Anti-Patterns

Avoid:

- Embedding SQL, filesystem paths, or cloud SDK objects directly in extract contracts.
- Returning dataframe types instead of logical contracts.
- Duplicating schema information already defined by `Data`.
- Coupling extracts to a specific execution engine.

## Key Principle

> An `Extract[T]` defines the logical origin of data. Execution plugins decide how
> that data is located, read, and materialized.

## Next Step

Continue with **[LOADS.md](LOADS.md)** to learn how typed loads publish validated
data at the end of a pipeline.
