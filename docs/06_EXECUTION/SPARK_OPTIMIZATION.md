# Spark Optimization

From 0.13, portable expressions compile to native Spark Column/DataFrame plans
that remain visible to Catalyst. Optimizers may rewrite physical expressions
only while preserving DTCS meaning, validation/security boundaries, and
logical expression attribution; undeclared UDF fallback is prohibited.

**Status: shipped in 0.7.0** for the local reference path. Deep cluster/AQE
tuning guides beyond the local provider remain aspirational.

Spark optimization in ETLantic is the process of improving the physical
execution of Spark-capable pipeline regions without changing the logical
semantics of the pipeline.

ETLantic optimizes from the validated Pipeline Plan. It does not require
pipeline authors to encode Spark-specific tuning into transformation contracts
or pipeline topology.

## Goals

Spark optimization should:

- Preserve DTCS and DPCS semantics.
- Minimize unnecessary materialization.
- Reduce shuffles and data movement.
- Preserve lazy execution.
- Use Spark-native optimizer capabilities.
- Keep optimization decisions inspectable.
- Fall back safely when optimization would change behavior.

## Philosophy

Optimize the physical `PipelinePlan`, not the pipeline definition.

```text
Validated Pipeline Plan
          │
          ▼
Spark-Capable Region Analysis
          │
          ▼
Optimization Passes
          │
          ▼
Spark Logical Plan
          │
          ▼
Catalyst Optimizer
          │
          ▼
Physical Spark Plan
```

ETLantic performs framework-level optimization before Spark performs its
own logical and physical optimization.

## Optimization Layers

Spark execution includes several optimization layers.

### ETLantic planning

Determines:

- Spark-capable regions
- Backend boundaries
- Validation boundaries
- Materialization points
- Resource requirements
- Reuse opportunities

### Spark logical optimization

Catalyst may perform:

- Predicate pushdown
- Projection pruning
- Constant folding
- Join reordering
- Expression simplification

### Spark physical optimization

Spark may choose:

- Broadcast joins
- Sort-merge joins
- Shuffle hash joins
- Partition counts
- Exchange strategies

### Adaptive Query Execution

AQE may adjust physical execution using runtime statistics.

Each layer must preserve observable pipeline semantics.

## Spark-Capable Regions

Adjacent steps with compatible PySpark implementations may be grouped into one
lazy Spark region.

```text
ReadOrders
    │
    ▼
FilterPaidOrders
    │
    ▼
JoinCustomers
    │
    ▼
AggregateMetrics
```

may become one Spark logical plan.

The region must preserve logical identities for every step.

## Region Fusion

Region fusion reduces unnecessary boundaries between transformations.

Benefits include:

- Fewer actions
- Fewer scans
- More Catalyst visibility
- More pushdown
- Better join optimization
- Less serialization

Fusion is permitted only when ETLantic can preserve:

- Validation semantics
- Failure boundaries
- Retry behavior
- Quality gates
- Lineage
- Diagnostics
- Ordering requirements

## Region Splitting

ETLantic should split Spark regions when required.

Reasons include:

- Transition to SQL or Polars
- Required checkpoint
- Independent retry boundary
- Full validation action
- Quality gate
- Streaming state boundary
- Different Spark sessions
- Different security domains
- Required materialization
- Incompatible implementation capability

Splitting should be explicit in the plan.

## Lazy Execution

Spark transformations should remain lazy until an action is required.

ETLantic should detect or discourage accidental actions such as:

- `collect()`
- `count()`
- `show()`
- `take()`
- `first()`
- `toPandas()`

These actions can break fusion and trigger unexpected jobs.

## Action Planning

Actions should occur only at intentional boundaries.

Examples include:

- Sink write
- Quality gate
- Validation result
- Checkpoint
- Backend transition
- Explicit materialization
- Runtime metric requiring evaluation

The compiled plan should list every planned action.

## Predicate Pushdown

Filters should execute as close to the source as possible.

```text
Read all rows
      │
      ▼
Filter in Spark
```

may become a source-level filter for:

- Parquet
- Delta Lake
- Iceberg
- JDBC
- Supported catalog tables

Pushdown capabilities depend on the source plugin.

## Projection Pruning

Only required columns should be read and retained.

ETLantic can derive required columns from:

- Transformation inputs
- Output contracts
- Quality gates
- Lineage requirements
- Downstream consumers

Unused columns should be pruned when doing so preserves semantics.

## Partition Pruning

Partition filters should be applied to partitioned sources.

Examples include:

- Date partitions
- Region partitions
- Tenant partitions
- Snapshot partitions

Partition pruning reduces file and metadata scanning.

## Aggregate Pushdown

