# Pydantic Integration

ETLantic relies on Pydantic through ContractModel rather than introducing a second data-modeling system.

Pydantic provides the Python-native type system, field metadata, validation behavior, and schema introspection used by `Data`. ContractModel extends that experience with data-contract semantics and [ODCS](ODCS.md) interoperability. ETLantic then consumes those contract classes as typed pipeline interfaces.

The relationship is:

```text
Python Type Annotations
          │
          ▼
       Pydantic
          │
          ▼
     ContractModel
          │
          ▼
ODCS-Compatible Data Contracts
          │
          ▼
     ETLantic
```

## Architectural Boundary

Each layer has a distinct responsibility.

### Pydantic

Pydantic owns:

- Python model construction
- Field parsing
- Field validation
- Defaults
- Aliases
- Validators
- Model serialization
- JSON Schema generation
- Type-driven editor support

### ContractModel

ContractModel owns:

- `Data`
- Data-contract metadata
- ODCS mappings
- Contract identity
- Runtime contract validation
- Compatibility analysis
- Data-contract generation and loading
- Data-contract-specific diagnostics

### ETLantic

ETLantic owns:

- Referencing data contracts from transformations
- Referencing data contracts from `Extract` and `Load` steps
- Validating pipeline wiring
- Coordinating validation boundaries
- Discovering contracts used by a pipeline
- Generating pipeline-wide contract bundles
- Passing contract requirements to execution plugins

ETLantic must not reimplement Pydantic field parsing or validation behavior.

## Basic Model Definition

A ETLantic-ready data contract is an ordinary ContractModel class:

```python
from etlantic import Data
from etlantic.contracts import load_data_contract


class Customer(Data):
    customer_id: int
    name: str
    email: str | None = None
```

The model should behave like a Pydantic model:

```python
customer = Customer(
    customer_id=42,
    name="Ada Lovelace",
)
```

The same class is usable as a logical pipeline type:

```python
from etlantic import Input, Output, Transformation


class NormalizeCustomers(Transformation):
    customers: Input[Customer]
    result: Output[Customer]
```

## Type Annotations

ETLantic should preserve standard Python and Pydantic typing conventions.

Supported annotations should include, where ContractModel and ODCS can represent them reliably:

- Primitive types
- Optional types
- Unions
- Literals
- Enums
- Lists
- Sets
- Tuples
- Dictionaries
- Nested models
- Dates and times
- UUIDs
- Decimal values
- Constrained values through `Annotated`

Example:

```python
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from etlantic import Data
from etlantic.contracts import load_data_contract


class Order(Data):
    order_id: UUID
    order_date: date
    total: Decimal
    status: Literal["pending", "paid", "cancelled"]
    tags: list[str] = []
```

ContractModel determines how these Python types map into ODCS.

ETLantic treats the resulting contract as authoritative.

## `Annotated`

`Annotated` is the preferred mechanism for attaching field constraints and documentation.

```python
from typing import Annotated

from pydantic import Field


class Customer(Data):
    customer_id: Annotated[
        int,
        Field(
            strict=True,
            gt=0,
            description="Stable customer identifier.",
        ),
    ]

    email: Annotated[
        str,
        Field(
            description="Primary email address.",
            min_length=3,
        ),
    ]
```

This style keeps the Python type visible while allowing additional metadata to travel with it.

ETLantic should reuse this information for:

- Generated documentation
- ODCS generation
- Validation diagnostics
- Compatibility checks
- Transformation interface documentation
- Pipeline diagrams and inspection tools

## Required Fields

A field without a default is required:

```python
class Customer(Data):
    customer_id: int
    email: str
```

ETLantic should not invent separate required-field metadata.

It should rely on Pydantic and ContractModel.

## Optional and Nullable Fields

Optionality should follow normal Python and Pydantic semantics.

```python
class Customer(Data):
    customer_id: int
    email: str | None = None
```

ContractModel must distinguish, where relevant, between:

- A field that is required but may contain null
- A field that is optional and may be omitted
- A field with a default value
- A field that is both nullable and defaulted

ETLantic should consume the normalized ContractModel interpretation rather than inferring these details independently.

## Defaults

Defaults remain ordinary Pydantic defaults:

```python
class Customer(Data):
    customer_id: int
    active: bool = True
```

Default factories should also remain available:

```python
from pydantic import Field


class Customer(Data):
    customer_id: int
    tags: list[str] = Field(default_factory=list)
```

Generated contracts should represent defaults only when the target standard can express them safely.

## Constraints

Pydantic field constraints should flow into contract metadata whenever possible.

Examples:

```python
class Customer(Data):
    age: Annotated[
        int,
        Field(ge=0, le=130),
    ]

    username: Annotated[
        str,
        Field(min_length=3, max_length=50),
    ]
```

Constraint handling falls into three categories:

### Portable constraints

These can be represented in ODCS and enforced across multiple runtimes.

Examples may include:

- minimum and maximum values
- minimum and maximum lengths
- required fields
- nullability
- regular-expression patterns
- enumerated values

### Python-only constraints

These depend on arbitrary Python logic and may not be portable.

### Engine-specific constraints

These can be pushed down into a particular runtime, such as SQL or Polars, but may not be universally supported.

ContractModel should classify these capabilities.

ETLantic should surface unsupported enforcement during planning.

## Strict Validation

Strict validation should remain available:

```python
class Customer(Data):
    customer_id: Annotated[
        int,
        Field(strict=True),
    ]
```

This prevents coercion such as converting `"42"` into `42`.

Profiles may choose different physical validation strategies, but they must not silently weaken declared contract semantics.

If an execution plugin cannot enforce strict typing directly, it must either:

- delegate to ContractModel
- perform a safe conversion followed by ContractModel validation
- report the capability gap
- refuse execution when required by policy

## Field Descriptions

Descriptions should be defined once and reused everywhere:

```python
class Customer(Data):
    customer_id: Annotated[
        int,
        Field(
            description="Stable identifier assigned by the customer system.",
        ),
    ]
```

ETLantic may include this description in:

- Generated ODCS
- Transformation documentation
- Pipeline documentation
- Graph inspection
- CLI output
- Visual editors
- Lineage views

## Examples

Pydantic field examples may also enrich generated documentation:

```python
class Customer(Data):
    email: Annotated[
        str,
        Field(
            description="Primary customer email.",
            examples=["ada@example.com"],
        ),
    ]
```

Examples are documentation metadata. They should not be treated as runtime defaults.

## Aliases

Aliases allow external names to differ from Python identifiers:

```python
class Customer(Data):
    customer_id: int = Field(alias="customerId")
```

ContractModel must define the canonical behavior for:

- Input validation
- Serialization
- ODCS field names
- Dataframe columns
- Database columns
- Compatibility checks

ETLantic should not independently choose whether to use the Python name or alias.

It should request the canonical contract field name from ContractModel.

## Serialization Aliases and Validation Aliases

Pydantic may allow different names for input and output.

When used, ContractModel must decide whether ODCS can represent the distinction.

ETLantic should treat unresolved naming ambiguity as a planning or compatibility diagnostic rather than guessing.

## Model Configuration

Pydantic model configuration should remain available through the normal Pydantic mechanisms.

Examples may include:

- strict mode
- alias behavior
- extra field behavior
- frozen models
- arbitrary type handling
- assignment validation

Not every Pydantic configuration option is meaningful for a portable data contract.

ContractModel should classify configuration as:

- contract-relevant
- Python-runtime-only
- unsupported for portable generation

ETLantic should only rely on the contract-relevant subset.

## Extra Fields

Pydantic can allow, ignore, or forbid extra fields.

This behavior has direct data-contract implications.

Example:

```python
from pydantic import ConfigDict


class Customer(Data):
    model_config = ConfigDict(extra="forbid")

    customer_id: int
    name: str
```

