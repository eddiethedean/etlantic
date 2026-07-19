# PySpark Execution

**Status: shipped in 0.7.0** for batch Spark via `etlantic-pyspark`. Streaming
callouts on this page are **experimental**.

The PySpark Execution subsystem defines how ETLantic executes validated
Pipeline Plans on Apache Spark.

PySpark execution converts Spark-capable regions of a Pipeline Plan into Spark
logical plans, coordinates resources and actions, preserves contract validation,
and reports structured runtime diagnostics.

Execution remains separate from pipeline modeling. The pipeline definition does
not change when moving between local Spark, Databricks, EMR, Kubernetes, YARN,
or another Spark environment.

## Purpose

PySpark execution is responsible for:

- Selecting registered PySpark transformation implementations
- Building Spark logical plans
- Preserving lazy execution
- Coordinating Spark actions
- Managing Spark sessions and resources
- Enforcing validation boundaries
- Supporting batch and Structured Streaming
- Reporting diagnostics and lineage
- Preserving DTCS and DPCS semantics

It is **not** responsible for:

- Defining transformation contracts
- Defining pipeline topology
- Replacing the planner
- Reinterpreting Python pipeline classes at runtime
- Silently weakening validation or failure behavior

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
Pipeline Plan
    │
    ▼
Spark Capability Analysis
    │
    ▼
PySpark Execution Region
    │
    ▼
Spark Logical Plan
    │
    ▼
Catalyst and AQE
    │
    ▼
Spark Runtime
```

The PySpark plugin consumes a validated Pipeline Plan or one of its
Spark-capable regions.

## Execution Lifecycle

A typical execution follows these phases:

1. Resolve the execution profile.
2. Acquire a Spark session.
3. Verify Spark and plugin capabilities.
4. Resolve Spark-compatible sources.
5. Build lazy transformation plans.
6. Apply required validation gates.
7. Materialize only at intentional boundaries.
8. Publish sinks.
9. Emit runtime lineage and diagnostics.
10. Release or return resources according to lifecycle policy.

## Transformation Implementations

Transformations remain portable.

```python
class BuildCustomerOrderSummary(Transformation):
    customers: Input[Customer]
    orders: Input[Order]
    result: Output[CustomerOrderSummary]
```

A PySpark implementation is registered separately:

```python
@BuildCustomerOrderSummary.implementation("pyspark")
def build_customer_order_summary(
    customers: SparkDataFrame[Customer],
    orders: SparkDataFrame[Order],
) -> SparkDataFrame[CustomerOrderSummary]:
    ...
```

`SparkDataFrame[T]` should be an SDK-facing typed wrapper or protocol around a
native PySpark `DataFrame`.

It communicates the governing data contract without replacing Spark's runtime
object.

## Native Spark Expressions

PySpark implementations should prefer native Spark column expressions.

```python
from pyspark.sql import functions as F


@NormalizeCustomers.implementation("pyspark")
def normalize_customers(
    customers: SparkDataFrame[RawCustomer],
    lowercase_email: bool,
) -> SparkDataFrame[Customer]:
    email = F.trim(F.col("email"))

    if lowercase_email:
        email = F.lower(email)

    return customers.select(
        F.col("customer_id"),
        F.concat_ws(
            " ",
            F.trim(F.col("first_name")),
            F.trim(F.col("last_name")),
        ).alias("full_name"),
        email.alias("email"),
    )
```

Native expressions preserve Catalyst optimization and reduce Python execution
overhead.

## Python UDFs

Python UDFs should be treated as a capability with explicit tradeoffs.

They may introduce:

- Serialization overhead
- Reduced optimizer visibility
- Worker startup cost
- Portability limitations
- Different null behavior
- Harder static analysis

The planner and documentation should distinguish:

- Native Spark expressions
- SQL expressions
- Scalar Python UDFs
- pandas UDFs
- Iterator pandas UDFs

A plugin should not claim equivalent optimization support for all categories.

## Spark-Capable Regions

The planner may group adjacent PySpark-capable steps into one Spark execution
region.

```text
FilterOrders
      │
      ▼
JoinCustomers
      │
      ▼
