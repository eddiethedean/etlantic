# SQL Plugin

**Status: shipped in 0.6.0** (`pipelantic.sql/1`). The reference plugin is
`pipelantic-sql` (PostgreSQL). Discover plugins via the
`pipelantic.sql_plugins` entry point.

A **SQL Plugin** implements the Pipelantic SQL Plugin API for a specific SQL
execution environment.

SQL plugins compile and execute eligible transformation regions inside relational
or analytical databases while preserving the semantics defined by ODCS, DTCS,
DPCS, and the validated Pipeline Plan.

A SQL plugin is more than a storage adapter. It participates in planning,
capability evaluation, SQL compilation, pushdown, execution, validation, and
transaction management.

## Purpose

A SQL plugin is responsible for:

- Compiling logical SQL expressions
- Adapting queries to a SQL dialect
- Executing SQL-native transformation implementations
- Reading from SQL sources
- Writing to SQL sinks
- Supporting SQL pushdown
- Managing transactions
- Reporting structured diagnostics
- Declaring dialect and runtime capabilities

It is **not** responsible for:

- Defining pipeline semantics
- Defining transformation contracts
- Replacing ODCS, DTCS, or DPCS
- Replanning pipelines during execution
- Silently weakening validation requirements

## Architecture

```text
Validated Pipeline Plan
          │
          ▼
    SQL Plugin API
          │
    ┌─────┴─────────────┐
    ▼                   ▼
SQL Planner Hooks   SQL Execution
    │                   │
    ▼                   ▼
Logical SQL IR      Transaction Manager
    │                   │
    └─────────┬─────────┘
              ▼
       Dialect Compiler
              │
              ▼
           Database
```

The SQL plugin consumes a validated plan or SQL-capable plan region.

It must not reinterpret the original Python pipeline definitions directly.

## Plugin Roles

A SQL plugin may fulfill several related roles.

### SQL compiler

Translates logical SQL expressions into dialect-specific SQL.

### SQL executor

Executes compiled statements and returns normalized results.

### SQL source and sink provider

Reads and writes datasets using logical bindings.

### Pushdown provider

Advertises which operations can execute inside the database.

### Capability provider

Describes supported SQL and runtime behavior to the planner.

One package may implement all roles, or a plugin ecosystem may separate shared
compiler logic from database-specific drivers.

## Plugin Interface

Conceptually:

```python
class SqlPlugin:
    name: str
    version: str
    dialect: str

    def capabilities(self) -> SqlCapabilities:
        ...

    def compile(
        self,
        plan: SqlPlan,
        context: CompilationContext,
    ) -> CompiledSql:
        ...

    def execute(
        self,
        compiled: CompiledSql,
        context: ExecutionContext,
    ) -> SqlExecutionResult:
        ...
```

The exact public SDK will evolve, but SQL plugins should expose stable,
structured operations rather than requiring Pipelantic to invoke private
database-library internals.

## Logical SQL Representation

Pipelantic should define or adopt a safe logical SQL representation.

A SQL implementation should return structured expressions rather than use raw
string concatenation as the primary interface.

Conceptually:

```python
@BuildCustomerSummary.implementation("sql")
def build_customer_summary(
    customers: SqlRelation[Customer],
    orders: SqlRelation[Order],
    included_status: str,
) -> SqlQuery[CustomerSummary]:
    return (
        select(
            customers.customer_id,
            customers.full_name,
            count(orders.order_id).alias("paid_order_count"),
            coalesce(sum(orders.order_total), 0.0).alias("paid_order_total"),
        )
        .from_(
            customers.left_join(
                orders,
                on=(
                    (customers.customer_id == orders.customer_id)
                    & (orders.status == parameter("included_status"))
                ),
            )
        )
        .group_by(
            customers.customer_id,
            customers.full_name,
        )
    )
```

Possible implementation foundations include:

- Pipelantic's own SQL expression IR
- SQLAlchemy Core
- A supported relational algebra library
- A carefully constrained adapter interface