For pipeline validation:

- `forbid` means undeclared fields should cause failure
- `ignore` means extra fields may be discarded
- `allow` means undeclared fields may pass through

ContractModel should translate this behavior into ODCS or extension metadata where possible.

ETLantic should preserve the declared policy at validation boundaries.

## Nested Models

Nested Pydantic models should remain first-class:

```python
class Address(Data):
    street: str
    city: str
    postal_code: str


class Customer(Data):
    customer_id: int
    address: Address
```

ContractModel owns the mapping into ODCS structures.

ETLantic treats the top-level contract as the logical pipeline type while retaining access to nested schema metadata for documentation and compatibility analysis.

## Reusable Component Models

Not every nested Pydantic model needs to be a published data contract.

Teams may define reusable internal models:

```python
from pydantic import BaseModel


class Address(BaseModel):
    street: str
    city: str


class Customer(Data):
    customer_id: int
    address: Address
```

ContractModel should distinguish:

- published data contracts
- embedded schema components
- internal helper models

ETLantic should only generate standalone ODCS documents for published contracts.

## Enums

Enums should map naturally into allowed values:

```python
from enum import StrEnum


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Customer(Data):
    customer_id: int
    status: CustomerStatus
```

Generated ODCS should preserve the semantic values rather than Python member names unless ContractModel explicitly defines otherwise.

## Discriminated Unions

Pydantic discriminated unions may represent polymorphic records.

```python
from typing import Annotated, Literal

from pydantic import Field


class CardPayment(Data):
    payment_type: Literal["card"]
    last_four: str


class BankPayment(Data):
    payment_type: Literal["bank"]
    account_id: str


Payment = Annotated[
    CardPayment | BankPayment,
    Field(discriminator="payment_type"),
]
```

ContractModel must determine whether the target ODCS version supports the equivalent structure.

ETLantic should report unsupported portability rather than flattening the union silently.

## Custom Field Types

Custom Pydantic-compatible types may be used:

```python
class CustomerId(str):
    ...
```

For portable contracts, ContractModel needs a documented mapping to:

- ODCS logical types
- primitive representations
- validation constraints

Unknown custom types should produce explicit diagnostics during contract generation or planning.

## Field Validators

Pydantic field validators can normalize or validate values:

```python
from pydantic import field_validator


class Customer(Data):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()
```

A Python validator may perform either:

- normalization
- validation
- both

This distinction matters.

A contract should ideally describe required semantics without depending entirely on hidden Python code.

ContractModel should expose whether a validator is:

- portable
- documented only
- Python-only
- execution-engine-specific

ETLantic should not assume a Python-only validator can run inside SQL, Polars, Spark, or another external engine.

## Model Validators

Cross-field validation may use model validators:

```python
from pydantic import model_validator


class DateRange(Data):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self
```

Cross-field rules are often important contract semantics but may be difficult to push down into every execution engine.

ETLantic should allow planning policies such as:

- validate through ContractModel after materialization
- use a plugin-native equivalent
- reject an execution profile that cannot enforce the rule
- allow sampled validation when explicitly configured

## Computed Fields

Computed fields should be used carefully.

A computed Pydantic field may be:

- documentation-only
- serialized output
- derived data
- a transformation concern

If a field is materially derived from other fields, it may belong in a transformation contract rather than a data contract model.

A useful rule is:

> Data contracts describe the shape and guarantees of data. Transformations describe how derived values are produced.

## Private Attributes

Private Pydantic attributes are implementation details and must not become part of:

- ODCS
- transformation interfaces
- pipeline wiring
- compatibility analysis

ETLantic should ignore private attributes.

## Generic Models

Generic Pydantic models may be useful for reusable containers:

```python
from typing import Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
```

Before a generic model can serve as a published pipeline data contract, it should be fully specialized.

ETLantic should not accept unresolved type variables as contract boundaries.

## Root Models

Pydantic root models may represent contracts whose top-level value is not an object.

