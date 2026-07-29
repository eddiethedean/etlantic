# Type Annotations

Type annotations are the foundation of ETLantic.

Inspired by FastAPI, ETLantic treats Python type annotations as the primary
source of truth for pipeline interfaces. Rather than maintaining separate YAML,
configuration files, and documentation, developers describe their pipelines
using ordinary Python typing constructs.

## Philosophy

A ETLantic definition should be understandable from its type annotations
alone.

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]
```

From these annotations, ETLantic can derive:

- [DTCS](DTCS.md) transformation contracts
- Pipeline validation rules
- Documentation
- Editor tooling
- Execution planning
- Lineage information

## Supported Annotation Types

ETLantic uses standard Python typing whenever possible.

### Data Contracts

```python
customers: Input[Customer]
```

### Outputs

```python
result: Output[Customer]
```

### Parameters

```python
minimum_age: Parameter[int]
```

### Optional Types

```python
timezone: Parameter[str | None] = None
```

### Collections

```python
customers: Input[list[Customer]]
```

### Enums

```python
class Mode(StrEnum):
    STRICT = "strict"
    LENIENT = "lenient"

mode: Parameter[Mode]
```

### Annotated Metadata

ETLantic encourages `typing.Annotated` with Pydantic `Field` metadata.

```python
from typing import Annotated
from pydantic import Field

batch_size: Parameter[
    Annotated[int, Field(gt=0, le=100000)]
] = 1000
```

This metadata may be reused for validation, documentation, and generated DTCS.

## Type Introspection

ETLantic inspects annotations to construct its internal model.

Conceptually:

```text
Python Class
      │
      ▼
Type Introspection
      │
      ▼
Transformation Model
      │
      ▼
Planning, Validation, Documentation
```

## Static Typing

Because interfaces are expressed with Python types, editors and static analysis
tools can provide:

- Autocomplete
- Type checking
- Refactoring support
- Navigation
- Inline documentation

Future releases may include dedicated Pyright or mypy plugins.

## Runtime Independence

Type annotations describe logical interfaces, not runtime objects.

Avoid:

```python
customers: Input["pl.DataFrame"]
```

Prefer:

```python
customers: Input[Customer]
```

Execution plugins determine the physical representation.

## Relationship to Pydantic

ETLantic builds on ContractModel and Pydantic rather than replacing them.

Pydantic provides:

- Field types
- Validation
- Constraints
- Metadata

ETLantic consumes those definitions through `Data`.

## Best Practices

- Prefer explicit types.
- Use `Annotated` for constraints and descriptions.
- Reference contract models rather than dataframe types.
- Use enums for finite choices.
- Keep annotations focused on logical interfaces.

## Anti-Patterns

Avoid:

- `Any` where a specific type is known.
- Embedding execution-engine classes in interfaces.
- Repeating schema information already defined by data contracts.
- Using untyped dictionaries for configuration.

## Key Principle

> Type annotations are the single source of truth for ETLantic interfaces.
> Everything else should be derived from them whenever practical.

## Next Step

Continue with **IMPLEMENTATIONS.md** to learn how typed transformation
interfaces are bound to one or more execution backends.