The chosen representation must support safe parameter binding and dialect-aware
compilation.

## Raw SQL

Plugins may support raw SQL as an escape hatch.

Conceptually:

```python
@Transformation.implementation("sql-raw")
def implementation(context) -> RawSqlQuery:
    return RawSqlQuery(
        statement="SELECT ... WHERE status = :status",
        parameters={"status": context.parameters.status},
    )
```

Raw SQL should require:

- Explicit dialect expectations
- Bound parameters
- Declared input and output contracts
- Clear portability limitations
- Structured validation and diagnostics

Raw SQL should not be the only SQL authoring model.

## SQL Relations

SQL inputs should be represented as typed logical relations.

```python
customers: SqlRelation[Customer]
```

A relation may refer to:

- A physical table
- A view
- A subquery
- A common table expression
- An upstream SQL-capable step
- A temporary materialization

The relation's contract remains authoritative regardless of physical form.

## SQL Queries

A SQL implementation should produce a typed result.

```python
SqlQuery[CustomerSummary]
```

The output type tells the planner and validator which contract governs the
result.

The SQL plugin must verify that the compiled projection can satisfy that
contract.

## Capabilities

Every SQL plugin should publish a structured capability model.

Conceptually:

```python
SqlCapabilities(
    dialect="postgresql",
    reads=True,
    writes=True,
    transactions=True,
    savepoints=True,
    merge=True,
    upsert=True,
    create_table_as=True,
    temporary_tables=True,
    common_table_expressions=True,
    recursive_ctes=True,
    window_functions=True,
    returning=True,
    streaming_reads=True,
    parameter_binding=True,
    schema_introspection=True,
)
```

Capabilities should cover both SQL syntax and runtime behavior.

## Operation Capabilities

Plugins should declare support for logical operations such as:

- Projection
- Filtering
- Sorting
- Joins
- Aggregation
- Window functions
- Set operations
- Deduplication
- Type casts
- Conditional expressions
- JSON operations
- Array operations
- Date and time operations
- String operations

A plugin may support an operation only for some type combinations.

Capability declarations should be expressive enough to communicate these
limits.

## Type Mapping

SQL plugins map logical contract types to database types.

Mappings may include:

- Integer widths
- Decimal precision and scale
- Strings and length constraints
- Booleans
- Dates
- Times
- Timestamps
- Time zones
- UUIDs
- JSON
- Arrays
- Binary values
- Enums

Plugins must report:

- Exact mappings
- Lossy mappings
- Unsupported mappings
- Backend-specific limitations

A lossy mapping must not be accepted silently when the contract requires exact
semantics.

## Null Semantics

SQL uses three-valued logic.

Plugins must define how they preserve:

- Nullable fields
- Required fields
- Null-safe equality
- Boolean expressions
- Join behavior
- Aggregate behavior
- Null ordering
- `IN` and `NOT IN` behavior

Dialect differences should be surfaced through capability and compatibility
checks.

## Numeric Semantics

Plugins must account for:

- Integer overflow
- Decimal precision
- Floating-point behavior
- Division rules
- Rounding
- Aggregation result types

The SQL result must remain compatible with the declared output contract.

## Date and Time Semantics

Plugins should declare behavior for:

- Date
- Time
- Naive datetime
- Zoned datetime
- Timestamp precision
- Time-zone conversion
- Interval types
- Database session time zone

Planning should reject a SQL implementation when required time semantics cannot
be preserved.

## Identifier Handling

SQL plugins must safely handle:

- Catalog names
- Schema names
- Table names
- Column names
- Aliases
- Reserved words
- Case sensitivity
- Quoting rules

Dynamic identifiers should be validated and quoted through the dialect compiler.

User values must never be inserted through identifier interpolation.

## Parameter Binding

All user-controlled values should use bound parameters.

```sql
SELECT *
FROM orders
WHERE status = :status
```

Plugins should not build value-bearing SQL through string concatenation.

Parameter handling should preserve:

