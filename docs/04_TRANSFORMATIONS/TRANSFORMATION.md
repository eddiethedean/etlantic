# Transformation

A `Transformation` defines the logical interface of a data operation.

Like a FastAPI endpoint, a Transformation declares **what it accepts** and
**what it produces** using Python type annotations. It does not describe how
the work is executed.

Define the logic once as a portable ETLantic transformation. Compatible engine
plugins compile that definition; native engine implementations remain explicit
escape hatches.

## Design Goals

A transformation should:

- Be strongly typed.
- Be independent of execution technology.
- Clearly declare inputs, outputs, and parameters.
- Generate a [DTCS](DTCS.md) artifact.
- Carry one backend-independent portable definition by default.
- Support native implementations where the portable surface is insufficient.

## Basic Example

```python
from etlantic import Input, Output, Parameter, Transformation

class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]
```

The declaration is the contract.

## Inputs

Inputs describe the logical datasets consumed by the transformation.

```python
customers: Input[RawCustomer]
```

Each input references a `Data` and is validated during planning.

## Outputs

Outputs describe the datasets produced by the transformation.

```python
result: Output[Customer]
```

ETLantic validates that downstream consumers are compatible with the
declared output contract.

## Parameters

Parameters configure behavior without becoming part of the pipeline graph.

```python
minimum_age: Parameter[int] = 18
```

Parameters are strongly typed and participate in validation and documentation.

## Portable Definition

```python
from etlantic.transform import functions as F


@NormalizeCustomers.portable
def normalize(customers, minimum_age):
    return (
        customers
        .filter(F.col("age") >= minimum_age)
        .select("customer_id", "full_name")
    )
```

The function receives symbolic inputs during definition building and produces
an immutable transformation IR. It never receives source rows. The qualified
baseline compiles to Local, Polars, Pandas, SQL, PySpark, DataFusion, and
DuckDB. This is the recommended path and the form supported by upcoming
adaptive execution.

See [Portable Transformations](PORTABLE_TRANSFORMATIONS.md) and the
[function reference](PORTABLE_FUNCTIONS.md).

## Native Implementations

A transformation may register a native body when a required operation is
outside the portable surface:

```python
@NormalizeCustomers.implementation("polars")
def normalize_polars(customers, minimum_age):
    ...
```

The contract remains reusable, but the body is tied to Polars and is not
eligible for adaptive execution.

## Synchronous and Asynchronous Execution

ETLantic supports both:

```python
@NormalizeCustomers.implementation("polars")
def normalize(customers, minimum_age=18):
    ...
```

```python
@NormalizeCustomers.implementation("remote")
async def normalize(customers, minimum_age=18):
    ...
```

The framework normalizes invocation internally.

## Relationship to DTCS

Every transformation can be represented as a DTCS artifact.

```text
Python Transformation
        │
        ▼
DTCS Transformation Contract
```

Python is the preferred authoring experience.
DTCS is the portable representation.

## Validation

ETLantic validates:

- Input contract compatibility
- Output contract compatibility
- Parameter types
- Implementation signatures
- Portable expression names, types, outputs, and bounded structure
- Compiler operation and semantic capabilities
- Plugin capability requirements

Validation occurs before execution planning.

## Planning

Transformations become nodes in the pipeline graph.

During planning, ETLantic resolves:

- Dependencies
- Runtime bindings
- Execution profiles
- Plugin selection
- Portable compiler selection and native fallback policy
- Validation requirements

## Best Practices

- Use one transformation per logical operation.
- Keep transformation contracts stable.
- Separate interface from implementation.
- Prefer typed parameters over unstructured dictionaries.
- Support multiple execution engines where practical.
- Prefer portable definitions for common relational behavior once the feature
  ships; use native implementations for explicit backend-specific behavior.

## Anti-Patterns

Avoid:

- Embedding execution-specific logic in the contract.
- Referencing dataframe libraries in transformation interfaces.
- Duplicating schema information already defined by data contracts.
- Mixing orchestration concerns into transformations.

## Key Principle

> A Transformation declares its typed contract. A portable definition may
> describe backend-independent relational behavior, while plugins and native
> implementations determine how that behavior runs.

## Next Step

Continue with [Inputs](INPUTS.md) and [Outputs](OUTPUTS.md) to learn how typed
ports define the boundaries between transformations.