AggregateMetrics
```

may remain one lazy Spark logical plan.

The physical Spark plan may combine or reorder operations, but ETLantic
must preserve logical step identities for:

- Lineage
- Diagnostics
- Validation
- Documentation
- Compatibility analysis
- Runtime events

## Lazy Execution

PySpark transformations should remain lazy until an action is required.

Common accidental actions include:

- `collect()`
- `count()`
- `toPandas()`
- `show()`
- `take()`
- `first()`

Implementations should avoid actions unless they are part of declared semantics
or validation.

Planning must never trigger Spark actions.

## Intentional Actions

Actions may occur at boundaries such as:

- Sink publication
- Full validation
- Quality gates
- Checkpointing
- Backend transitions
- Explicit user-requested materialization
- Runtime metrics that require computation

The execution plan should make action boundaries inspectable.

## Sources

PySpark-compatible sources may include:

- Parquet
- Delta Lake
- Iceberg
- JDBC
- CSV
- JSON
- Kafka
- Cloud object storage
- Hive-compatible tables
- Catalog-managed tables

Sources remain logical `Extract[T]` bindings in the pipeline.

The profile and storage plugins resolve them into Spark reads.

## Source Pushdown

Where supported, the plugin should preserve:

- Predicate pushdown
- Projection pruning
- Partition pruning
- Aggregate pushdown
- JDBC query pushdown

Pushdown is an optimization and must preserve contract semantics.

## Sinks

PySpark-compatible sinks may include:

- Parquet
- Delta Lake
- Iceberg
- JDBC
- Kafka
- Catalog-managed tables
- Object storage

Sink behavior may support:

- Append
- Overwrite
- Partition overwrite
- Merge
- Upsert
- Complete replacement
- Checkpointed streaming writes

Write modes should be selected through bindings and profiles.

## Materialization Boundaries

The planner may introduce materialization when required by:

- A sink
- A quality gate
- A validation boundary
- Reuse by multiple branches
- A checkpoint
- A transition to SQL or Polars
- A failure or retry boundary
- Streaming state
- Cluster or job boundaries

Materialization may use:

- Cache
- Persist
- Checkpoint
- Temporary views
- Temporary tables
- Delta or Parquet staging
- Arrow batches
- Collected local values for small control data

The plan should explain why each boundary exists.

## Cache and Persist

Caching is an execution optimization.

The planner may recommend caching when:

- A dataframe is consumed by multiple downstream steps.
- Recomputing the lineage is expensive.
- Iterative algorithms reuse the same data.
- A quality gate and sink both require the same result.

The profile may configure storage levels.

Caching must not change observable semantics.

## Checkpointing

Checkpointing may be used to:

- Truncate long Spark lineage
- Support Structured Streaming
- Create retry boundaries
- Preserve stateful execution
- Improve fault recovery

The plugin should declare support for:

- Reliable checkpoints
- Local checkpoints
- Streaming checkpoints
- Checkpoint cleanup
- External checkpoint storage

Checkpoint locations belong in profiles or Resource Providers.

## Partitioning

The planner and plugin may reason about:

- Input partitioning
- Repartitioning
- Coalescing
- Range partitioning
- Hash partitioning
- Output partitioning
- Shuffle boundaries

Partition choices affect performance, not logical pipeline semantics.

Explicit partition requirements should be represented as execution requirements
when they affect correctness or resource constraints.

## Joins

The PySpark plugin may support:

- Inner joins
- Left joins
- Right joins
- Full joins
- Cross joins
- Left semi joins
- Left anti joins
- Broadcast joins
- Bucket-aware joins

Join semantics must match the transformation contract, especially for null keys
and duplicate rows.

## Broadcast Joins

The planner may select a broadcast join when:

- One side is sufficiently small.
- Spark capabilities support broadcasting.
- The profile permits it.
- Memory constraints are satisfied.

Hints should not be applied when they risk failure or semantic changes.

## Aggregations

Spark-native aggregations should preserve:

- Grouping keys
- Null behavior
- Numeric result types
- Decimal precision
- Determinism requirements
- Approximate versus exact semantics

Approximate aggregations must be explicit.

## Window Functions

The plugin should declare support for:

- Partitioning
- Ordering
- Ranking
- Lag and lead
- Row frames
- Range frames
- Aggregate windows
- Null treatment

Window semantics must remain compatible with DTCS.

## Type Mapping

The plugin maps ContractModel types to Spark SQL types.

Mappings may include:

- Byte
- Short
- Integer
- Long
- Float
- Double
- Decimal
- String
- Boolean
- Date
- Timestamp
- Timestamp without time zone
- Binary
- Array
- Map
- Struct

Mapping results should indicate:

- Exact
- Compatible
- Lossy
- Unsupported

Lossy mappings must not be accepted silently.

## Decimal Semantics

Financial and exact numeric fields require special care.

The plugin should preserve:

- Precision
- Scale
- Rounding
- Aggregate widening
- Overflow behavior

Spark may widen or alter decimal result types during expressions.

The output must still satisfy the declared contract.

## Timestamp Semantics

The plugin must account for:

- Spark session time zone
- Timestamp types
- Naive and zoned datetime mappings
- Parsing behavior
- Daylight-saving transitions
- Precision

Session time zone should be configured explicitly through the execution profile.

## Null Semantics

The plugin should preserve:

- Required and nullable fields
- Spark's null-safe equality
- Boolean three-valued logic
- Aggregate behavior
- Join behavior
- Sorting behavior
- Conditional expression behavior

SQL, Polars, Pandas, and Spark implementations should be tested for equivalent
contractual behavior.

## Schema Validation

The plugin may validate structure through Spark schemas.

Checks may include:

- Required columns
- Unexpected columns
- Data types
- Nullability
- Nested structs
- Arrays and maps
- Decimal precision
- Field order where relevant

Schema compatibility alone does not guarantee row-level validity.

## Row-Level Validation

Portable constraints may be compiled into Spark expressions.

Examples include:

```python
invalid = dataframe.filter(
    (F.col("customer_id") <= 0)
    | F.col("email").isNull()
)
```

The plugin may produce:

- Valid dataframe
- Invalid dataframe
- Validation counts
- Structured diagnostics

## Invalid-Data Splitting

Conceptually:

```text
Input Spark DataFrame
         │
         ├── Valid rows ─────► Continue
         │
         └── Invalid rows ───► Quarantine
