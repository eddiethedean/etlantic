# Parameters

`Parameter[T]` defines a typed configuration value for a `Transformation`.

Unlike `Input[T]` and `Output[T]`, parameters are **not** pipeline edges. They
configure how a transformation behaves without representing data flowing
through the pipeline.

## Purpose

Parameters answer a single question:

> How should this transformation behave?

Because parameters are strongly typed, ETLantic can validate them,
document them, and include them in [DTCS](DTCS.md) artifacts.

## Basic Example

```python
from etlantic import Input, Output, Parameter, Transformation

class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]

    minimum_age: Parameter[int] = 18
    trim_whitespace: Parameter[bool] = True

    result: Output[Customer]
```

The transformation interface now consists of:

- One input
- Two parameters
- One output

## Relationship to the Pipeline Graph

Parameters are **configuration**, not data flow.

```text
RawCustomer
      │
      ▼
NormalizeCustomers
  minimum_age=18
  trim_whitespace=True
      │
      ▼
Customer
```

Changing a parameter changes transformation behavior without changing the
pipeline topology.

## Strong Typing

Parameters use ordinary Python type annotations.

```python
batch_size: Parameter[int]
threshold: Parameter[float]
enabled: Parameter[bool]
mode: Parameter[str]
```

ETLantic validates parameter values before execution.

## Defaults

Parameters may provide defaults.

```python
minimum_age: Parameter[int] = 18
```

If a caller does not override the value, the default is used.

## Required Parameters

A parameter without a default is required.

```python
country: Parameter[str]
```

Planning should fail if a required parameter is not supplied.

## Optional Parameters

Optional values use normal Python typing.

```python
from typing import Optional

timezone: Parameter[Optional[str]] = None
```

## Enums

Enums are recommended when only a fixed set of values is valid.

```python
from enum import StrEnum

class Mode(StrEnum):
    STRICT = "strict"
    LENIENT = "lenient"

mode: Parameter[Mode] = Mode.STRICT
```

Enums improve validation, documentation, and editor support.

## Validation

ETLantic validates:

- Required parameters
- Parameter types
- Default values
- Enum membership
- Constraint metadata
- User-supplied overrides

Parameter validation occurs before transformation execution.

## Constraint Metadata

Parameters may use `Annotated` and `Field` metadata.

```python
from typing import Annotated
from pydantic import Field

batch_size: Parameter[
    Annotated[int, Field(gt=0, le=100000)]
] = 1000
```

This metadata may appear in:

- DTCS artifacts
- Generated documentation
- CLI help
- Visual editors

## Runtime Overrides

Parameters may be overridden when constructing a pipeline.

```python
normalized = NormalizeCustomers.step(
    customers=raw.result,
    minimum_age=21,
)
```

The override becomes part of the execution plan while the transformation
contract remains unchanged.

## Per-run overrides

Profiles do not contain transformation parameter values in 0.34. Declare
stable defaults on the transformation or supply explicit per-run overrides:

```python
from etlantic.runtime import RunRequest

request = RunRequest(
    parameter_overrides={
        "normalize_customers": {"batch_size": 100},
    }
)
```

This keeps the profile focused on execution behavior and makes an override
explicit in the run request.

## Relationship to DTCS

Declared parameters become part of the generated DTCS transformation contract.

DTCS records:

- Name
- Type
- Required status
- Default value
- Documentation
- Constraints (where portable)

## Documentation

Parameters are automatically included in generated documentation, allowing
users to understand configuration without reading implementation code.

## Best Practices

- Use descriptive parameter names.
- Prefer explicit types.
- Provide sensible defaults where appropriate.
- Use enums instead of free-form strings.
- Keep parameters focused on transformation behavior.
- Validate values before execution.

## Anti-Patterns

Avoid:

- Passing large datasets as parameters.
- Using untyped dictionaries for configuration.
- Embedding execution-engine objects as parameters.
- Repeating information already present in data contracts.

## Key Principle

> `Parameter[T]` configures **how** a transformation behaves. It is not part of
the logical data flowing through the pipeline.

## Next Step

Continue with **IMPLEMENTATIONS.md** to learn how execution backends satisfy a
transformation contract while keeping the logical interface unchanged.
