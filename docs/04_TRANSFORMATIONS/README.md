# Transformations

Transformations are the heart of ETLantic.

A transformation defines **how data logically changes** as it moves through a pipeline. Like FastAPI endpoints, transformations are declared using Python classes and type annotations. The declaration describes the interface; execution implementations remain separate.

ETLantic models transformations using **Transformation Contracts**, represented portably by the **Data Transformation Contract Standard (DTCS)**.

## What This Section Covers

This section explains how to:

- Define transformations using Python classes
- Declare typed inputs and outputs
- Define transformation parameters
- Register execution implementations
- Support synchronous and asynchronous execution
- Generate DTCS artifacts
- Validate transformation compatibility
- Connect transformations into pipelines

## The Authoring Model

A transformation begins as a typed class:

```python
from etlantic import Input, Output, Parameter, Transformation


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]
```

This declaration answers:

- What data enters?
- What data leaves?
- What configuration controls behavior?

It intentionally does **not** answer how the work is performed.

An accepted 0.11+ design adds a PySpark-inspired, implementation-agnostic
definition that serializes as a DTCS 3.0 Transformation Plan and plugins
compile. See
[Portable Transformations](PORTABLE_TRANSFORMATIONS.md). This API is not
available in ETLantic 0.10.

## Separating Interface from Implementation

Execution is registered independently.

```python
@NormalizeCustomers.implementation("polars")
def normalize(customers, minimum_age):
    ...
```

A second implementation may target another backend:

```python
@NormalizeCustomers.implementation("pandas")
def normalize(customers, minimum_age):
    ...
```

Both satisfy the same transformation contract.

## Relationship to DTCS

DTCS is the portable representation of a transformation.

```text
Python Transformation
        │
        ▼
Typed Transformation Model
        │
        ▼
DTCS Contract
```

The Python class is the preferred authoring surface.

The DTCS document is the portable artifact.

## Relationship to Pipelines

Transformations are connected together inside pipelines.

```python
class CustomerPipeline(Pipeline):
    normalized = NormalizeCustomers.step(
        customers=raw_source,
    )
```

ETLantic validates that upstream outputs satisfy downstream inputs before execution planning begins.

## Sync and Async

ETLantic supports both synchronous and asynchronous implementations.

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

The framework normalizes invocation internally so authors focus on business logic rather than concurrency.

## Callbacks

Transformations may expose lifecycle callbacks for events such as:

- Invalid input data
- Invalid output data
- Execution failures
- Retry decisions
- Completion notifications

Callbacks may be synchronous or asynchronous.

## Validation

ETLantic validates:

- Input compatibility
- Output compatibility
- Parameter types
- Implementation signatures
- Plugin capabilities

DTCS defines transformation semantics; ETLantic coordinates validation.

## Generated Artifacts

A transformation can generate:

- DTCS contracts
- Documentation
- Mermaid diagrams
- Graphviz diagrams
- API metadata
- Planning metadata

These artifacts are deterministic and suitable for version control.

## Documentation Roadmap

Read this section in the following order:

1. `TRANSFORMATION.md`
2. `INPUTS.md`
3. `OUTPUTS.md`
4. `PARAMETERS.md`
5. `TYPE_ANNOTATIONS.md`
6. `IMPLEMENTATIONS.md`
7. `PORTABLE_TRANSFORMATIONS.md` (accepted 0.11+ authoring design)
8. `PORTABLE_FUNCTIONS.md` (DTCS 2.0/3.0 mapping for the planned facade)
9. `CALLBACKS.md`
10. `ERROR_HANDLING.md`
11. `ASYNC.md`
12. `DTCS.md`

## Key Principles

- Transformations define interfaces, not execution.
- Types are the source of truth.
- Implementations are interchangeable.
- DTCS is the canonical portable representation.
- Python remains the preferred authoring experience.
- Execution belongs to plugins.

## Next Step

Continue with [Transformation](TRANSFORMATION.md) to learn how to define
transformation contracts using typed Python classes.
