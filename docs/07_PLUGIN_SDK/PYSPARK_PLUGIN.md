# PySpark Plugin

**Status: shipped in 0.7.0** (`etlantic.spark/1`). The reference plugin is
`etlantic-pyspark`.

!!! note "Future compiler role"
    Compilation of PySpark-inspired `etlantic.transform/1` definitions to
    native Spark expressions is planned for 0.13 and follows the
    [portable compiler protocol](PORTABLE_TRANSFORM_COMPILER.md).

A **PySpark Plugin** implements the ETLantic PySpark Plugin API for Apache
Spark execution environments.

The plugin converts Spark-capable regions of a validated Pipeline Plan into
PySpark DataFrame operations, Spark SQL logical plans, batch jobs, or Structured
Streaming queries while preserving ODCS, DTCS, and DPCS semantics.

A PySpark plugin is an execution backend, not a modeling layer. Pipeline authors
continue to define portable contracts, transformations, and pipelines without
embedding Spark sessions, cluster settings, DataFrame types, or deployment
details into those definitions.

## Purpose

A PySpark plugin is responsible for:

- Executing registered PySpark transformation implementations
- Building Spark logical plans
- Preserving lazy execution
- Coordinating Spark actions
- Supporting batch and Structured Streaming
- Mapping contract types to Spark schemas
- Enforcing validation boundaries
- Participating in Spark optimization
- Managing Spark-specific diagnostics and lineage
- Declaring Spark and runtime capabilities

It is **not** responsible for:

- Defining pipeline semantics
- Defining transformation contracts
- Replacing the ETLantic planner
- Replanning a pipeline during execution
- Embedding cluster configuration into contracts
- Silently weakening validation or failure behavior

## Architecture

```text
Validated Pipeline Plan
          │
          ▼
    PySpark Plugin API
          │
    ┌─────┴─────────────────────────────┐
    ▼                                   ▼
Spark Region Compiler           Spark Runtime Adapter
    │                                   │
    ├── DataFrame API                   ├── SparkSession
    ├── Spark SQL                       ├── Job submission
    ├── Streaming plans                 ├── Cancellation
    └── Optimization metadata           └── Metrics
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

## Plugin Roles

A PySpark plugin may fulfill several related roles.

### Transformation executor

Invokes registered PySpark implementations with typed Spark DataFrame inputs.

### Spark region compiler

Combines compatible steps into one lazy Spark execution region.

### Schema adapter

Maps ContractModel data contracts to Spark schemas and back.

### Validation provider

Compiles compatible constraints into Spark expressions and quality checks.

### Streaming provider

Builds Structured Streaming queries for streaming-capable regions.

### Runtime adapter

Coordinates Spark sessions, job groups, cancellation, metrics, and deployment.

One package may implement all roles, or the ecosystem may separate shared Spark
logic from environment-specific runtime providers.

## Plugin Interface

Conceptually:

```python
class PySparkPlugin:
    name: str
    version: str

    def capabilities(self) -> SparkCapabilities:
        ...

    def compile(
        self,
        region: SparkPlanRegion,
        context: SparkCompilationContext,
    ) -> CompiledSparkPlan:
        ...

    def execute(
        self,
        compiled: CompiledSparkPlan,
        context: ExecutionContext,
    ) -> SparkExecutionResult:
        ...
```

The exact SDK may evolve, but plugins should expose stable structured objects
rather than requiring ETLantic to call private Spark internals.

## Typed Spark DataFrames

The SDK should expose a typed wrapper or protocol:

```python
SparkDataFrame[Customer]
```

This wrapper communicates the governing contract while delegating execution to
a native PySpark `DataFrame`.

It should support:

- Access to the native DataFrame
- Contract identity
- Schema compatibility metadata
- Logical lineage identity
- Execution-region identity
- Controlled conversion to other backends

The wrapper must not duplicate the entire PySpark API.

## Transformation Implementations

A transformation remains portable:

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]
```

A PySpark implementation is registered separately:

```python
@NormalizeCustomers.implementation("pyspark")
def normalize_customers(
    customers: SparkDataFrame[RawCustomer],
) -> SparkDataFrame[Customer]:
    ...
```

The planner selects it only when:

- The plugin is installed.
- Required Spark capabilities are available.
- Input relations can enter a Spark region.
- Output validation can be preserved.
- The selected profile permits PySpark execution.

## Native Expression Policy

Plugins should encourage native Spark expressions.

Preferred:

```python
from pyspark.sql import functions as F

result = dataframe.select(
    F.trim(F.col("name")).alias("name"),
)
```

Discouraged when a native equivalent exists:

```python
from pyspark.sql.functions import udf
```

The compiled plan should record whether an implementation uses:

- Native DataFrame expressions
- Spark SQL expressions
- Scalar Python UDFs
- pandas UDFs
- Iterator pandas UDFs
- JVM extensions

## Capability Model

Every plugin should publish structured capabilities.

Conceptually:

```python
SparkCapabilities(
    batch=True,
    structured_streaming=True,
    native_expressions=True,
    python_udfs=True,
    pandas_udfs=True,
    adaptive_query_execution=True,
    checkpointing=True,
    caching=True,
    broadcast_joins=True,
    window_functions=True,
    delta_lake=True,
    iceberg=True,
    jdbc=True,
    kafka=True,
    arrow_interchange=True,
    spark_connect=False,
)
```

Capabilities should distinguish:

- Supported
- Partially supported
- Environment dependent
- Version dependent
- Unsupported

## Version Metadata

Every plugin should publish compatibility for:

- ETLantic
- Plugin SDK
- PySpark
- Apache Spark
- Python
- Java
- Scala binary version where relevant
- Hadoop libraries
- Delta Lake
- Iceberg
- Cloud runtime distributions

Planning should reject unsupported combinations before job submission.

## Spark Environment Identity

The plugin should identify the execution environment.

Examples include:

- Local Spark
- Standalone Spark
- YARN
- Kubernetes
- Databricks
- Amazon EMR
- Google Dataproc
- Azure Synapse
- Spark Connect

Environment identity may influence capabilities without changing pipeline
semantics.

## Spark Session Provider

Spark sessions should be supplied through a Resource Provider.

Conceptually:

```text
PySpark Plugin
      │
      ▼
SparkSession Provider
      │
      ▼
SparkSession
```

The provider may configure:

- Master or remote endpoint
- Application name
- Catalogs
- Spark extensions
- Packages and JARs
- Session time zone
- Shuffle partitions
- Cloud credentials
- Delta or Iceberg support
- Spark Connect
- Cluster policies

The plugin should not construct arbitrary unmanaged sessions inside
transformations.

## Session Lifecycle

Supported lifecycle policies may include:

- One session per pipeline run
- Shared worker session
- Externally managed session
- Remote session
- Session pool
- Databricks Connect session

The provider should declare:

- Ownership
- Reuse policy
- Cleanup responsibility
- Thread-safety constraints
- Concurrent run behavior

## Spark Compilation Context

Compilation may require:

```python
SparkCompilationContext(
    spark_version="4.0.0",
    environment="databricks",
    execution_mode="batch",
    session_timezone="UTC",
    capabilities=...,
)
```

The context should include only planning and compilation metadata, not secrets.

## Spark Plan Regions

The planner groups adjacent PySpark-capable steps into Spark regions.

A region may contain:

- Sources
- Transformations
- Validation expressions
- Quality gates
- Materialization boundaries
- Sink preparation

The plugin compiles the region into one or more lazy Spark DataFrame plans.

## Region Fusion

Fusion should be supported when it preserves:

- Logical step identities
- Input and output contracts
- Validation boundaries
- Retry boundaries
- Failure semantics
- Quality gates
- Lineage
- Determinism

The plugin may physically fuse steps while retaining logical attribution
metadata.

## Region Splitting

The plugin or planner should require a split for:

- Backend transition
- Checkpoint
- Full validation action
- Distinct retry boundary
- Different Spark session
- Security boundary
- Streaming state boundary
- Required materialization
- Incompatible implementation

The reason should be visible in diagnostics and plan inspection.

## Lazy Execution

The plugin must preserve Spark laziness.

Compilation must not call actions such as:

- `collect()`
- `count()`
- `show()`
- `take()`
- `first()`
- `toPandas()`