Examples include:

- a list of records
- a scalar value
- a mapping

ContractModel must define whether and how these map into ODCS.

ETLantic should support them only when:

- ContractModel exposes a valid data-contract identity
- the active execution plugin supports the representation
- the pipeline boundary semantics are unambiguous

## Dataclasses

Pydantic dataclasses may be supported through ContractModel adapters, but `Data` should remain the recommended authoring surface.

A consistent base class makes contract identity, metadata, generation, and loading easier to reason about.

## JSON Schema

Pydantic can generate JSON Schema.

JSON Schema is useful for:

- editor tooling
- validation
- generated forms
- API integration
- documentation

However, JSON Schema is not a replacement for ODCS.

The relationship is:

```text
Pydantic Model
    ├── JSON Schema
    └── ODCS Data Contract
```

Each artifact serves a different purpose.

ContractModel should own both mappings.

ETLantic may expose generated schemas through inspection and documentation APIs.

## Runtime Record Validation

Pydantic is optimized for validating Python objects and records.

Example:

```python
customer = Customer.model_validate(
    {
        "customer_id": 42,
        "name": "Ada",
    }
)
```

For large dataframe workloads, row-by-row Pydantic validation may be too expensive.

ETLantic should allow execution plugins to provide optimized validation while preserving the same declared semantics.

## Dataframe Validation

A dataframe plugin may translate Pydantic and ContractModel metadata into native expressions.

For example, a Polars plugin may compile:

```python
age: Annotated[int, Field(ge=0, le=130)]
```

into a native validation expression.

A Pandas plugin may use vectorized masks.

A SQL plugin may generate predicates or constraints.

The plugin must report which constraints it can enforce natively.

Unsupported constraints must not disappear silently.

## Validation Fallback

When a plugin cannot enforce a contract fully, ETLantic may:

1. Materialize records.
2. Delegate validation to ContractModel or Pydantic.
3. Collect structured failures.
4. Apply invalid-data policy.
5. Continue or fail according to configuration.

This fallback preserves correctness at the cost of performance.

## Schema Pushdown

Where supported, ETLantic may ask plugins to push contract validation closer to the source.

Examples include:

- SQL predicates
- database constraints
- Parquet schema checks
- Arrow schema checks
- Polars expressions

Pushdown is an optimization.

The Pydantic and ContractModel declaration remains the semantic source of truth.

## Transformation Inputs and Outputs

Pydantic-backed data contract classes appear inside ETLantic annotations:

```python
class AggregateOrders(Transformation):
    orders: Input[Order]
    summary: Output[OrderSummary]
```

ETLantic should introspect these types through ContractModel's public API.

It should not inspect Pydantic internals directly.

## Type Compatibility

Two Python models are not necessarily compatible merely because they share fields.

Compatibility should consider:

- Contract identity
- Contract version
- Required fields
- Nullability
- Field types
- Constraints
- Aliases
- Defaults
- Semantic metadata
- Compatibility policy

ContractModel owns this analysis.

ETLantic uses the result to validate graph edges.

## Dynamic Models

Pydantic can create models dynamically.

Dynamic models may be useful when loading ODCS:

```python
Customer = load_data_contract(
    "customer.odcs.yaml",
)
```

ETLantic should treat dynamically generated and statically authored models equivalently when they satisfy the ContractModel public interface.

## Generated Python Source

ContractModel may optionally generate Python source from ODCS rather than only dynamic classes.

That supports:

- version control
- static type checking
- editor navigation
- code review
- reproducible builds

ETLantic should be compatible with either approach.

## Model Rebuilding

Forward references and recursive types may require Pydantic model rebuilding.

ContractModel should ensure loaded or authored models are fully resolved before ETLantic uses them as pipeline boundaries.

Unresolved forward references should produce clear model-definition diagnostics.

## Static Type Checking

ETLantic should preserve as much static typing as possible.

