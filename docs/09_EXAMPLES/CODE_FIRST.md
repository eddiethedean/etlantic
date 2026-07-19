# Code-First Pipeline

!!! warning "Future design—not a ETLantic 0.14 API guide"
    This page is a design study. It may describe packages, commands, or
    interfaces beyond the shipped API surface. Prefer Current Capabilities,
    the runnable examples under `examples/`, the API reference, and the CLI
    reference for installable behavior.


This example demonstrates the complementary workflow to **CONTRACT_FIRST.md**.
Instead of authoring ODCS, DTCS, and DPCS documents first, developers begin
with strongly typed Python classes and allow ETLantic to generate portable
contracts automatically.

## Philosophy

```text
Python Models
      │
      ▼
Validation
      │
      ▼
Normalized Pipeline Model
      │
      ├──► ODCS
      ├──► DTCS
      ├──► DPCS
      ├──► Documentation
      ├──► Mermaid
      └──► Execution Plan
```

The normalized model is the canonical internal representation. Code-first and
contract-first converge to the same planning, validation, lineage, and execution
pipeline.

## Goals

A code-first project should allow developers to:

1. Define data contracts as Python classes.
2. Define transformations using typed inputs, outputs, and parameters.
3. Define pipelines with sources, steps, subpipelines, and sinks.
4. Bind execution implementations (Polars, Pandas, SQL, PySpark, etc.).
5. Validate the complete graph.
6. Generate ODCS, DTCS, and DPCS artifacts.
7. Publish those artifacts to a registry.
8. Generate documentation, lineage, OpenAPI-style pipeline descriptions,
   Mermaid diagrams, and implementation reports.

## Project Layout

```text
customer_pipeline/
├── src/
│   ├── contracts.py
│   ├── transformations.py
│   ├── implementations.py
│   ├── pipeline.py
│   └── profiles.py
├── contracts/
├── docs/
└── tests/
```

## Data Contracts

```python
from typing import Annotated
from pydantic import Field
from etlantic import DataContractModel

class RawCustomer(DataContractModel):
    customer_id: int
    first_name: str
    last_name: str
    email: str | None

class Customer(DataContractModel):
    customer_id: Annotated[int, Field(gt=0)]
    full_name: str
    email: str
```

## Transformation

```python
from etlantic import Input, Output, Parameter, Transformation

class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    lowercase_email: Parameter[bool] = True
    result: Output[Customer]
```

## Implementation

```python
@NormalizeCustomers.implementation("polars")
def normalize(customers: pl.LazyFrame,
              lowercase_email: bool) -> pl.LazyFrame:
    ...
```

## Pipeline

```python
class CustomerPipeline(Pipeline):
    raw = Source[RawCustomer](binding="customers_input")

    normalized = NormalizeCustomers.step(
        customers=raw,
        lowercase_email=True,
    )

    curated = Sink[Customer](
        input=normalized.result,
        binding="customers_output",
    )
```

## Validation

```python
report = CustomerPipeline.validate()
report.raise_for_errors()
```

Validation verifies contracts, graph integrity, implementations, profiles,
resource bindings, compatibility, and execution capabilities.

## Planning

```python
plan = CustomerPipeline.plan(profile=production)
```

The resulting Pipeline Plan is identical to the plan produced by the
contract-first workflow.

## Contract Generation

```python
CustomerPipeline.write_contracts("contracts/")
```

Expected output:

```text
contracts/
├── data/
│   ├── raw-customer.odcs.yaml
│   └── customer.odcs.yaml
├── transformations/
│   └── normalize-customers.dtcs.yaml
└── pipelines/
    └── customer-pipeline.dpcs.yaml
```

Generated artifacts should be deterministic so that repeated generation produces
stable diffs suitable for CI.

## Publishing

```python
CustomerPipeline.publish_contracts(
    registry="company-registry",
)
```

Registries may perform compatibility checks, version validation, signing,
approval workflows, and search indexing.

## Documentation

```python
plan.write_html("docs/pipeline.html")
plan.write_mermaid("docs/pipeline.mmd")
```

## Round-Trip Guarantee

A core design goal is:

```text
Python
  │
  ▼
ODCS / DTCS / DPCS
  │
  ▼
Load Again
  │
  ▼
Equivalent Normalized Model
```

The generated contracts should be semantically equivalent to the original
Python definitions.

## CI Workflow

1. Run validation.
2. Generate contracts.
3. Verify generated artifacts are current.
4. Validate implementation conformance.
5. Execute tests.
6. Publish contracts and documentation.

## Best Practices

- Treat generated contracts as build artifacts.
- Commit generated contracts for public APIs.
- Keep implementation code separate from generated outputs.
- Use explicit semantic versions.
- Validate before generating.
- Publish only validated contracts.
- Test round-trip equivalence.

## Anti-Patterns

Avoid:

- Editing generated contracts manually.
- Publishing contracts from invalid pipelines.
- Mixing environment-specific bindings into portable contracts.
- Skipping compatibility checks.
- Depending on generation order or formatting differences.

## Relationship to Contract-First

Contract-first is ideal when contracts are governed externally or shared across
multiple languages.

Code-first is ideal when Python is the primary authoring environment and
developers want rapid iteration with strong typing.

Both workflows intentionally converge to the same normalized ETLantic,
Pipeline Plan, execution behavior, documentation, and portable contract
artifacts.
