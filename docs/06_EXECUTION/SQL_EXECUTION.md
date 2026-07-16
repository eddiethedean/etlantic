# SQL Execution

**Status: shipped in 0.6.0** for the `pipelantic-sql` PostgreSQL reference
plugin. SQLite is usable for local demos; it is not the conformance reference.

The SQL Execution subsystem defines how Pipelantic executes validated
Pipeline Plans directly within SQL databases.

Unlike dataframe execution backends, SQL execution compiles eligible
transformations into database-native operations. This allows computation to run
where the data already resides while preserving the semantics defined by ODCS,
DTCS, and DPCS.

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
def normalize_customers(...):
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
- MERGE / UPSERT
- DELETE
- UPDATE

Support depends on plugin capabilities.

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
- MERGE
- Recursive CTEs
- Window functions
- Temporary tables
- Streaming
- Materialized views

If mandatory capabilities are unavailable, planning fails closed. There is no
silent emulation of unsupported merge, transaction, or dialect features.

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

> SQL execution is a backend implementation of the Pipelantic execution
model. It executes validated Pipeline Plans inside relational databases while
preserving the same portable semantics available through every other execution
backend.

## Next Step

Continue with **SQL_PUSHDOWN.md** to learn how Pipelantic optimizes SQL
execution through predicate, projection, aggregation, and join pushdown while
preserving correctness.