Actions belong to execution boundaries, not compilation.

## Action Model

The compiled Spark plan should identify actions explicitly.

Conceptually:

```python
SparkAction(
    kind="write",
    step_id="publish-customers",
)
```

Possible action categories include:

- Sink write
- Validation count
- Quality-gate aggregation
- Checkpoint
- Explicit materialization
- Small control result
- Streaming query start

## Schema Mapping

The plugin maps data contracts to Spark SQL schemas.

Supported logical mappings may include:

- Integer types
- Decimal
- Float
- Boolean
- String
- Binary
- Date
- Timestamp
- Timestamp without time zone
- Array
- Map
- Struct

Every mapping should report:

- Exact
- Compatible
- Lossy
- Unsupported

## Nullability

Spark schemas include nullable metadata, but runtime data may still violate
logical expectations.

The plugin should distinguish:

- Schema nullability
- Contract requiredness
- Row-level null validation
- Nested nullability
- Container element nullability

## Decimal Mapping

Decimal support must preserve:

- Precision
- Scale
- Rounding
- Aggregate widening
- Overflow behavior

The plugin should report when Spark expression inference produces a type that no
longer satisfies the output contract.

## Timestamp Mapping

The plugin should declare behavior for:

- Session time zone
- Naive datetime
- Zoned datetime
- Spark timestamp types
- Precision
- Parsing
- Serialization

Time-zone configuration should be explicit and deterministic.

## Nested Types

The plugin should support contract mappings for:

- Structs
- Lists
- Maps
- Optional nested fields
- Nested arrays and structs

Unsupported nested validators should produce explicit fallback diagnostics.

## Input Conversion

Spark inputs may originate from:

- Native Spark sources
- SQL relations
- Arrow tables
- Polars DataFrames
- Pandas DataFrames
- Python records for small fixtures

Conversions must preserve contract semantics and remain explicit in the plan.

## Output Conversion

Spark outputs may be consumed by:

- Another Spark region
- Spark-compatible sinks
- SQL sinks
- Arrow interchange
- Polars
- Pandas for small results
- Python callbacks receiving metadata only

Large datasets should not be collected to the driver by default.

## Arrow Interchange

Arrow may support transitions between Spark and local dataframe engines.

The plugin should declare:

- Arrow version compatibility
- Supported logical types
- Batch-size controls
- Time-zone behavior
- Decimal behavior
- Nested type behavior

Arrow conversion is a materialization boundary.

## Sources

The plugin may support Spark-native source bindings for:

- Parquet
- Delta Lake
- Iceberg
- JDBC
- Kafka
- CSV
- JSON
- ORC
- Cloud object storage
- Hive metastore
- Unity Catalog
- Custom DataSource V2 connectors

Source capabilities should be advertised through the storage or source plugin.

## Source Pushdown

The plugin should preserve source optimizations such as:

- Predicate pushdown
- Projection pruning
- Partition pruning
- Aggregate pushdown
- JDBC query pushdown
- DataSource V2 filters

Pushdown decisions should remain inspectable.

## Sinks

Supported Spark sinks may include:

- Delta Lake
- Iceberg
- Parquet
- ORC
- JDBC
- Kafka
- Catalog-managed tables
- Custom DataSource V2 sinks

The plugin should coordinate with storage plugins rather than owning every
backend directly.

## Write Modes

Possible modes include:

- Append
- Overwrite
- Partition overwrite
- Merge
- Upsert
- Replace
- Complete streaming output
- Update streaming output
- Append streaming output

Write semantics must be explicit and capability-validated.

## Delta Lake

A plugin may declare Delta capabilities such as:

- Read and write
- Merge
- Change Data Feed
- Time travel
- Schema enforcement
- Schema evolution
- Transactional writes
- Optimize
- Vacuum
- Streaming source and sink

Delta behavior may be environment and version dependent.

## Iceberg

Iceberg capabilities may include:

- Snapshot reads
- Incremental reads
- Merge
- Partition evolution
- Schema evolution
- Catalog integration
- Streaming support where available

The plugin should avoid assuming identical behavior between Delta and Iceberg.

## JDBC

JDBC execution may support:

- Partitioned reads
- Predicate pushdown
- Batch writes
- Truncate
- Isolation options
- Query-based sources
- Driver properties

JDBC retry and idempotency behavior should be explicit.

## Batch Execution

The plugin should support bounded Spark jobs.

A compiled batch region may contain:

- Lazy source reads
- Transformations
- Validation
- Quality gates
- Sink writes
- Metrics

The orchestrator determines when and where the job runs.

## Structured Streaming

The plugin should declare separate streaming capabilities.

Conceptually:

```python
SparkStreamingCapabilities(
    micro_batch=True,
    continuous_processing=False,
    event_time=True,
    watermarks=True,
    stateful_aggregations=True,
    streaming_joins=True,
    deduplication=True,
    foreach_batch=True,
)
```

Batch support must not imply streaming support.

## Streaming Sources

Possible streaming sources include:

- Kafka
- Delta Change Data Feed
- File streams
- Cloud file ingestion systems
- Custom connectors

Each source should declare delivery, offset, and recovery semantics.

## Streaming Sinks

Possible sinks include:

- Kafka
- Delta Lake
- Iceberg where supported
- `foreachBatch`
- Console for development
- Memory sink for testing

The plugin should declare output-mode compatibility.

## Watermarks

Watermark support should include:

- Event-time field
- Allowed lateness
- State cleanup behavior
- Late-event policy
- Multi-stream watermark constraints

Watermark semantics affect observable results and must be preserved.

## Stateful Execution

Stateful capabilities may include:

- Windowed aggregation
- Sessionization
- Streaming joins
- Deduplication
- Group state
- Transform with state
- State-store providers

The plugin should expose checkpoint and state schema requirements.

## Streaming Query Lifecycle

The plugin should coordinate:

- Query construction
- Query start
- Progress monitoring
- Graceful stop
- Cancellation
- Restart
- Checkpoint recovery
- Failure diagnostics

Streaming query IDs should be mapped back to pipeline and step identities.

## Validation Provider

The plugin should compile compatible data-contract constraints into Spark
expressions.

Examples include:

- Required values
- Numeric ranges
- Allowed values
- String lengths
- Regex patterns
- Cross-field expressions
- Uniqueness checks
- Aggregate quality rules

The plugin must declare which rules are natively supported.

## Validation Result Model

Conceptually:

```python
SparkValidationResult(
    valid=dataframe,
    invalid=invalid_dataframe,
    diagnostics=[...],
    metrics={...},
)
```

The result may remain lazy until a quality gate or sink requires an action.

## Unsupported Validators

Unsupported validators may require:

- Planning failure
- pandas UDF fallback
- ContractModel fallback
- Sampling when explicitly permitted
- Materialization to another backend
- Post-write verification

The chosen strategy should be visible in the plan.

## Invalid-Data Handling

The plugin should support explicit policies:

- Fail
- Quarantine
- Continue with valid rows
- Route to side output
- Invoke callback
- Emit metrics only when permitted

Partial acceptance must never be implicit.

## Quality Gates

The plugin may combine compatible quality metrics into one Spark aggregation.

This reduces duplicate scans while preserving each logical gate.

Quality-gate results should map back to stable diagnostic codes.

## Caching

The plugin should support cache planning and lifecycle management.

Capabilities may include:

- Cache
- Persist
- Storage levels
- Unpersist
- Shared cache
- Region-local cache

Caching should be inserted only when beneficial or required.

## Checkpointing

The plugin should support:

- Reliable checkpoints
- Local checkpoints
- Streaming checkpoints
- Checkpoint cleanup
- External checkpoint providers

Checkpoint semantics should remain distinct from caching.

## Partitioning

The plugin should expose execution controls for:

- Repartition
- Coalesce
- Range partitioning
- Hash partitioning
- Shuffle partitions
- Output partitioning
- Bucketing where supported

Partition configuration belongs in profiles or optimization plans.

## Adaptive Query Execution

The plugin should declare support for AQE features such as:

- Shuffle partition coalescing
- Dynamic join strategy changes
- Skew handling
- Local shuffle reads

The compiled plan should record whether AQE is:

- Required
- Enabled
- Disabled
- Environment managed

## Join Strategy Hints

The plugin may support hints such as:

- Broadcast
- Merge
- Shuffle hash
- Shuffle replicate nested loop

Hints should remain optimization metadata and must not change logical semantics.

## Python UDF Policy

Profiles may control Python UDF usage.

Conceptually:

```python
SparkUdfPolicy(
    scalar_python="warn",
    pandas_udf="allow",
    native_required=False,
)
```

The plugin should report optimizer visibility and portability implications.

## Compilation Output

A compiled Spark plan may include:

```python
CompiledSparkPlan(
    regions=[...],
    actions=[...],
    required_packages=[...],
    session_requirements={...},
    diagnostics=[...],
)
```

It should be inspectable without executing Spark.

## Deployment Artifacts

The plugin may compile to:

- Python entry point
- Wheel bundle
- Spark-submit command
- Databricks job task
- EMR step
- Kubernetes SparkApplication
- Orchestrator operator configuration
- Spark Connect request

Deployment artifacts must preserve the same Pipeline Plan semantics.

## Dependency Packaging

The plugin should describe required:

- Python packages
- Wheels
- JARs
- Maven coordinates
- Spark packages
- Configuration files
- Native libraries

Dependencies should be deterministic and reviewable.

## Job Identity

Spark jobs should use stable metadata derived from:

- Pipeline identity
- Run identity
- Step or region identity
- Attempt number

Where available, job groups should support cancellation and diagnostic
attribution.

## Execution Result

Conceptually:

```python
SparkExecutionResult(
    success=True,
    outputs={...},
    application_id="...",
    query_ids=[...],
    diagnostics=[...],
    metrics={...},
)
```

Large distributed outputs should be represented by typed references rather than
collected values.

## Failure Classification

The plugin should classify failures such as:

- Session acquisition failure
- Analysis error
- Missing column
- Type incompatibility
- Source failure
- Task failure
- Stage failure
- Executor loss
- Shuffle failure
- Sink commit failure
- Streaming query failure
- Checkpoint failure
- Permission failure
- Cancellation

Classification supports retries and remediation.

## Retryability

Potentially retryable failures include:

- Executor loss
- Transient object-storage errors
- Fetch failures
- Cluster startup failures
- Temporary network failures
- Rate limiting

Non-retryable failures often include:

- Analysis errors
- Contract incompatibility
- Unsupported expressions
- Invalid schema
- Missing permissions

The plugin should return typed retry guidance, not retry automatically outside
the execution policy.

## Idempotency

The plugin should describe sink idempotency.

Examples:

- Deterministic overwrite
- Delta merge with stable keys
- Append-only output
- Kafka delivery
- JDBC batch inserts
- `foreachBatch` custom writes

Retries should not be approved without considering idempotency.

## Cancellation

The plugin should support cancellation where available.

Cancellation may target:

- Spark job group
- Spark job
- Streaming query
- Remote submission
- Databricks run
- Kubernetes Spark application

Cleanup behavior should be documented.

## Diagnostics

Diagnostics may include:

- Plugin name and version
- Spark and PySpark versions
- Environment identity
- Pipeline identity
- Region identity
- Step identity
- Application ID
- Job group
- Job ID
- Stage ID
- Task attempt
- Streaming query ID
- Failure category
- Suggested remediation

Sensitive configuration and row data must be redacted.

## Observability

The plugin may emit:

- Input and output rows
- Job and stage durations
- Shuffle bytes
- Spill
- Partition counts
- Executor failures
- Cache metrics
- Streaming progress
- Watermark progress
- State-store size
- Sink commit information

Metrics supplement the logical pipeline model.

## Lineage

Logical lineage comes from the Pipeline Plan.

The plugin may add runtime lineage such as:

- Physical paths
- Catalog tables
- Delta versions
- Iceberg snapshots
- Kafka offsets
- Spark query IDs
- Checkpoint locations

Runtime lineage must not replace contract-level lineage.

## Plan Inspection

The plugin should expose:

- Spark regions
- Fused steps
- Action boundaries
- Materialization points
- Cache points
- Checkpoints
- Backend transitions
- Required packages
- Capability decisions

Conceptually:

```python
compiled.optimization_report()
```

## Spark Explain

The plugin may expose Spark explain modes without running actions.