- Type information
- Null behavior
- Collection parameters
- Driver compatibility
- Prepared statement support where available

## Compilation

Compilation transforms a logical SQL plan into one or more executable statements.

Compiled output may contain:

- SQL text or driver-native statement objects
- Bound parameter specifications
- Expected result contracts
- Temporary object requirements
- Transaction requirements
- Statement dependencies
- Cleanup actions
- Diagnostic metadata

Conceptually:

```python
CompiledSql(
    statements=[...],
    parameters={...},
    output_contract=CustomerSummary,
    transactional=True,
)
```

## Deterministic Compilation

Equivalent logical SQL plans should produce semantically equivalent compiled
output.

Stable compilation supports:

- Testing
- Caching
- Review
- Query inspection
- Reproducible plans
- Diagnostic attribution

Formatting differences must not alter semantics.

## SQL Pushdown

SQL plugins participate in pushdown planning by identifying executable
operations and regions.

A plugin may accept:

```text
Filter
  │
  ▼
Join
  │
  ▼
Aggregate
```

and compile them into one SQL statement or CTE chain.

The plugin must reject pushdown when it cannot preserve:

- Contract semantics
- Validation boundaries
- Failure boundaries
- Lineage
- Ordering
- Determinism
- Null and type behavior

## Step Fusion

SQL plugins may fuse adjacent SQL-capable steps.

Fusion must preserve logical step identities in:

- Lineage
- Diagnostics
- Documentation
- Execution events
- Compatibility analysis

One physical statement may represent several logical steps, but the plugin must
retain attribution metadata.

## Materialization

Plugins may materialize intermediate results using:

- Temporary tables
- Persistent staging tables
- Views
- Materialized views
- CTEs
- Result sets

Materialization strategy should consider:

- Reuse
- Failure isolation
- Retry boundaries
- Validation boundaries
- Transaction limits
- Backend capabilities
- Cleanup requirements

Temporary objects should use collision-safe names derived from execution
identity rather than unsanitized user input.

## Transactions

SQL plugins should describe their transaction behavior.

Capabilities may include:

- Atomic multi-statement transactions
- Savepoints
- Transactional DDL
- Autocommit-only operations
- Distributed transactions
- Idempotent writes

The execution plan should state which steps or regions require one transaction.

Plugins must not claim atomicity when the backend cannot provide it.

## Write Strategies

SQL plugins may support:

- Append
- Replace
- Insert
- Update
- Delete and insert
- Merge
- Upsert
- Create table as select
- Insert select
- Snapshot publication
- Staging and swap

Write strategies belong to profile or binding configuration unless they affect
portable pipeline semantics.

## Schema Management

Plugins may support:

- Schema inspection
- Table existence checks
- Table creation
- Compatible migrations
- Constraint creation
- Index creation
- View creation

Automatic schema management must derive from contract metadata through public
ContractModel APIs.

Plugins should not invent independent schema semantics.

## Validation

SQL plugins may enforce data contracts through:

- Schema inspection
- Generated validation queries
- `CHECK` constraints
- `NOT NULL` constraints
- Type checks
- Uniqueness checks
- Foreign-key checks
- Pre-publication queries
- Post-query ContractModel fallback

Plugins must publish which rules are:

- Enforced natively
- Checked through generated SQL
- Checked after materialization
- Unsupported

Unsupported mandatory validation must prevent planning or trigger an explicit
fallback.

## Data Quality Queries

A plugin may compile quality gates into SQL.

Examples include:

```sql
SELECT COUNT(*) AS invalid_count
FROM result
WHERE customer_id <= 0;
```

or:

```sql
SELECT email, COUNT(*)
FROM result
GROUP BY email
HAVING COUNT(*) > 1;
```

Quality queries should return structured results rather than require users to
parse arbitrary query output.

## Sources

A SQL source plugin should support logical bindings such as:

```python
Source[Customer](
    binding="customers_source",
)
```

The profile may resolve the binding to:

- Database resource
- Catalog
- Schema
- Table or view
- Query
- Snapshot
- Partition predicate

Queries used as source bindings must still declare the output contract.

## Sinks

A SQL sink plugin should write only data compatible with its declared contract.

```python
Sink[CustomerSummary](
    input=summary.result,
    binding="customer_summary_sink",
)
```

The plugin should validate before publication according to the active policy.

## Cross-Database Execution

A SQL plugin should not assume all SQL relations share one database.

The planner must identify execution locality.

Possible cases include:

- Same connection and database
- Different schemas in one database
- Different databases on one server
- Federated query support
- Separate systems requiring materialization

Cross-system movement should be explicit in the plan.

## Hybrid Execution

A pipeline may transition between SQL and dataframe execution.

```text
SQL relation
    │
    ▼
SQL-capable steps
    │
    ▼
Materialize to Arrow or DataFrame
    │
    ▼
Polars-only step
    │
    ▼
Write through SQL sink
```

The SQL plugin should support standardized exchange formats where practical,
especially Apache Arrow.

## Streaming and Chunked Reads

Plugins may support:

- Server-side cursors
- Chunked result retrieval
- Arrow batches
- Partitioned reads
- Streaming result sets

Streaming capabilities should include clear transaction and resource-lifecycle
semantics.

## Resource Providers

Database connections and credentials should be supplied through Resource
Providers.

Conceptually:

```text
SQL Plugin
    │
    ▼
Database Resource Provider
    │
    ▼
Connection or Engine
```

The SQL plugin should not read credentials directly from pipeline contracts.

## Async Support

A SQL plugin may support:

- Synchronous drivers
- Asynchronous drivers
- Both

Pipelantic should normalize invocation while respecting driver constraints.

A synchronous database client may run through an appropriate thread or worker
strategy when used inside an asynchronous execution environment.

## Connection Management

Plugins should handle:

- Connection acquisition
- Connection pooling
- Transaction scope
- Session configuration
- Statement timeouts
- Cleanup
- Broken connection handling

Connection objects should not leak into public pipeline interfaces.

## Cancellation

Where supported, plugins should propagate cancellation to the database driver.

Cancellation behavior should be documented, especially for:

- Long-running queries
- Transaction rollback
- Temporary object cleanup
- Remote query cancellation

## Retries

SQL retries require careful classification.

Potentially retryable failures include:

- Transient network errors
- Deadlocks
- Serialization failures
- Connection resets
- Temporary resource exhaustion

Non-retryable failures include:

- Invalid SQL
- Contract incompatibility
- Missing required permissions
- Unsupported type mappings

Plugins should return typed failure categories to the execution layer.

## Idempotency

Plugins should document whether write operations are idempotent.

Retrying an `INSERT` may duplicate records unless:

- The write uses an idempotency key
- The operation is transactional and rolled back
- The strategy uses merge or replacement
- The sink provides deduplication guarantees

Planning should consider idempotency before applying retry policies.

## Diagnostics

SQL plugins should emit structured diagnostics for:

- Compilation failures
- Capability mismatches
- Type mapping problems
- Unsupported expressions
- Query execution errors
- Transaction failures
- Validation failures
- Cleanup failures
- Fallback decisions

A diagnostic may include:

- Plugin name and version
- Dialect
- Pipeline identity
- Step identity
- Logical operation
- Statement identifier
- Backend error code
- Redacted SQL excerpt
- Suggested remediation

Sensitive parameter values should be redacted.

## Query Inspection

Compiled SQL should be inspectable before execution.

Conceptually:

```python
compiled = sql_plugin.compile(sql_plan, context)

print(compiled.render(redact_parameters=True))
```

Inspection is valuable for:

- Debugging
- Code review
- Performance analysis
- Governance
- Explain plans

## Explain Plans

Plugins may expose explain-plan support.

```python
explanation = sql_plugin.explain(
    compiled,
    analyze=False,
)
```

`ANALYZE` or execution-bearing explain operations should require explicit
permission because they may run the query.

