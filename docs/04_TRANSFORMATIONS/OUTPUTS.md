# Outputs

`Output[T]` defines a typed output port for a `Transformation`.

An output represents the logical dataset produced by a transformation. Like
`Input[T]`, the type parameter references a data contract rather than a
particular dataframe implementation.

## Purpose

Outputs answer a single question:

> What data does this transformation produce?

By declaring outputs with type annotations, ETLantic can infer:

- Downstream contract compatibility
- Pipeline graph edges
- [DTCS](DTCS.md) output definitions
- Documentation
- Validation rules
- Lineage information

## Basic Example

```python
from etlantic import Input, Output, Transformation

class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]
```

`result` becomes a typed output that downstream nodes can consume.

The output is a logical result port. When a transformation is instantiated as a
step, that port becomes a typed reference to the result of that particular step
execution.

## Relationship to Data Contracts

Outputs reference `Data` classes.

```python
result: Output[Customer]
```

The contract describes the logical records.

Execution plugins determine whether those records are represented as:

- Polars DataFrames
- Pandas DataFrames
- Arrow Tables
- SQL result sets
- Streaming batches
- Other runtime-native structures

## Multiple Outputs

A transformation may produce more than one output.

```python
class ValidateCustomers(Transformation):
    customers: Input[RawCustomer]

    valid: Output[Customer]
    rejected: Output[RejectedCustomer]
```

Multiple outputs make branching explicit in both the pipeline graph and DTCS.

## Optional Outputs

Where appropriate, outputs may be optional.

```python
from typing import Optional

audit: Output[Optional[AuditRecord]]
```

Whether an output is optional is part of the transformation contract.

## Collection Outputs

Outputs may describe collections of records.

```python
customers: Output[list[Customer]]
```

This expresses the logical interface rather than the runtime container type.

## Pipeline Wiring

Outputs are connected to downstream inputs.

```python
validated = ValidateCustomers.step(
    customers=raw.result,
)

published = PublishCustomers.step(
    customers=validated.valid,
)
```

ETLantic validates that each downstream input is compatible with the
declared output contract.

The downstream step consumes the previous step's result. It does not implicitly
reload the producer's complete destination table.

## Output References

Given:

```python
normalized = NormalizeCustomers.step(customers=raw.result)
```

`normalized.result` is conceptually an `OutputRef[Customer]`.

An output reference identifies:

- the producer step
- the output name
- the data contract
- the logical pipeline edge

It deliberately does not specify whether the result is held in memory,
represented lazily, expressed as SQL, cached, checkpointed, or persisted.

Planning resolves that physical representation for the selected backend. This
lets ETLantic pass intermediate results directly between compatible steps
and avoid unnecessary table writes and reads.

## Validation

Transformation outputs are one of the most important validation boundaries.

ETLantic validates:

- Output contract compatibility
- Required outputs
- Missing output bindings
- Contract versions
- Runtime validation policy

If a transformation produces data that violates its declared output contract,
the implementation has failed to satisfy its interface.

The recommended default behavior is to fail the node before invalid data can
flow downstream.

## Planning

During planning, each output becomes an outgoing edge in the pipeline graph.

The planner resolves:

- Consumer nodes
- Contract identity
- Validation requirements
- Runtime bindings

## Relationship to DTCS

Every declared output becomes part of the generated DTCS transformation
contract.

The Python declaration is the source of truth.

## Documentation and Lineage

Output definitions are used to generate:

- DTCS artifacts
- Pipeline documentation
- Mermaid diagrams
- Graphviz diagrams
- Lineage graphs
- Visual editors

Because outputs are strongly typed, lineage can be derived automatically.

## Best Practices

- Give outputs descriptive names.
- Reference published data contracts.
- Keep outputs focused on logical datasets.
- Validate outputs before publication.
- Prefer explicit multiple outputs over embedding unrelated results in one
  contract.

## Anti-Patterns

Avoid:

- Returning dataframe types as output contracts.
- Mixing execution metadata into output declarations.
- Duplicating schema information already present in data contracts.
- Publishing data that has not been validated against its declared contract.

## Key Principle

> An `Output[T]` defines **what data leaves** a transformation. Execution plugins
determine how that data is represented and transported.

## Next Step

Continue with **PARAMETERS.md** to learn how transformations expose typed
configuration that influences behavior without becoming part of the pipeline
graph.