```python
compiled.explain(
    mode="formatted",
)
```

Explain output should be linked to logical region and step identities where
possible.

## Security

Requirements include:

- External credentials
- Redacted Spark configuration
- Least-privilege storage access
- Safe dependency distribution
- Controlled UDF execution
- Restricted Spark UI links
- Secure checkpoint storage
- Safe logs
- No secrets in compiled plans
- Isolation between pipeline runs

## Plugin Discovery

Conceptually:

```python
from etlantic.plugins import register_pyspark_plugin

register_pyspark_plugin(
    DefaultPySparkPlugin(),
)
```

Normal installations should use standard plugin discovery rather than manual
registration.

## Package Naming

Recommended package names include:

- `etlantic-pyspark`
- `etlantic-databricks`
- `etlantic-emr`
- `etlantic-spark-kubernetes`
- `etlantic-delta`
- `etlantic-iceberg`

A shared PySpark package may provide the core executor and conformance suite,
while environment packages provide Resource Providers and deployment adapters.

## Conformance Testing

Every PySpark plugin should pass shared SDK tests.

Required areas include:

- Discovery
- Capability metadata
- Version compatibility
- Typed DataFrame wrappers
- Schema mapping
- Decimal and timestamp semantics
- Null behavior
- Native expressions
- UDF policy
- Region fusion
- Region splitting
- Lazy execution
- Action boundaries
- Validation
- Invalid-data routing
- Caching
- Checkpointing
- Batch execution
- Structured Streaming
- Failure classification
- Retry guidance
- Idempotency
- Cancellation
- Diagnostics
- Observability
- Lineage
- Plan inspection

## Backend Equivalence

PySpark results should be compared with reference backends.

Recommended comparisons include:

- PySpark vs. Polars
- PySpark vs. SQL
- Local Spark vs. remote Spark
- Batch vs. available-now streaming where semantics align

Equivalent inputs should produce contract-compatible logical outputs.

## Local Fixtures

The SDK should provide a deterministic local Spark fixture.

```python
def test_plugin_conformance(
    local_spark_session,
    pyspark_plugin,
) -> None:
    ...
```

Local fixtures should remain small and fast enough for CI.

## Integration Tests

Optional suites may target:

- Databricks
- EMR
- Kubernetes
- YARN
- Spark Connect
- Delta Lake
- Iceberg
- Kafka
- Cloud object storage

Integration tests should be separated from local conformance tests.

## Performance Benchmarks

Benchmarks may track:

- Runtime
- Stage count
- Task count
- Shuffle volume
- Spill
- Cache reuse
- Input and output bytes
- File count
- Streaming latency
- State-store growth

Performance benchmarks do not replace semantic tests.

## Best Practices

- Depend only on public Plugin SDK interfaces.
- Preserve lazy execution.
- Prefer native Spark expressions.
- Declare batch and streaming capabilities separately.
- Keep sessions behind Resource Providers.
- Make actions and materialization explicit.
- Preserve validation and failure boundaries.
- Retain logical step identity through fusion.
- Use typed distributed output references.
- Expose plan inspection and diagnostics.
- Test backend equivalence.
- Keep environment details out of pipeline definitions.

## Anti-Patterns

Avoid:

- Treating PySpark as only a dataframe adapter.
- Creating Spark sessions inside transformations.
- Calling actions during compilation.
- Collecting large datasets to the driver.
- Assuming batch implementations are streaming-safe.
- Hiding Python UDF usage.
- Skipping validation because a Spark schema exists.
- Fusing across quality gates or retry boundaries.
- Retrying non-idempotent writes blindly.
- Embedding cluster credentials in profiles or plans.
- Leaking native Spark objects into portable contracts.
- Assuming all Spark distributions provide identical capabilities.

## Key Principle

> A PySpark Plugin turns Spark-capable regions of a validated Pipeline Plan into
> lazy, distributed Spark execution while preserving contracts, validation,
> lineage, failure semantics, diagnostics, and observable behavior.

## Next Step

Continue with **SPARK_PROVIDER.md** to define the Resource Provider API for
creating, configuring, reusing, and disposing Spark sessions across local,
cluster, managed-cloud, and Spark Connect environments.
