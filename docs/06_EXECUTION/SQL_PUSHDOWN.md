# SQL Pushdown

**Status: shipped in 0.6.0** as part of SQL-native planning and execution.
Pushdown applies when a SQL plugin and dialect advertise the required
capabilities; unsupported features fail closed at planning.

SQL pushdown is the process of moving eligible pipeline operations into the
database so computation occurs as close to the data as possible.

Pipelantic uses pushdown as an execution optimization. The logical pipeline,
contracts, transformation interfaces, lineage, validation boundaries, and
failure semantics remain unchanged.

## Goals

SQL pushdown should:

- Minimize data movement.
- Reduce in-memory processing.
- Improve performance.
- Preserve DTCS and DPCS semantics.
- Remain transparent to pipeline authors.
- Fall back safely when pushdown is unavailable.

## Philosophy

Push computation to the data when doing so preserves semantics.

```text
Pipeline Plan
      │
      ▼
SQL Capability Analysis
      │
      ▼
Pushdown Planning
      │
      ├── SQL-executable region
      └── Non-SQL region
```

Pushdown is chosen by the planner and compiler, not encoded in the pipeline
definition.

## Eligible Operations

Typical pushdown candidates include:

- Projection
- Filtering
- Sorting
- Joins
- Aggregations
- Window functions
- Deduplication
- Type casts
- Null handling
- Conditional expressions
- INSERT ... SELECT
- CREATE TABLE AS SELECT
- MERGE / UPSERT

Support depends on the selected SQL dialect and plugin capabilities.

## Predicate Pushdown

Filters should be applied as early as possible.

```text
Read all rows
      │
      ▼
Filter in Python
```

may become:

```sql
SELECT *
FROM customers
WHERE active = TRUE;
```

Predicate pushdown reduces data transfer and memory usage.

## Projection Pushdown

Only required columns should be read.

```sql
SELECT
    customer_id,
    email
FROM customers;
```

Unused columns should not be materialized when they are not needed by downstream
steps.

## Join Pushdown

When inputs are accessible in the same SQL environment, joins may execute inside
the database.

```sql
SELECT
    c.customer_id,
    c.full_name,
    o.order_total
FROM customers AS c
JOIN orders AS o
    ON c.customer_id = o.customer_id;
```

Cross-system joins require explicit planning and may need materialization.

## Aggregation Pushdown

Aggregations are strong candidates for pushdown.

```sql
SELECT
    customer_id,
    COUNT(*) AS order_count,
    SUM(order_total) AS order_total
FROM orders
GROUP BY customer_id;
```

This avoids moving detailed records into Python when only summaries are needed.

## Step Fusion

Adjacent SQL-capable steps may be fused into one query.

```text
FilterOrders
      │
      ▼
JoinCustomers
      │
      ▼
AggregateOrders
```

may compile into one statement or CTE chain.

Fusion is permitted only when it preserves:

- Step semantics
- Validation guarantees
- Diagnostics
- Failure behavior
- Lineage
- Observable outputs

## Materialization Boundaries

The planner should introduce materialization only when necessary.

Possible boundaries include:

- Transition to a non-SQL implementation
- Cross-database movement
- Required validation boundary
- Checkpoint
- Quality gate
- Retry boundary
- Reuse by multiple downstream branches
- Transaction boundary

Materialization may use:

- Temporary tables
- Views
- Materialized views
- Result sets
- Arrow data
- Dataframes

## Hybrid Execution

Pushdown can coexist with in-memory execution.

```text
SQL Source
    │
    ▼
SQL Filter + Join
    │
    ▼
Materialize
    │
    ▼
Polars Transformation
    │
    ▼
SQL Sink
```

The planner should minimize transitions while preserving required semantics.

## Capability Analysis

Before pushdown, Pipelantic should verify:

- Dialect support
- Function support
- Type compatibility
- Transaction support
- Join compatibility
- Window-function support
- Temporary object support
- Parameter binding
- Validation capabilities

Unsupported operations remain outside the SQL region.

## Contract Validation

Pushdown must not bypass contracts.

Validation may occur through:

- SQL predicates
- Database constraints
- Generated validation queries
- Schema inspection
- Post-query validation
- ContractModel fallback

If the database cannot enforce a required rule, Pipelantic must preserve the
validation boundary through another strategy.

## Semantic Preservation

Pushdown must preserve:

- Input and output contracts
- Null semantics
- Type behavior
- Ordering requirements
- Determinism requirements
- Failure semantics
- Quality gates
- Lineage
- Parameter behavior

SQL dialect differences must be handled explicitly.