```

Partial acceptance must be explicit in the validation policy.

The split should remain lazy until a downstream action requires execution.

## Custom Python Validators

Some ContractModel validators may not compile into Spark expressions.

Possible strategies include:

- Reject planning
- Use a pandas UDF
- Materialize a small dataset
- Apply sampled validation
- Run post-write verification
- Invoke ContractModel fallback

Fallback behavior must be explicit and visible in the plan.

## Quality Gates

Quality gates may require Spark actions.

Examples include:

- Invalid row count
- Duplicate count
- Freshness checks
- Null percentage
- Row-count thresholds
- Distribution checks

The planner should avoid duplicate scans by combining compatible metrics when
possible.

## Batch Execution

Batch execution processes bounded datasets.

The plugin should coordinate:

- Source reads
- Lazy transformation regions
- Validation actions
- Sink writes
- Retries
- Cleanup

Batch pipelines may run through Local Python, Airflow, or another orchestrator.

## Structured Streaming

Structured Streaming requires additional semantics.

The plugin should declare support for:

- Micro-batch mode
- Continuous processing where available
- Event time
- Watermarks
- Stateful aggregations
- Streaming joins
- Output modes
- Checkpointing
- Trigger configuration
- Exactly-once or at-least-once behavior

A batch-compatible transformation is not automatically streaming-compatible.

## Streaming Inputs and Outputs

Streaming sources may include:

- Kafka
- Cloud file streams
- Delta change data feed
- Socket or custom connectors

Streaming sinks may include:

- Kafka
- Delta Lake
- Console for development
- `foreachBatch`
- Custom sinks

The profile selects concrete bindings and trigger settings.

## Watermarks

Watermark semantics should be explicit.

A transformation may require:

- Event-time field
- Allowed lateness
- State eviction behavior
- Late-data policy

Watermarks affect observable results and therefore belong in the pipeline or
transformation semantics where standardized.

## Stateful Operations

Stateful Spark operations require:

- Checkpoint storage
- Recovery semantics
- State schema compatibility
- Version-aware upgrades
- Resource controls

The plugin must not treat stateful and stateless transformations as equivalent.

## Streaming Validation

Streaming validation may operate:

- Per micro-batch
- Per record
- Per event-time window
- Through aggregate quality metrics
- Through quarantine streams

Full-dataset validation may be impossible for unbounded input.

The validation policy must reflect that limitation explicitly.

## Orchestrator Integration

The PySpark plugin may run under:

- Local Python
- Airflow
- Dagster
- Prefect
- Argo Workflows
- Databricks Jobs
- Spark-submit
- EMR Steps

The orchestrator coordinates the Spark application.

The PySpark plugin owns Spark-specific execution behavior.

## Spark Session Provider

Spark sessions should be supplied through a Resource Provider.

Conceptually:

```text
PySpark Plugin
      │
      ▼