For example:

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]
```

Static tooling should be able to determine:

- the logical contract of `customers`
- the logical contract of `result`
- whether a pipeline connection is compatible
- which output ports exist

Some advanced typing may require a mypy or Pyright plugin in future releases, but the public API should remain understandable without one.

## Introspection API

ContractModel should expose a stable normalized view of a Pydantic-backed contract.

Conceptually:

```python
info = inspect_data_contract(Customer)

info.identity
info.fields
info.constraints
info.metadata
info.odcs_version
```

ETLantic should depend on this normalized interface rather than:

- `model_fields` directly
- private Pydantic internals
- undocumented metadata storage
- raw JSON Schema alone

This boundary protects ETLantic from Pydantic and ContractModel implementation changes.

## Version Compatibility

ETLantic and ContractModel should define supported Pydantic major versions explicitly.

A suggested policy is:

- Support one active Pydantic major version at a time.
- Treat Pydantic internals as private.
- Test against the minimum and latest supported minor versions.
- Keep ETLantic integration behind ContractModel's public API.
- Document breaking changes before upgrading the required Pydantic major version.

## Error Translation

Pydantic validation errors should be translated into ETLantic's structured invalid-data diagnostics.

The resulting event should preserve:

- field path
- error code
- message
- invalid value when safe
- source node
- transformation or sink
- contract identity
- run identifier

Example conceptual flow:

```text
Pydantic ValidationError
        │
        ▼
ContractModel Validation Report
        │
        ▼
ETLantic normalized validation evidence
        │
        ▼
PipelineRunReport
```

ETLantic should not expose raw Pydantic exceptions as the only failure interface.

## Security and Sensitive Values

Validation diagnostics may contain sensitive data.

ETLantic and ContractModel should support:

- redacted values
- field-level sensitivity metadata
- safe logging defaults
- configurable diagnostic detail
- omission of secrets and personal data

Pydantic's error structures should be sanitized before being emitted to logs or external systems.

## Performance Considerations

Pydantic validation is valuable but should be applied deliberately in high-volume pipelines.

Recommended strategies include:

- native vectorized validation
- schema pushdown
- batch validation
- sampled validation where policy permits
- full validation at publication boundaries
- cached schema compilation
- avoiding repeated model introspection

ETLantic should make performance strategy explicit through profiles while preserving contract semantics.

## Recommended Practices

- Use `Data` for published pipeline datasets.
- Prefer `Annotated` with `Field` for constraints and documentation.
- Keep contract metadata explicit and versioned.
- Reuse Pydantic models directly in transformation annotations.
- Separate portable constraints from Python-only validators.
- Use aliases only with a documented canonical naming policy.
- Require fully resolved concrete models at pipeline boundaries.
- Let ContractModel provide normalized introspection.
- Let plugins optimize validation without redefining semantics.
- Translate Pydantic errors into structured pipeline diagnostics.

## Anti-Patterns

### Duplicating schemas

Avoid redefining the same fields in a transformation or pipeline node.

```python
## Avoid
class NormalizeCustomers(Transformation):
    input_columns = {
        "customer_id": int,
        "email": str,
    }
```

Prefer:

```python
class NormalizeCustomers(Transformation):
    customers: Input[Customer]
```

### Inspecting Pydantic internals in ETLantic

ETLantic should not depend directly on private Pydantic details.

### Treating all validators as portable

Arbitrary Python validators cannot automatically run in SQL, Polars, Spark, or remote services.

### Silent coercion

Execution plugins must not weaken strict contract requirements without an explicit policy.

### Using Pydantic models as dataframe containers

A `Data` describes record semantics. It should not force the physical dataframe representation.

## Key Principle

> Pydantic defines the Python model experience. ContractModel turns that model into an operational data contract. ETLantic uses the contract as a typed boundary across the pipeline.

## Next Step

Continue with **ODCS.md** to learn how ContractModel-backed Pydantic classes map to the Open Data Contract Standard and how ETLantic generates, loads, references, and versions ODCS artifacts.