## Null Semantics

SQL null behavior may differ from Python and dataframe libraries.

The compiler must account for:

- Three-valued logic
- Null-safe equality
- Aggregate null behavior
- Join semantics
- Sorting of nulls
- Boolean expressions

A pushdown is invalid if equivalent behavior cannot be guaranteed.

## Type Semantics

SQL dialects differ in:

- Numeric precision
- Integer widths
- Timestamp behavior
- Time zones
- Boolean representation
- String collation
- Decimal handling
- JSON types

The planner must detect lossy or unsupported mappings.

## Parameter Binding

All generated queries should use bound parameters.

```sql
SELECT *
FROM orders
WHERE status = :included_status;
```

String interpolation should not be used for user-controlled values.

## Query Inspection

Pipelantic should make generated SQL inspectable.

Conceptually:

```python
sql_plan = plan.compile(
    target="sql",
)

print(sql_plan.statements)
```

Inspection should support debugging without requiring execution.

## Diagnostics

Pushdown diagnostics may include:

- Operation pushed down
- Operation not pushed down
- Capability mismatch
- Dialect limitation
- Validation fallback
- Materialization boundary
- Semantic incompatibility
- Optimization decision

Example:

```text
PMSQL301

Step: CalculateCustomerMetrics
Operation: window function
Dialect: SQLite

The selected dialect cannot preserve the required window-frame semantics.
This operation will execute with the Polars implementation instead.
```

## Explain Plans

Where supported, SQL plugins may expose database query plans.

Conceptually:

```python
explain = sql_plan.explain()
```

Database explain output is runtime metadata.

It should supplement, not replace, the Pipelantic `PipelinePlan`.

## Cost-Based Selection

Future planners may use cost information such as:

- Estimated row counts
- Data size
- Transfer cost
- Database statistics
- Available indexes
- Compute location
- Materialization cost

Cost-based planning should remain advisory unless it can preserve deterministic
selection requirements.

## Configuration

Profiles may control pushdown behavior.

Conceptually:

```python
Profile(
    sql_pushdown="automatic",
)
```

Possible modes:

- `automatic`
- `required`
- `disabled`
- `prefer_sql`
- `prefer_dataframe`

Configuration affects execution strategy, not logical pipeline semantics.

## Required Pushdown

Some environments may require SQL execution for governance or data-locality
reasons.

If pushdown is required and cannot preserve semantics, planning should fail
rather than silently materializing data into Python.

## Lineage

Pushdown must preserve logical lineage even when multiple steps compile into one
query.

The runtime may execute one SQL statement, but the lineage model should still
represent each logical transformation and dataset relationship.

## Failure Semantics

Fused SQL execution can change failure granularity.

Pipelantic must preserve declared semantics by determining whether:

- Steps may be fused safely
- Separate transactions are required
- Checkpoints must be retained
- Individual diagnostics can still be attributed
- Retry boundaries remain valid

If not, the planner should retain separate execution units.

## Security

Pushdown implementations should:

- Use parameterized queries
- Respect least-privilege access
- Avoid exposing generated SQL with secrets
- Validate identifiers safely
- Restrict dynamic object names
- Redact sensitive diagnostics

## Testing

Pushdown tests should compare SQL and reference implementations.

Recommended coverage includes:

- Equivalent outputs
- Null behavior
- Type behavior
- Boundary values
- Join semantics
- Aggregation semantics
- Window functions
- Parameter binding
- Validation failures
- Dialect differences
- Hybrid materialization
- Lineage preservation

## Best Practices

- Push filters and projections early.
- Keep contracts backend-independent.
- Use capability-driven planning.
- Preserve validation boundaries.
- Make generated SQL inspectable.
- Prefer parameterized expressions.
- Retain logical lineage through fusion.
- Fall back safely when equivalence is uncertain.

## Anti-Patterns

Avoid:

- Assuming SQL behavior matches Python automatically.
- Fusing steps across required failure or validation boundaries.
- Dropping unsupported constraints.
- Embedding dialect-specific SQL in pipeline definitions.
- Moving data into Python when equivalent safe pushdown is available.
- Requiring pushdown when semantics cannot be preserved.

## Key Principle

> SQL pushdown changes where computation runs, not what the pipeline means.
> Pipelantic may move eligible operations into the database only when it can
> preserve contracts, validation, lineage, diagnostics, and observable behavior.

## Next Step

Continue with [SQL Dialect](../07_PLUGIN_SDK/SQL_DIALECT.md) to learn how SQL
plugins declare capabilities, type mappings, compilation behavior, and
portability limitations.