Some sources support aggregate pushdown.

Examples include:

- JDBC databases
- Data warehouses
- Advanced table formats

The planner should use aggregate pushdown only when result types and semantics
remain compatible.

## Join Planning

Join performance is often the dominant Spark optimization concern.

ETLantic may consider:

- Input sizes
- Partitioning
- Join keys
- Null behavior
- Data skew
- Broadcast eligibility
- Source locality
- Reuse

The planner should preserve the join type declared by the transformation.

## Broadcast Joins

A small relation may be broadcast to avoid a large shuffle.

Conceptually:

```python
broadcast(customers)
```

Broadcast should be chosen only when:

- The relation is sufficiently small.
- Cluster memory can support it.
- The profile permits broadcast.
- Statistics are reliable enough.
- The join semantics are preserved.

A forced broadcast hint should be inspectable.

## Sort-Merge Joins

Sort-merge joins are appropriate for large equi-joins.

They may require:

- Shuffle
- Sorting
- Compatible key types
- Adequate partition counts

ETLantic should not force a physical join strategy unless necessary.

## Shuffle Hash Joins

Shuffle hash joins may be beneficial under some sizes and configurations.

The plugin should treat them as runtime choices rather than pipeline semantics.

## Join Reordering

Catalyst may reorder joins.

ETLantic should allow reordering only when:

- Logical equivalence is preserved.
- Outer join semantics are not changed.
- Failure and validation boundaries do not depend on order.
- Vendor-specific behavior does not alter results.

## Skew Handling

Skewed keys may create slow tasks or memory pressure.

Optimization options include:

- AQE skew join handling
- Salting
- Pre-aggregation
- Broadcast
- Custom partitioning
- Splitting heavy keys

Salting changes physical representation and must not affect logical outputs.

## Partitioning

Partitioning affects performance and resource use.

ETLantic may reason about:

- Current partitioning
- Required partitioning
- Shuffle cost
- Output partitioning
- Downstream reuse
- Streaming state

Partitioning should remain an execution concern unless correctness depends on it.

## Repartition

`repartition()` triggers a shuffle.

It may be appropriate when:

- Increasing parallelism
- Redistributing skewed data
- Preparing for joins
- Aligning output partitions
- Satisfying partition-key requirements

Unnecessary repartitioning should be avoided.

## Coalesce

`coalesce()` reduces partitions without a full shuffle in common cases.

It may be useful before:

- Small output writes
- Local collection of tiny control data
- Reducing file counts

Over-coalescing can reduce parallelism.

## Repartition by Range

Range partitioning may improve:

- Ordered operations
- Range joins
- Window operations
- Sorted output

It should be used only when the downstream workload benefits.

## Shuffle Partition Count

The profile may configure:

```text
spark.sql.shuffle.partitions
```

A fixed default may be inefficient across workloads.

ETLantic may support:

- Profile-defined values
- Size-based recommendations
- AQE coalescing
- Backend defaults

Recommendations should remain advisory unless explicitly configured.

## Adaptive Query Execution

AQE can improve execution using runtime statistics.

Capabilities include:

- Coalescing shuffle partitions
- Switching join strategies
- Handling skewed joins
- Optimizing local shuffle reads

Profiles may enable AQE.

ETLantic should record whether AQE is required, preferred, or optional.

## Statistics

Optimization may use statistics such as:

- Estimated row counts
- Data sizes
- Column cardinality
- Null rates
- Partition counts
- File counts
- Catalog statistics

Statistics may come from:

- Source metadata
- Catalogs
- Previous runs
- Sampling
- User declarations

Stale or missing statistics should reduce confidence, not change semantics.

## Cost-Based Planning

Future planners may compare execution alternatives.

Examples:

- Spark vs. SQL
- Broadcast vs. shuffle join
- Cache vs. recompute
- Materialize vs. fuse
- Local vs. distributed execution

Cost-based decisions should consider:

- Data size
- Transfer cost
- Compute cost
- Cluster startup cost
- Reuse
- Validation cost
- Storage locality

## Cache Planning

Caching may benefit reused datasets.

The planner may cache when:

- One result feeds multiple downstream branches.
- A result is used by both validation and publication.
- Recomputing the source lineage is expensive.
- Iterative processing reuses the same data.

Caching should be avoided when:

- Data is used once.
- The dataset is too large.
- Recalculation is inexpensive.
- Memory pressure is high.

## Persist Storage Levels

The profile may choose storage levels such as:

- Memory only
- Memory and disk
- Disk only
- Serialized variants
- Off-heap where supported

The plugin should expose these through portable profile settings rather than
requiring pipeline code to import Spark constants.

## Cache Lifecycle