## Observability

SQL plugins should emit execution metadata such as:

- Statement duration
- Rows read
- Rows written
- Bytes transferred where available
- Transaction outcome
- Retry count
- Materialization count
- Pushdown coverage
- Database query identifier

Operational metadata supplements the logical pipeline model.

## Lineage

The plugin should preserve and enrich lineage.

Logical lineage comes from the Pipeline Plan.

Runtime lineage may add:

- Physical database objects
- Query identifiers
- Materialized intermediate tables
- Actual source and sink locations

Runtime lineage must not replace logical ODCS, DTCS, and DPCS relationships.

## Security

SQL plugins should follow secure defaults.

Requirements include:

- Parameterized queries
- Safe identifier quoting
- External credential providers
- Least-privilege access
- Redacted diagnostics
- No secrets in generated artifacts
- Controlled raw SQL support
- Safe temporary object names
- Restricted query inspection for sensitive systems

## Plugin Registration

Conceptually:

```python
from pipelantic.plugins import register_sql_plugin


register_sql_plugin(
    PostgreSqlPlugin(),
)
```

Normal deployments should prefer automatic discovery through package entry
points or the standard Pipelantic plugin registry.

## Package Naming

Shipped in 0.6.0:

- `pipelantic-sql` — PostgreSQL reference plugin

Additional dialect packages (for example DuckDB, Snowflake, BigQuery) may
follow the same protocol later; they are not part of this release.

## Version Metadata

Every SQL plugin should publish:

- Plugin version
- Supported Pipelantic version
- Supported Plugin SDK version
- Supported DTCS version
- Supported DPCS version
- Dialect identity and version range
- Driver compatibility
- Capability metadata

## Testing

SQL plugins should run shared conformance tests.

Required test categories include:

- Capability declarations
- Type mappings
- Parameter binding
- Null semantics
- Numeric semantics
- Date and time semantics
- Projection
- Filtering
- Joins
- Aggregation
- Window functions where supported
- Transactions
- Rollback
- Write strategies
- Pushdown
- Step fusion
- Validation
- Diagnostics
- Retry classification
- Idempotency behavior
- Sync and async execution
- Lineage preservation

## Cross-Backend Equivalence

Where possible, SQL plugin results should be compared against the reference
Polars implementation.

Equivalent inputs should produce contract-compatible and logically equivalent
outputs.

Differences caused by backend behavior must be normalized or documented as
unsupported.

## Reference Fixtures

The SDK should provide reusable fixtures for:

- SQLite
- PostgreSQL
- DuckDB
- Other officially supported test backends

Plugins for managed cloud systems may supply optional integration test suites.

## Best Practices

- Depend only on public Plugin SDK interfaces.
- Use structured SQL expressions and bound parameters.
- Declare capabilities precisely.
- Preserve validation and failure boundaries.
- Keep contracts and pipelines dialect-independent.
- Make compiled SQL inspectable.
- Report lossy type mappings.
- Preserve logical step identity through fusion.
- Use Resource Providers for connections.
- Test against shared conformance suites.

## Anti-Patterns

Avoid:

- Treating a SQL plugin as only a read/write adapter.
- Embedding dialect-specific SQL in transformation contracts.
- Concatenating user values into SQL.
- Claiming unsupported transaction guarantees.
- Silently coercing incompatible types.
- Dropping validation because the query executes successfully.
- Fusing steps across required semantic boundaries.
- Replanning the pipeline during execution.
- Leaking driver connection objects into public APIs.
- Assuming all SQL sources are co-located.

## Key Principle

> A SQL Plugin turns SQL-capable regions of a validated Pipeline Plan into safe,
> dialect-aware, database-native execution while preserving contracts,
> validation, lineage, failure semantics, and observable behavior.

## Next Step

Continue with **SQL_DIALECT.md** to define the SDK contract for dialect-specific
type mappings, syntax capabilities, compilation rules, and portability
diagnostics.
