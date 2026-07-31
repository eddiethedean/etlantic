# SQL Execution

**Status: available in 0.37.0.** `etlantic-sql` treats SQLite and PostgreSQL
as live Tier A dialects. PostgreSQL alone advertises `sql_merge`; SQLite fails
closed when merge is required.

The SQL Execution subsystem defines how ETLantic executes validated
Pipeline Plans directly within SQL databases.

Unlike dataframe execution backends, SQL execution compiles eligible
transformations into database-native operations. This allows computation to run
where the data already resides while preserving the semantics defined by [ODCS](../03_DATA_CONTRACTS/ODCS.md),
[DTCS](../04_TRANSFORMATIONS/DTCS.md), and [DPCS](../05_PIPELINES/DPCS.md).

## Purpose

SQL execution is responsible for:

- Executing SQL transformation implementations
- Compiling logical operations to SQL
- Coordinating transactional reads and writes
- Preserving contract validation
- Supporting multiple SQL dialects
- Reporting structured diagnostics

It is **not** responsible for pipeline modeling or planning.

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
SQL Execution Plugin
    │
    ▼
SQL Compiler
    │
    ▼
Dialect Adapter
    │
    ▼
Database
```

## Execution Flow

1. Validate the pipeline.
2. Build a Pipeline Plan.
3. Select SQL implementations where applicable.
4. Compile logical operations into dialect-specific SQL.
5. Execute inside the target database.
6. Validate outputs.
7. Commit or roll back transactions.
8. Emit diagnostics and lineage events.

## SQL Implementations

Transformations remain backend-independent.

```python
class NormalizeCustomers(Transformation):
    customers: Input[Customer]
    result: Output[Customer]
```

A SQL implementation is registered independently:

```python
@NormalizeCustomers.implementation("sql")
def normalize_customers(customers):
    ...
```

The planner selects it only when all required capabilities are available.

## Compiler Responsibilities

The SQL compiler should:

- Generate parameterized SQL
- Adapt syntax to the selected dialect
- Preserve transformation semantics
- Avoid SQL injection
- Produce deterministic output
- Expose structured compilation diagnostics

## Supported Operations

Typical operations include:

- Projection
- Filtering
- Joins
- Aggregations
- Window functions
- Common table expressions
- INSERT ... SELECT
- CREATE TABLE AS SELECT
- DELETE
- UPDATE
- MERGE / UPSERT (only when the plugin advertises `sql_merge`)

Support depends on plugin capabilities. PostgreSQL advertises
`sql_merge=True` (`INSERT … ON CONFLICT`); SQLite remains
`sql_merge=False` and fails closed at planning when merge is required.

## Hybrid Execution

A Pipeline Plan may execute partly in SQL and partly in memory.

```text
SQL Source
    │
    ▼
SQL Transformation
    │
    ▼
Polars Transformation
    │
    ▼
SQL Sink
```

The planner chooses execution boundaries while preserving semantics.

## Transactions

Where supported:

```text
Begin
  │
Read
  │
Transform
  │
Validate
  │
Publish
  │
Commit
```

Failures should trigger rollback whenever possible.

## Capability Matching

Planning should verify support for features such as:

- Transactions
- MERGE (when `sql_merge` is required)
- Recursive CTEs
- Window functions
- Staging / temporary tables
- Streaming
- Materialized views

If mandatory capabilities are unavailable, planning fails closed. There is no
silent emulation of unsupported merge, transaction, or dialect features.
The current reference plugin stages intermediates in durable run-scoped tables
(not session TEMP) so handoffs work across connection pools.

## Performance

SQL execution may optimize through:

- Predicate pushdown
- Projection pruning
- Query fusion
- Join pushdown
- Aggregation pushdown
- Batch execution
- Minimal data movement

Optimizations must never alter observable behavior.

## Diagnostics

Execution should report:

- Pipeline identity
- Step identity
- Generated query identifier
- Dialect
- Duration
- Rows processed
- Transaction outcome
- Backend exceptions

## Security

SQL execution should:

- Use parameterized queries
- Avoid string concatenation
- Keep credentials in Resource Providers
- Respect least-privilege database access
- Avoid embedding secrets in generated artifacts

## Best Practices

- Keep SQL implementations portable.
- Prefer logical query builders over raw SQL.
- Let the planner choose execution.
- Validate outputs before publication.
- Declare plugin capabilities accurately.

## Anti-Patterns

Avoid:

- Embedding database credentials in pipelines.
- Mixing pipeline semantics with SQL dialect details.
- Returning unvalidated data.
- Assuming one SQL dialect.

## Key Principle

> SQL execution is a backend implementation of the ETLantic execution
model. It executes validated Pipeline Plans inside relational databases while
preserving the same portable semantics available through every other execution
backend.

## Next Step

Continue with **SQL_PUSHDOWN.md** to learn how ETLantic optimizes SQL
execution through predicate, projection, aggregation, and join pushdown while
preserving correctness.
