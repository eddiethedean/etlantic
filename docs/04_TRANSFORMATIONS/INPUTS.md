# Inputs

`Input[T]` defines a typed input port for a `Transformation`.

An input represents a logical dataset flowing into a transformation. The type
parameter `T` must be a `Data` (or another supported contract
type), allowing ETLantic to validate compatibility before execution.

## Purpose

Inputs answer a single question:

> What data does this transformation require?

By declaring inputs with type annotations, ETLantic can infer:

- Required upstream contracts
- Pipeline graph edges
- Validation rules
- [DTCS](DTCS.md) input definitions
- Documentation
- Editor tooling

## Basic Example

```python
from etlantic import Input, Output, Transformation

class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]
```

`customers` is the logical input to the transformation.

## Relationship to Data Contracts

Inputs always reference a contract rather than a dataframe type.

```python
customers: Input[Customer]
```

The contract describes the records.

Execution plugins decide whether those records are represented as:

- Polars DataFrames
- Pandas DataFrames
- Arrow Tables
- SQL result sets
- Streaming batches
- Other runtime-native structures

## Multiple Inputs

Transformations may declare multiple inputs.

```python
class MergeCustomers(Transformation):
    crm: Input[CRMCustomer]
    billing: Input[BillingCustomer]
    result: Output[Customer]
```

Each input is validated independently.

## Optional Inputs

Optional inputs may be expressed using standard Python typing when supported.

```python
from typing import Optional

lookup: Input[Optional[LookupTable]]
```

Whether an input is required is part of the transformation contract.

## Collection Inputs

Inputs may represent collections of contract instances.

```python
customers: Input[list[Customer]]
```

The collection describes the logical interface, not the runtime container.

## Named Inputs

Input names become part of the transformation interface.

```python
orders: Input[Order]
customers: Input[Customer]
```

These names appear in:

- DTCS artifacts
- Documentation
- Validation diagnostics
- Pipeline graphs

## Pipeline Wiring

Inputs are connected from upstream outputs.

```python
normalized = NormalizeCustomers.step(
    customers=raw.result,
)
```

ETLantic validates that `raw.result` is compatible with the declared
`Input[RawCustomer]`.

## Validation

Before execution, ETLantic validates:

- Input contract compatibility
- Required inputs
- Duplicate bindings
- Missing bindings
- Type compatibility
- Version compatibility (through ContractModel)

## Planning

During planning, each input becomes an incoming edge in the pipeline graph.

The planner resolves:

- Upstream producer
- Contract identity
- Validation policy
- Runtime binding

## Relationship to DTCS

Every declared input becomes part of the generated DTCS transformation contract.

The Python declaration is the source of truth.

## Best Practices

- Use descriptive input names.
- Reference published `Data` classes.
- Keep inputs focused on logical datasets.
- Let execution plugins determine physical representations.

## Anti-Patterns

Avoid:

- Using dataframe types (`pl.DataFrame`, `pd.DataFrame`) as input types.
- Embedding execution-specific metadata in input declarations.
- Duplicating schema definitions already provided by data contracts.

## Key Principle

> An `Input[T]` defines **what data enters** a transformation. It does not define
how that data is stored, transported, or processed.

## Next Step

Continue with **OUTPUTS.md** to learn how transformations declare typed results
that flow to downstream pipeline nodes.