Cached data should be unpersisted when no longer needed.

The compiled plan should know:

- Cache creation point
- Consumers
- Release point
- Failure cleanup behavior

## Checkpoint Optimization

Checkpointing can truncate long lineage.

It may be useful when:

- Plans become extremely deep.
- Recomputing lineage is expensive.
- Streaming requires reliable state.
- Retry boundaries require persistence.
- Iterative algorithms accumulate lineage.

Checkpointing adds I/O and should not be applied automatically without reason.

## Local Checkpoints

Local checkpoints may be faster but provide weaker durability.

They should not satisfy a requirement for reliable recovery.

## File Size Optimization

Spark sinks may create too many small files.

Optimization strategies include:

- Coalescing before write
- Repartitioning by partition keys
- Target file size configuration
- Delta optimization
- Compaction jobs
- Writer-specific options

File layout is a storage concern but can materially affect future pipeline
performance.

## Output Partitioning

Output partitioning may be configured through profiles or sink bindings.

Examples:

- Partition by date
- Partition by tenant
- Cluster by customer
- Bucket by key

Partition choices should not be embedded in data contracts unless they are part
of a published storage interface.

## Python UDF Elimination

The optimizer should prefer native expressions over Python UDFs.

Possible rewrites include:

- Native string functions
- Native date functions
- SQL expressions
- Higher-order array functions
- Built-in aggregates
- pandas UDFs when unavoidable

Automatic rewrites should occur only when equivalence is certain.

## pandas UDFs

pandas UDFs may improve performance over scalar Python UDFs.

They still introduce:

- Arrow conversion
- Python worker execution
- Batch semantics
- Type-mapping concerns
- Memory constraints

Their use should be visible in the compiled plan.

## Arrow Interchange

Arrow may be used for:

- PySpark to Polars transitions
- pandas UDFs
- Spark Connect
- Batch interchange
- Validation fallback

Arrow conversion should preserve contract types and nullability.

## SQL and Spark Interoperability

Spark SQL and DataFrame operations share the same optimizer.

A PySpark implementation may use:

- DataFrame API
- Spark SQL expressions
- Temporary views
- SQL strings through a constrained interface

SQL strings should use safe parameter or identifier handling where applicable.

## Source Locality

The planner should consider where data resides.

Spark is often appropriate when:

- Data is in distributed object storage.
- Data is in Delta or Iceberg tables.
- Inputs are too large for one machine.
- Existing cluster resources are available.
- Multiple large sources require distributed joins.

SQL may be preferable when all data is already in one capable warehouse.

## Backend Boundary Minimization

Transitions between Spark, SQL, Polars, and Pandas may require data movement.

The planner should minimize:

- Serialization
- Network transfer
- Materialization
- Format conversion
- Driver collection

A backend transition should have an explicit reason.

## Validation Optimization

Validation can cause additional scans.

ETLantic may optimize by:

- Combining multiple validation expressions
- Reusing aggregates
- Validating during transformation
- Validating staging outputs
- Caching reused results
- Using source constraints
- Pushing compatible checks down

Validation must not be skipped merely for performance.

## Combined Quality Metrics

Compatible quality checks may be computed in one aggregation.

For example:

```text
row_count
invalid_id_count
null_email_count
duplicate_email_count
```

may be collected with fewer passes.

## Sampling

Sampling may be useful for:

- Profiling
- Planning estimates
- Non-authoritative diagnostics
- Development previews

Sampling must not replace mandatory validation unless the contract explicitly
permits sampled validation.

## Streaming Optimization

Structured Streaming introduces additional considerations:

- Micro-batch trigger interval
- State-store size
- Watermarks
- Output mode
- Checkpoint frequency
- Source rate limits
- Backpressure
- Stateful operator placement

Streaming optimization must preserve event-time and late-data semantics.

## State Store Optimization

Stateful operations may require tuning:

- State partition count
- Watermark duration
- State retention
- RocksDB state store where supported
- Checkpoint storage
- Compaction

These choices affect performance and recovery behavior.

## Trigger Selection

Possible trigger modes include:

- Processing-time micro-batches
- Available-now
- Once
- Continuous processing where supported

Trigger choice belongs in the execution profile unless it changes standardized
pipeline behavior.

## Failure Boundaries

Optimization must preserve failure semantics.

Region fusion may be invalid when:

- Steps have independent retry policies.
- A quality gate separates steps.
- One step has a distinct compensation path.
- A checkpoint is required.
- Diagnostics must identify separately materialized outputs.

Physical fusion should never erase logical attribution.

## Retry Boundaries

Recomputing a fused Spark region may repeat expensive upstream work.

Checkpointing or caching may be introduced when a retry boundary requires
isolation.

