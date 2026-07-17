# Core Concepts

ETLantic is easiest to understand as a sequence of distinct models rather
than as one large framework object.

## The Complete Lifecycle

```text
Data contracts + transformation contracts + pipeline contract
                          ↓
                 Typed logical model
                          ↓
                     Validation
                          ↓
               Profile and bindings
                          ↓
                    PipelinePlan
                          ↓
            Execute, compile, or generate
                          ↓
                 Results and evidence
```

Each stage answers a different question.

## Data Contract

A data contract describes valid data.

In the code-first experience, `Data` is ETLantic's public facade over a
ContractModel-compatible Pydantic class:

```python
from etlantic import Data


class Customer(Data):
    customer_id: int
    full_name: str
```

ContractModel owns operational behavior such as runtime validation and ODCS
interoperability. ETLantic uses the class as a typed dataset boundary.

## Transformation

A transformation is a reusable typed interface describing how data is expected
to change:

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]
```

The declaration defines ports and parameters. DTCS defines its portable
semantics. It does not commit the transformation to a dataframe engine.

### Portable Definition (0.11+ design)

!!! warning "Accepted 0.11+ design—not available in ETLantic 0.10"
    `etlantic.transform`, `@Transformation.portable`, and portable compilers
    are documented future design. Do not import them in 0.10 code. Use
    `@Transformation.implementation(...)` today.

A portable definition will describe common relational behavior once using
PySpark-inspired symbolic DataFrame and Column expressions:

```python
from etlantic.transform import functions as F


@NormalizeCustomers.portable
def normalize(customers, minimum_age):
    return customers.filter(F.col("age") >= minimum_age)
```

ETLantic will normalize this definition into the canonical DTCS Transformation
Plan (`dtcs.transform-plan/2`, with v1 readable) through the public `dtcs`
package. Plugins will compile that plan to native operations. The definition
does not process data and is not a native implementation.

## Implementation

An implementation satisfies a transformation for a specific execution
technology:

```python
@NormalizeCustomers.implementation("polars")
def normalize_polars(customers, minimum_age):
    ...
```

One transformation may have multiple implementations. The planner selects a
compatible implementation for the chosen profile.

Native implementations remain the explicit escape hatch for behavior outside
the portable language or for approved backend-specific optimization.

## Port

A port is a named, typed transformation boundary:

- `Input[T]` consumes data governed by `T`.
- `Output[T]` produces data governed by `T`.
- `Parameter[T]` configures behavior but does not create a data-flow edge.

Ports make compatibility and lineage explicit.

## Pipeline

A pipeline is a portable logical graph:

```python
class CustomerPipeline(Pipeline):
    raw: Source[RawCustomer] = Source(binding="customer_source")
    normalized = NormalizeCustomers.step(customers=raw)
    curated: Sink[Customer] = Sink(
        input=normalized.result,
        binding="customer_sink",
    )
```

DPCS defines the portable pipeline contract. The Python class is the preferred
code-first authoring surface.

## Source, Step, and Sink

### Source

A `Source[T]` introduces a logical dataset into the graph. Its binding says
where an environment obtains the data.

### Step

A `Step` is one use of a reusable transformation inside a pipeline. Two steps
may use the same transformation with different inputs or parameters.

### Sink

A `Sink[T]` publishes data governed by `T`. A storage plugin performs the
physical write.

## Subpipeline

A subpipeline exposes a stable public interface while hiding internal nodes.
It supports composition, reuse, independent validation, and team ownership.

Parent pipelines bind to public subpipeline ports rather than private internal
steps.

## Logical Graph

The logical graph is the user-visible topology of sources, steps, outputs,
sinks, dependencies, and contracts.

It is stable across execution backends.

## Profile

A profile binds portable names to an environment:

- Orchestrator
- Default transformation engine
- Source and sink implementations
- Resource providers
- Concurrency limits
- Backend options
- Portable-versus-native implementation policy

Profiles may choose how a pipeline runs. They may not change what the pipeline
means.

## Binding

A binding connects a logical name to a concrete implementation:

```text
customer_source
    → PostgreSQL table in production
    → local Parquet file in development
```

Bindings belong to profiles and configuration, not portable contracts.

## Capability

A capability is a feature a plugin can preserve, such as:

- Async execution
- Streaming
- Transactions
- Checkpoints
- Dynamic task mapping
- SQL window functions
- Spark watermarks
- Portable transformation operations, functions, types, and semantic modes

Planning compares required semantics with available capabilities.

## PipelinePlan

`PipelinePlan` is the immutable, resolved intermediate representation produced
by planning.

It contains:

- Resolved implementations
- Portable definition and compiler fingerprints when selected
- Resolved bindings
- Dependency order
- Execution regions
- Materialization boundaries
- Capability decisions
- Resource references

It does not contain resolved secrets or live runtime objects.

## Execution Region

An execution region is a group of compatible logical nodes realized together by
one backend.

For example, three logical SQL-capable steps may compile into one statement,
while still retaining mappings back to all three logical identities.

## Plugin

A plugin extends ETLantic with backend behavior:

- Dataframe execution
- SQL or Spark execution
- Orchestration
- Storage
- Compilation

Plugins do not redefine pipeline semantics.

## Resource Provider

A resource provider acquires and cleans up a managed dependency such as a
database connection, Spark session, HTTP client, secret manager, or cache.

Logical models request resources by name or type. Providers resolve them at
runtime.

## Artifact

The term artifact has two related uses:

### Generated artifact

A file derived from a model or plan, such as ODCS, DTCS, DPCS, documentation,
or an Airflow DAG.

### Runtime data artifact

A value or reference passed between physical execution units, such as an
in-memory dataframe, database relation, Parquet location, Arrow table, or
plugin-native handle.

Context should make the meaning clear.

## Callback and Action

A callback responds to a lifecycle event. It receives typed context and may
return a declarative action:

```text
Invalid data → reject, drop, quarantine, continue with valid rows, or fail
Execution failure → retry, skip, fail node, fail pipeline, or use a fallback
```

The active backend carries out the action.

## Diagnostic

A diagnostic is a structured finding with a stable code, severity, message,
source location, logical path, and optional remediation.

Expected model errors produce diagnostics. Exceptions are reserved for API,
infrastructure, plugin, or invariant failures.

## Compilation

Compilation transforms a `PipelinePlan` into a backend artifact without making
that artifact the source of truth.

Examples include:

- Airflow DAG source
- SQL scripts
- Spark job configuration
- Deployment bundles

## Result and Evidence

Execution produces structured results and evidence:

- Pipeline and node states
- Attempts and timing
- Diagnostics
- Invalid-data counts
- Lineage events
- Generated or persisted artifacts

Observed evidence can be compared with declared contracts, but it does not
silently rewrite them.

## Responsibility Map

| Responsibility | Owner |
|---|---|
| Data-contract semantics | ODCS |
| Data-contract operationalization | ContractModel |
| Transformation semantics | DTCS |
| Pipeline semantics | DPCS |
| Typed authoring and logical graph | ETLantic |
| Validation and planning | ETLantic |
| Runtime adaptation | Plugins |
| Actual computation and scheduling | External engines |

## Next Step

Continue with [Architecture](ARCHITECTURE.md) to see how these concepts are
organized into implementation layers.
