# FastAPI Philosophy

## Why FastAPI?

ETLantic is heavily inspired by FastAPI---not because it serves
HTTP APIs, but because it demonstrates how Python's type system can
become the foundation of an exceptional developer experience.

FastAPI showed that developers can describe an interface using ordinary
Python classes and type annotations while the framework automatically
provides validation, documentation, editor support, and runtime
behavior.

ETLantic applies that same philosophy to data engineering.

## The Central Idea

FastAPI asks developers to describe an API.

ETLantic asks developers to describe a pipeline.

Everything that can be derived from those descriptions should be derived
automatically.

``` text
FastAPI

Python Types
      │
      ▼
Validation
OpenAPI
Documentation
Runtime Routing


ETLantic

Python Types
      │
      ▼
Validation
ODCS
DTCS
DPCS
Documentation
Execution Planning
Visualization
```

The goal is not to copy FastAPI's implementation. The goal is to adopt
its design philosophy.

## Types Are the Source of Truth

ETLantic avoids duplicate configuration whenever possible.

Instead of maintaining Python code, YAML, diagrams, and documentation
independently, developers define strongly typed Python models.

Those models become the authoritative description of the pipeline.

For example:

``` python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]
```

From these annotations ETLantic can infer:

-   transformation inputs
-   transformation outputs
-   parameter definitions
-   validation rules
-   documentation
-   DTCS contracts
-   editor tooling

## Declarative Instead of Imperative

Pipeline authors describe *what* exists rather than *how* to execute it.

A pipeline definition is a logical model.

Execution details belong to plugins.

``` python
class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(asset="customer_source")

    normalized = NormalizeCustomers.step(
        customers=raw,
    )

    curated: Load[Customer] = Load(
        input=normalized.result,
        binding="customer_sink",
    )
```

The pipeline above describes relationships between contracts and
transformations. It does not dictate how they are scheduled or executed.

## Minimize Boilerplate

A guiding principle of ETLantic is:

> Never ask the developer to repeat information that can be inferred
> safely.

Examples include:

-   Generating contracts from Python models
-   Inferring validation rules from type annotations
-   Discovering pipeline topology from node relationships
-   Producing diagrams from the logical graph

## Sync and Async Should Feel the Same

FastAPI allows developers to write either `def` or `async def` endpoint
functions.

ETLantic adopts the same experience for transformation
implementations, callbacks, and resources.

``` python
@NormalizeCustomers.implementation("polars")
def normalize(df):
    ...
```

``` python
@NormalizeCustomers.implementation("remote")
async def normalize(df):
    ...
```

The framework normalizes invocation internally so users focus on
business logic rather than concurrency primitives.

## Great Tooling Comes Naturally

When the type system is the source of truth, rich tooling becomes
possible:

-   autocomplete
-   static analysis
-   generated documentation
-   diagnostics
-   contract generation
-   visualization

These capabilities emerge from the model rather than requiring
additional configuration.

## ETLantic Is Not FastAPI for ETL

ETLantic is inspired by FastAPI's philosophy, not limited by its
domain.

It introduces concepts unique to data engineering:

-   Data Contracts
-   Transformation Contracts
-   Pipeline Contracts
-   Execution Profiles
-   Plugin Bindings
-   Execution Planning

The result is a framework tailored specifically to contract-driven
pipeline development.

## Guiding Principle

Every new feature should answer a simple question:

> Does this make authoring typed, contract-driven pipelines simpler,
> clearer, or more expressive?

If the answer is yes, it probably belongs in ETLantic.

If it concerns execution mechanics alone, it likely belongs in an
execution plugin instead.

## Next Step

Continue with **DESIGN_PRINCIPLES.md** to learn the architectural rules
that guide every ETLantic design decision.