The planner should consider sink idempotency.

## Diagnostics

Optimization diagnostics should explain decisions.

Examples include:

- Steps fused into one Spark region
- Region split at validation boundary
- Broadcast join selected
- Broadcast join rejected due to size
- Cache inserted for reused branch
- Cache rejected due to memory estimate
- Repartition inserted
- SQL pushdown selected instead of Spark
- Backend transition required
- Python UDF limits optimizer visibility

Example:

```text
PMSPARK310

Pipeline: customer-metrics
Region: customer-join

Broadcast join was not selected because the estimated customer relation size
exceeds the profile limit of 256 MB.

Selected strategy:
- Sort-merge join
- 200 shuffle partitions
- Adaptive Query Execution enabled
```

## Plan Inspection

Optimization decisions should be inspectable.

Conceptually:

```python
compiled = plan.compile(
    target="pyspark",
)

print(compiled.optimization_report())
```

The report may include:

- Spark regions
- Fusion decisions
- Action boundaries
- Cache points
- Checkpoints
- Join strategies
- Partitioning
- Pushdown
- Backend transitions
- Required capabilities

## Explain Integration

The PySpark plugin may expose Spark explain plans.

Conceptually:

```python
compiled.explain(mode="formatted")
```

Spark explain output supplements ETLantic's optimization report.

## Determinism

Optimization decisions should be deterministic for equivalent:

- Pipeline Plan
- Profile
- Capability set
- Statistics
- Plugin versions

AQE may alter physical execution at runtime, but logical semantics must remain
stable.

## Profile Controls

Profiles may configure optimization.

Conceptually:

```python
Profile(
    spark={
        "adaptive_execution": True,
        "broadcast_threshold": "256MB",
        "shuffle_partitions": 200,
        "cache_policy": "automatic",
        "checkpoint_policy": "required-only",
    },
)
```

Possible settings include:

- Region fusion
- AQE
- Broadcast thresholds
- Shuffle partition policy
- Cache policy
- Checkpoint policy
- Skew handling
- Pushdown preferences
- Output file sizing
- UDF policy

## Required and Advisory Settings

Some profile options are mandatory.

Others are hints.

The plan should distinguish:

- Required execution constraints
- Preferred optimizations
- Backend defaults
- Runtime adaptive decisions

## Security and Governance

Optimization must respect:

- Data locality restrictions
- Security boundaries
- Tenant isolation
- Restricted materialization
- Encryption requirements
- Cluster policies
- Approved UDF policies

A faster plan is invalid if it violates governance requirements.

## Testing

Optimization tests should cover:

- Region fusion
- Region splitting
- Predicate pushdown
- Projection pruning
- Partition pruning
- Broadcast joins
- Shuffle joins
- Skew handling
- Cache insertion
- Cache cleanup
- Checkpoint placement
- Action boundaries
- Backend transitions
- Validation reuse
- AQE configuration
- Streaming state
- Failure boundaries
- Lineage preservation
- Deterministic planning

## Performance Benchmarks

Benchmarks may measure:

- Runtime
- Shuffle volume
- Input bytes
- Output bytes
- Stage count
- Task count
- Spill
- File count
- Cache reuse
- Cluster utilization

Benchmarks should not replace semantic tests.

## Best Practices

- Preserve lazy execution.
- Fuse compatible Spark steps.
- Make action boundaries explicit.
- Push filters and projections to sources.
- Prefer native expressions.
- Use broadcast only with credible size estimates.
- Cache only reused or expensive results.
- Checkpoint only for recovery or lineage reasons.
- Minimize backend transitions.
- Keep optimization decisions inspectable.
- Preserve logical step identity.
- Test backend equivalence.

## Anti-Patterns

Avoid:

- Calling actions inside ordinary transformation implementations.
- Repartitioning without a downstream reason.
- Caching every dataframe.
- Forcing broadcast joins blindly.
- Disabling validation for performance.
- Fusing across quality gates or retry boundaries.
- Assuming AQE fixes every poor plan.
- Collecting large datasets to the driver.
- Using Python UDFs for native operations.
- Treating partition count as pipeline semantics.
- Optimizing across security boundaries.

## Key Principle

> Spark optimization changes the physical execution strategy, not the logical
> pipeline. ETLantic may fuse regions, push operations down, adjust
> partitioning, cache, checkpoint, and select Spark strategies only when it can
> preserve contracts, validation, lineage, failure behavior, and observable
> results.

## Next Step

Continue with **STRUCTURED_STREAMING.md** to define how ETLantic models and
executes event-time processing, watermarks, stateful transformations,
checkpoints, and streaming sink guarantees with PySpark.
