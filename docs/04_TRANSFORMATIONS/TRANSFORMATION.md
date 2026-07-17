# Transformation

A `Transformation` defines the logical interface of a data operation.

Like a FastAPI endpoint, a Transformation declares **what it accepts** and
**what it produces** using Python type annotations. It does not describe how
the work is executed.

Execution implementations are registered separately, allowing the same
transformation contract to run on different execution engines.

The accepted 0.11+ design also permits a single portable relational definition
that compatible plugins compile. This API is not available in 0.10.

## Design Goals

A transformation should:

- Be strongly typed.
- Be independent of execution technology.
- Clearly declare inputs, outputs, and parameters.
- Generate a DTCS artifact.
- Support multiple interchangeable implementations.
- Optionally carry one backend-independent portable definition.

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

## Implementations

A transformation may have multiple implementations.

```python
@NormalizeCustomers.implementation("polars")
def normalize(customers, minimum_age):
    ...
```

```python
@NormalizeCustomers.implementation("pandas")
def normalize(customers, minimum_age):
    ...
```

The transformation contract remains unchanged while execution varies.

## Portable Definition (0.11+)

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
an immutable transformation IR. It never receives source rows. Engine plugins
compile supported operations to Polars, Pandas, SQL, PySpark, or future native
expressions.

See [Portable Transformations](PORTABLE_TRANSFORMATIONS.md) and the
[function reference](PORTABLE_FUNCTIONS.md).

## Synchronous and Asynchronous Execution

ETLantic supports both:

```python
@NormalizeCustomers.implementation("polars")
def normalize(...):
    ...
```

```python
@NormalizeCustomers.implementation("remote")
async def normalize(...):
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