Spark Session Provider
      │
      ▼
SparkSession
```

The provider may configure:

- Master URL
- Application name
- Packages
- Catalogs
- Extensions
- Session time zone
- Shuffle partitions
- Authentication
- Cloud storage access
- Delta or Iceberg integration

## Session Lifecycle

Possible lifecycle policies include:

- One session per pipeline run
- One shared session per worker
- Externally managed session
- Remote session
- Databricks Connect session

The provider should expose ownership and cleanup semantics.

## Configuration

Profiles may configure Spark behavior.

Conceptually:

```python
Profile(
    transformation_engine="pyspark",
    spark={
        "adaptive_execution": True,
        "shuffle_partitions": 200,
        "session_timezone": "UTC",
    },
)
```

Environment-specific Spark configuration belongs in profiles and Resource
Providers.

## Dependency Distribution

PySpark execution may require distributing:

- Python packages
- Wheel files
- JARs
- Configuration files
- UDF dependencies
- Native libraries

The plugin should make dependency requirements inspectable during compilation.

## Compilation

The PySpark plugin may compile a Pipeline Plan into:

- A local execution graph
- A Python entry point
- Spark-submit arguments
- Databricks job tasks
- Cluster-specific deployment artifacts

Compilation must preserve DPCS semantics.

## Runtime Execution

Execution may use:

- In-process Spark sessions
- Remote Spark jobs
- Databricks Jobs API
- Spark Connect
- Cluster submission tools
- Orchestrator-specific operators

Backend-specific submission details should not leak into pipeline definitions.

## Actions and Job Boundaries

One Spark action may trigger multiple stages and tasks.

ETLantic should distinguish:

- Logical pipeline step
- Spark logical plan node
- Spark stage
- Spark task
- Spark action

Diagnostics and lineage should preserve mappings among these levels when
available.

## Failure Handling

Spark failures may occur at:

- Driver startup
- Session acquisition
- Source read
- Analysis
- Query planning
- Stage execution
- Task execution
- Shuffle
- Sink commit
- Streaming recovery
- Checkpoint loading

The plugin should classify failures into structured categories.

## Retryability

Potentially retryable failures include:

- Executor loss
- Transient network failure
- Temporary object-store failure
- Cluster startup failure
- Task fetch failure
- Rate limiting

Non-retryable failures often include:

- Analysis errors
- Missing columns
- Contract incompatibility
- Invalid transformation logic
- Unsupported types
- Permission errors

Retries must consider sink idempotency and streaming checkpoint state.

## Idempotency

The plugin should document whether sink operations are safe to retry.

Examples:

- Overwriting a deterministic path may be idempotent.
- Appending may duplicate records.
- Delta merge may be idempotent with stable keys and conditions.
- Kafka writes depend on connector guarantees.
- JDBC writes may require transaction or staging strategies.

Retry behavior belongs in the execution plan.

## Cancellation

Where supported, cancellation should propagate to:

- Spark jobs
- Job groups
- Streaming queries
- Remote submissions
- Cluster jobs

The plugin should use stable pipeline and step identities when assigning Spark
job groups.

## Diagnostics

Structured diagnostics may include:

- Pipeline identity
- Step identity
- Spark application ID
- Job group ID
- Job ID
- Stage ID
- Task attempt
- Query execution ID
- Streaming query ID
- Plugin version
- Spark version
- Failure category
- Backend exception
- Suggested remediation

Sensitive configuration values should be redacted.

## Observability

The plugin may emit:

- Step duration
- Job and stage duration
- Input rows
- Output rows
- Shuffle read and write
- Spill metrics
- Partition counts
- Cache usage
- Executor failures
- Streaming progress
- Watermark progress
- State-store metrics

Metrics supplement, but do not redefine, the logical pipeline model.

## Spark UI Integration

Where available, execution reports may link to:

- Spark application UI
- SQL query details
- Stage pages
- Streaming query pages
- Databricks run pages

Links are runtime metadata and should be access-controlled.

## Lineage

Logical lineage comes from the Pipeline Plan.

The PySpark plugin may enrich lineage with:

- Physical tables and paths
- Spark query execution IDs
- Streaming source offsets
- Sink commit versions
- Delta table versions
- Materialized checkpoint locations

Runtime lineage must not replace ODCS, DTCS, and DPCS relationships.

## Explain Plans

The plugin should support plan inspection.

Conceptually:

```python
compiled = plan.compile(
    target="pyspark",
)

