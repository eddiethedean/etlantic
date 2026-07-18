# PySpark

**Status: shipped in 0.7.0** via `etlantic-pyspark` (local Spark provider).
Managed cluster providers (Databricks/EMR/Connect) remain future adapters.
Structured Streaming APIs are **experimental**.

The PySpark execution backend enables ETLantic to execute eligible
transformations on Apache Spark using the same validated Pipeline Plans used by
every other execution backend.

PySpark execution is an implementation strategy, not a different pipeline
model. ODCS, DTCS, DPCS, contracts, transformation interfaces, lineage, and
validation semantics remain portable regardless of whether execution occurs on
Spark, SQL, Polars, Pandas, or another backend.

ETLantic's proposed portable transformation syntax is deliberately inspired by
PySpark's DataFrame and Column APIs. It uses ETLantic symbolic objects and
semantics rather than importing PySpark into core. The PySpark compiler is
ships in 0.13; native `@implementation("pyspark")` remains available.

## Goals

The PySpark backend should:

- Execute transformations on distributed datasets.
- Scale from local development to large clusters.
- Preserve contract semantics.
- Support Catalyst optimization.
- Support batch and streaming execution.
- Fall back to other implementations when required.

## Architecture

```text
Pipeline
    │
    ▼
Validation
    │
    ▼
Planning
    │
    ▼
Pipeline Plan (IR)
    │
    ▼
PySpark Execution Plugin
    │
    ▼
Spark Logical Plan
    │
    ▼
Catalyst Optimizer
    │
    ▼
Spark Runtime
```

## Transformation Implementations

Transformations remain backend independent.

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    lowercase_email: Parameter[bool] = True
    result: Output[Customer]
```

A Spark implementation may be registered independently.

```python
@NormalizeCustomers.implementation("pyspark")
def normalize_customers(...):
    ...
```

The planner selects the Spark implementation only when its capability
requirements are satisfied.

## Portable compiler (0.13)

```python
from etlantic.transform import functions as F


@NormalizeCustomers.portable
def normalize(customers, lowercase_email):
    email = F.lower(F.col("email"))
    return customers.withColumn("email", email)
```

`etlantic-pyspark` registers an `etlantic.transform_compilers` entry point that
claims `portable-relational-kernel/1` and `portable-relational/1`. It lowers
validated `dtcs.transform-plan/2` IR to native Spark DataFrame and Column
expressions so Catalyst can inspect and optimize them. Automatic Python or
Pandas UDF fallback is forbidden on the portable path (native
`@implementation("pyspark")` UDF policy remains separate). Portable steps use
the provider session from execution context and do **not** participate in
Spark region UDF fusion. If Spark cannot preserve an ETLantic semantic,
planning rejects the step or requires an explicit native implementation
policy.

Default CI exercises the compiler via sparkless; Catalyst-visible / no-UDF
acceptance runs under a gated real-PySpark job (`SPARKLESS_TEST_MODE=pyspark`).

## Planner Selection

The planner should prefer PySpark when:

- A compatible PySpark implementation exists.
- Distributed execution is beneficial or required.
- Required Spark capabilities are available.
- Contract validation can be preserved.
- The selected execution profile requests Spark.

Otherwise another implementation such as SQL or Polars may be selected.

## Spark Optimizations

The backend should preserve Spark's native optimization opportunities,
including:

- Catalyst query optimization
- Predicate pushdown
- Projection pruning
- Broadcast joins
- Partition pruning
- Lazy execution
- Whole-stage code generation
- Adaptive Query Execution (AQE)

These optimizations must never change observable pipeline behavior.

## Batch and Streaming

The same logical pipeline may execute in:

- Batch mode
- Structured Streaming

Streaming support depends on plugin capabilities and transformation semantics.

## Materialization

Spark should remain lazy whenever possible.

Materialization should occur only at intentional boundaries such as:

- Sink publication
- Checkpoints
- Validation gates
- Backend transitions
- Explicit caching or persistence

## Validation

Contracts remain authoritative.

Validation may be implemented using:

- Spark schema inspection
- Native Spark expressions
- Validation datasets
- Quarantine datasets
- ContractModel fallback validation

## Diagnostics

Execution diagnostics should include:

- Pipeline identity
- Step identity
- Spark application ID
- Stage identifiers
- Partition information
- Execution duration
- Rows processed
- Backend exceptions

## Supported Environments

A PySpark plugin may target:

- Local Spark
- Standalone Spark
- Kubernetes
- YARN
- Databricks
- Amazon EMR
- Google Dataproc
- Azure Synapse

Execution environments should not affect logical pipeline semantics.

## Best Practices

- Prefer native Spark expressions over Python UDFs.
- Keep transformation contracts backend independent.
- Let the planner choose Spark execution.
- Preserve validation boundaries.
- Minimize unnecessary materialization.
- Use Resource Providers for Spark sessions and cluster configuration.

## Anti-Patterns

Avoid:

- Embedding native Spark code in portable definitions or pipeline declarations.
- Calling Spark actions unnecessarily.
- Using Python UDFs when native expressions exist.
- Bypassing contract validation.
- Assuming cluster-specific behavior.

## Key Principle

> PySpark is a distributed execution backend for ETLantic. It executes the
same validated Pipeline Plans using Apache Spark while preserving portable
contracts, validation, lineage, diagnostics, and execution semantics.

## Next Step

Continue with **PYSPARK_EXECUTION.md** for the detailed execution lifecycle,
planning, optimization, and runtime behavior of the PySpark backend.