print(compiled.explain(mode="formatted"))
```

Plan inspection should not execute the pipeline.

Possible modes may include:

- Simple
- Extended
- Codegen
- Cost
- Formatted

Availability depends on Spark version and runtime.

## Security

The plugin should follow secure defaults.

Requirements include:

- External credentials
- Redacted configuration
- Least-privilege storage access
- Safe dependency distribution
- Controlled UDF execution
- Restricted Spark UI exposure
- Secure temporary storage
- Safe logging
- No secrets in generated plans or documentation

## Version Compatibility

The plugin should publish compatibility metadata for:

- ETLantic
- Plugin SDK
- PySpark
- Spark
- Python
- Java
- Scala binary version where relevant
- Delta Lake
- Iceberg
- Hadoop connectors
- Cloud runtime versions

Planning should reject unsupported combinations before submission.

## Backend Equivalence

PySpark implementations should be tested against reference implementations.

Where practical:

- PySpark vs. Polars
- PySpark vs. SQL
- Batch vs. streaming micro-batch results
- Local Spark vs. remote Spark

Equivalent inputs should produce contract-compatible logical outputs.

## Determinism

Distributed execution may not guarantee row order.

Pipeline semantics should not assume ordering unless explicitly declared.

The plugin should document nondeterministic operations such as:

- Unordered aggregation collection
- Random sampling
- Partition-dependent ordering
- Approximate algorithms
- Non-deterministic UDFs

Determinism requirements belong in transformation semantics.

## Testing

Required tests should cover:

- Plugin discovery
- Capability declarations
- Type mappings
- Schema validation
- Row-level validation
- Native expressions
- Python UDF behavior
- Joins
- Aggregations
- Windows
- Lazy execution
- Action boundaries
- Caching
- Checkpointing
- Batch execution
- Structured Streaming
- Failure classification
- Cancellation
- Retry and idempotency
- Diagnostics
- Lineage
- Backend equivalence

## Local Test Environment

The SDK should provide fixtures for local Spark testing.

Conceptually:

```python
def test_pipeline_with_local_spark(
    local_spark_profile,
) -> None:
    result = CustomerPipeline.run(
        profile=local_spark_profile,
    )

    assert result.success
```

Local tests should use small deterministic datasets.

## Integration Testing

Optional integration suites may target:

- Databricks
- EMR
- Kubernetes
- YARN
- Spark Connect
- Cloud object storage
- Delta Lake
- Iceberg

Integration tests should be separated from fast local conformance tests.

## Best Practices

- Use native Spark expressions.
- Preserve lazy execution.
- Keep contracts Spark-independent.
- Make action boundaries explicit.
- Use Resource Providers for Spark sessions.
- Preserve validation boundaries.
- Declare batch and streaming support separately.
- Test null, decimal, and timestamp semantics.
- Keep runtime configuration in profiles.
- Preserve logical step identities through Spark optimization.
- Use shared conformance and equivalence tests.

## Anti-Patterns

Avoid:

- Calling `collect()` inside ordinary transformations.
- Embedding Spark sessions in pipeline definitions.
- Treating all PySpark transformations as streaming-compatible.
- Using Python UDFs unnecessarily.
- Relying on row order without declaring it.
- Skipping validation because Spark has a schema.
- Hiding materialization and action boundaries.
- Retrying non-idempotent sinks blindly.
- Logging credentials or complete sensitive rows.
- Coupling DTCS contracts to Spark-specific APIs.

## Key Principle

> PySpark execution turns Spark-capable regions of a validated Pipeline Plan
> into lazy, distributed Spark computations while preserving contracts,
> validation, lineage, diagnostics, failure semantics, and observable behavior.

## Next Step

Continue with **SPARK_OPTIMIZATION.md** to define ETLantic's Spark planning
rules for region fusion, partitioning, caching, adaptive execution, pushdown,
and materialization boundaries.
