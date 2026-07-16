# SQL Dialect

**Status: shipped in 0.6.0** as part of `pipelantic.sql/1`. The reference
dialect path is PostgreSQL via `pipelantic-sql`. SQLite may be used for demos;
it is not a full conformance target.

A **SQL Dialect** defines the database-specific rules used by a Pipelantic
SQL Plugin to compile logical SQL expressions into valid, semantically
equivalent SQL for a target database.

The dialect layer isolates differences in syntax, data types, functions,
identifier rules, transaction behavior, and feature support. Pipeline authors
and transformation contracts remain independent of these differences.

## Purpose

A SQL dialect is responsible for:

- Mapping logical types to database types
- Compiling logical SQL expressions
- Quoting identifiers safely
- Declaring supported SQL features
- Normalizing dialect-specific behavior
- Reporting portability limitations
- Preserving contract and transformation semantics

It is **not** responsible for:

- Pipeline modeling
- Pipeline planning
- Runtime connection management
- Credential resolution
- Orchestration
- Defining transformation semantics

## Architecture

```text
Logical SQL Plan
       │
       ▼
SQL Plugin
       │
       ▼
SQL Dialect
       │
       ├── Type Mapping
       ├── Syntax Rules
       ├── Function Mapping
       ├── Capability Model
       └── Portability Diagnostics
       │
       ▼
Compiled SQL
```

The SQL Plugin owns execution.

The SQL Dialect owns database-specific compilation behavior.

## Why Dialects Matter

SQL is standardized, but real databases differ significantly.

Differences include:

- Identifier quoting
- Boolean types
- String concatenation
- Date and time functions
- `MERGE` support
- `RETURNING` support
- Temporary table behavior
- JSON operations
- Array types
- Window semantics
- Null ordering
- Transactional DDL
- Parameter styles

The dialect layer prevents these differences from leaking into portable
Pipelantic contracts.

## Dialect Identity

Every dialect should expose a stable identity.

Conceptually:

```python
SqlDialectIdentity(
    name="postgresql",
    version_range=">=14,<19",
)
```

Identity metadata may include:

- Dialect name
- Supported database versions
- Driver compatibility
- Plugin version
- Capability profile version

## Dialect Interface

Conceptually:

```python
class SqlDialect:
    name: str

    def capabilities(self) -> SqlDialectCapabilities:
        ...

    def map_type(self, logical_type) -> SqlTypeMapping:
        ...

    def compile_expression(self, expression, context) -> str:
        ...

    def quote_identifier(self, identifier: str) -> str:
        ...
```

The exact API may evolve, but dialect implementations should remain isolated
behind public SDK interfaces.

## Capability Model

A dialect should advertise syntax and semantic capabilities.

Conceptually:

```python
SqlDialectCapabilities(
    common_table_expressions=True,
    recursive_ctes=True,
    window_functions=True,
    merge=True,
    upsert=True,
    returning=True,
    create_table_as=True,
    temporary_tables=True,
    transactional_ddl=True,
    arrays=True,
    json=True,
    uuid=True,
    time_zones=True,
    nulls_first_last=True,
)
```

Capabilities should describe support, limitations, and any version-dependent
behavior.

## Feature Levels

Capabilities may need more detail than a boolean.

Conceptually:

```python
FeatureSupport(
    supported=True,
    level="partial",
    notes="MERGE supports matched and not-matched branches but not all clauses.",
)
```

Possible states include:

- Supported
- Partially supported
- Emulated
- Unsupported
- Version dependent
- Driver dependent

Planning should treat emulated and partial support differently from native
support when semantics or performance matter.

## Type Mapping

The dialect maps logical ContractModel types to SQL types.

Examples include:

- Integer
- Big integer
- Decimal
- Float
- Boolean
- String
- Binary
- Date
- Time
- Datetime
- Timestamp with time zone
- UUID
- JSON
- Array
- Enum

A mapping result should indicate whether it is:

- Exact
- Compatible
- Lossy
- Unsupported

Conceptually:

```python
SqlTypeMapping(
    sql_type="NUMERIC(18, 4)",
    fidelity="exact",
)
```

## Integer Types

Dialects differ in integer widths and overflow behavior.

The mapping layer should account for:

- Signedness
- Minimum and maximum values
- Storage width
- Auto-increment behavior
- Sequence support
- Overflow behavior

A logical integer contract must not be mapped to a narrower SQL type silently.

## Decimal and Numeric Types

Decimal mappings should preserve:

- Precision
- Scale
- Rounding expectations
- Overflow behavior

If the target dialect cannot preserve the declared precision, planning should
report a compatibility error or require explicit acceptance of a lossy mapping.

## Floating-Point Types

Dialects may expose different floating-point types and precision guarantees.

The dialect should document mappings for:

- Single precision
- Double precision
- Database-specific floating types
- NaN and infinity support

## String Types

String mappings may consider:

- Fixed versus variable length
- Maximum length
- Unicode behavior
- Collation
- Case sensitivity
- Large text types

Contract constraints such as `max_length` should be preserved where supported.

## Boolean Types

Some dialects have native booleans.

Others emulate booleans using integers, strings, or constraints.

The dialect must preserve:

- Accepted values
- Comparison behavior
- Null behavior
- Serialization behavior

## Date and Time Types

Dialect mappings should distinguish:

- Date
- Time
- Naive datetime
- Zoned datetime
- Timestamp precision
- Interval
- Time-zone support

The dialect must report when time-zone semantics cannot be preserved exactly.

## UUID Types

UUID may map to:

- Native UUID
- Fixed-length binary
- Fixed-length string
- Variable-length string

The mapping should document storage and comparison semantics.

## JSON Types

JSON support varies significantly.

A dialect may support:

- Native JSON
- Binary JSON
- Text-backed JSON
- JSON path queries
- Indexing
- Mutation functions

The capability model should distinguish storage support from expression support.

## Array Types

Array support may be:

- Native
- Emulated through JSON
- Emulated through child tables
- Unsupported

Emulation must not be treated as equivalent automatically if observable
semantics differ.

## Enum Types

Enums may map to:

- Native enum types
- Check-constrained strings
- Lookup tables
- Plain strings

The dialect should indicate whether the allowed value constraint is enforced by
the database.

## Identifier Rules

The dialect must define:

- Quote character or quoting syntax
- Case folding
- Maximum identifier length
- Reserved words
- Unicode support
- Catalog and schema qualification
- Temporary object naming rules

Conceptually:

```python
quoted = dialect.quote_identifier("order")
```

The result must be safe for the target dialect.

## Identifier Validation

Dynamic identifiers should be validated before compilation.

The dialect should reject:

- Invalid characters
- Unsafe qualification
- Unsupported identifier lengths
- Empty identifiers
- Unescaped separator syntax

User values must never be treated as identifiers.

## Parameter Styles

Drivers use different parameter styles.

Examples include:

- Named parameters
- Positional parameters
- Question-mark parameters
- Numeric parameters
- Driver-native bind objects

The dialect or driver adapter should translate Pipelantic's logical
parameters into the required format.

## Expression Compilation

The dialect compiles logical expressions such as:

- Column references
- Literals
- Parameters
- Comparisons
- Boolean expressions
- Arithmetic
- Conditional expressions
- Casts
- Function calls
- Aggregates
- Window expressions

Compilation should preserve precedence and use parentheses where necessary.

## Function Mapping

Functions vary by database.

A logical function registry may map operations such as:

```text
lower
trim
substring
date_trunc
coalesce
count
sum
current_timestamp
```

to dialect-specific syntax.

Unsupported functions should produce diagnostics rather than silently changing
behavior.

## String Concatenation

String concatenation may use:

- `||`
- `CONCAT(...)`
- `+`
- Dialect-specific functions

The dialect must account for null behavior because some operators return null
when any operand is null while others do not.

## Date and Time Functions

Common portability issues include:

- Date truncation
- Date addition
- Timestamp difference
- Time-zone conversion
- Current time
- Interval syntax
- Week numbering

The dialect should expose semantic function mappings rather than simple textual
aliases.

## Null Semantics

Dialect behavior must be defined for:

- Null comparisons
- Null-safe equality
- Sorting nulls
- Aggregation
- Concatenation
- Boolean expressions
- `IN` and `NOT IN`
- Conditional expressions

When a dialect lacks a native operation, the compiler may emulate it only when
semantics are preserved.

## Ordering

Dialects differ in default null ordering and collation.

The dialect should support explicit compilation of:

- Ascending and descending order
- Nulls first and nulls last
- Collation where portable
- Stable tie-breaking when required

Ordering should be generated only when the transformation or pipeline semantics
require it.

## Joins

The dialect capability model should describe support for:

- Inner joins
- Left joins
- Right joins
- Full joins
- Cross joins
- Lateral joins
- Semi joins
- Anti joins
- Null-safe join predicates

Unsupported joins may be rewritten only when equivalence is guaranteed.

## Aggregations

The dialect should define support for:

- Standard aggregates
- Distinct aggregates
- Filtered aggregates
- Ordered aggregates
- Approximate aggregates
- Statistical aggregates

Return types must remain compatible with output contracts.

## Window Functions

Window capabilities should include:

- Partitioning
- Ordering
- Row frames
- Range frames
- Groups frames
- Ranking functions
- Offset functions
- Aggregate windows
- Null treatment options

Partial window support should be represented explicitly.

## Common Table Expressions

Capabilities should distinguish:

- Non-recursive CTEs
- Recursive CTEs
- Materialized CTE hints
- Non-materialized hints
- Data-modifying CTEs

The compiler may use CTEs for readability, fusion, or intermediate semantics.

## Subqueries

The dialect should declare support for subqueries in:

- `FROM`
- `WHERE`
- `SELECT`
- `JOIN`
- `INSERT`
- `UPDATE`
- `DELETE`

Correlated subqueries may require separate capability declarations.

## Set Operations

Supported operations may include:

- `UNION`
- `UNION ALL`
- `INTERSECT`
- `EXCEPT`

The dialect should specify support for duplicate-preserving and distinct
semantics.

## Data Modification

The dialect should declare support for:

- `INSERT`
- `UPDATE`
- `DELETE`
- `MERGE`
- Upsert extensions
- `RETURNING`
- Multi-row values
- Insert from select
- Update from join
- Delete using join

These capabilities influence sink compilation and incremental loading.

## Merge and Upsert

Merge semantics differ widely.

The dialect should describe:

- Match clauses
- Multiple match branches
- Insert branches
- Delete branches
- Source deduplication requirements
- Concurrency behavior
- Return values

A generic Pipelantic merge strategy should compile only when equivalent
semantics can be guaranteed.

## Table Creation

Capabilities may include:

- `CREATE TABLE`
- `CREATE TABLE AS SELECT`
- Temporary tables
- Unlogged tables
- Tables created from contract schema
- Constraints
- Indexes
- Partitioning
- Clustering

Schema generation should use ContractModel's normalized contract metadata.

## Temporary Objects

The dialect should define:

- Temporary table syntax
- Scope
- Lifetime
- Transaction visibility
- Session visibility
- Cleanup behavior
- Naming limits

Temporary materialization must be safe across concurrent pipeline runs.

## Views and Materialized Views

The dialect may support:

- Standard views
- Temporary views
- Materialized views
- Refresh operations
- Replace semantics

These may serve as optimization or publication targets.

## Transaction Semantics

Transaction capabilities should include:

- Autocommit behavior
- Explicit transactions
- Savepoints
- Isolation levels
- Read-only transactions
- Transactional DDL
- Nested transaction behavior
- Statement-level atomicity

The SQL Plugin uses this metadata when building execution boundaries.

## Isolation Levels

The dialect should expose supported isolation levels and any backend-specific
names.

Examples include:

- Read uncommitted
- Read committed
- Repeatable read
- Serializable
- Snapshot

Pipelantic should request logical isolation requirements rather than
hard-code vendor syntax.

## Locking

Capabilities may include:

- Row locks
- Table locks
- `FOR UPDATE`
- Skip locked
- Nowait
- Advisory locks

Locking should be used only when required by execution or publication
semantics.

## Savepoints

Savepoint support matters for partial rollback and nested execution regions.

The dialect should describe:

- Create
- Rollback to savepoint
- Release
- Interaction with DDL
- Driver limitations

## Error Classification

The dialect or driver adapter should help classify backend errors.

Categories may include:

- Syntax error
- Type error
- Constraint violation
- Deadlock
- Serialization failure
- Permission error
- Authentication failure
- Missing object
- Connection failure
- Timeout
- Resource exhaustion

Classification enables safe retry and diagnostics behavior.

## Retryability

The dialect should identify error categories that may be retryable.

Retryability may depend on:

- Transaction state
- Statement type
- Idempotency
- Driver error code
- Backend version

The dialect should provide evidence, not a blanket retry flag.

## Explain Plans

The dialect may support:

- Explain without execution
- Explain analyze
- Format selection
- JSON plans
- Text plans
- Estimated costs
- Actual row counts

Execution-bearing explain modes should require explicit consent.

## Schema Introspection

The dialect may expose metadata retrieval for:

- Tables
- Views
- Columns
- Types
- Nullability
- Constraints
- Indexes
- Primary keys
- Foreign keys
- Partitions

Introspection supports source validation, sink compatibility, and schema
management.

## Metadata Normalization

Database metadata should be normalized into Pipelantic structures.

The core should not depend on vendor-specific catalog row formats.

## Dialect Compilation Context

Compilation may require context such as:

- Database version
- Driver
- Active capabilities
- Current schema
- Identifier policy
- Parameter style
- Contract type mappings
- Profile settings

Conceptually:

```python
DialectCompilationContext(
    database_version="16.3",
    parameter_style="named",
    default_schema="public",
)
```

## Version-Aware Behavior

Dialect behavior may vary by database version.

Examples include:

- Newly introduced `MERGE`
- Expanded JSON support
- Improved window functions
- Changed identifier limits
- New type support

Capability evaluation should use the actual target version when known.

## Driver Adapters

Database dialect and Python driver behavior are related but distinct.

A driver adapter may handle:

- Parameter formatting
- Connection objects
- Cursor behavior
- Async APIs
- Server-side cursors
- Result conversion
- Error objects

The same SQL dialect may support multiple drivers.

## Compilation Output

A compiled statement should include structured metadata.

Conceptually:

```python
CompiledSqlStatement(
    sql="SELECT ...",
    parameters={"status": "paid"},
    output_contract=CustomerSummary,
    statement_id="build-summary",
)
```

Multiple statements may be grouped into one compiled SQL program.

## Portability Diagnostics

When a logical operation cannot be compiled portably, the dialect should explain
why.

Examples include:

- Unsupported function
- Lossy type mapping
- Different null semantics
- Unsupported merge clause
- Time-zone incompatibility
- Unsupported window frame
- Identifier length violation

Diagnostics should include possible alternatives when known.

## Fallback Guidance

The dialect may suggest:

- Use another SQL implementation
- Materialize and use Polars
- Split the transformation
- Change the execution profile
- Require a newer database version
- Use an explicit extension

Fallback suggestions should not be applied automatically when they change
semantics.

## Extension Mechanism

Dialect plugins may expose namespaced extensions for:

- Vendor-specific functions
- Types
- Table options
- Indexes
- Storage formats
- Optimizer hints

Extensions should remain explicit and must not redefine standard logical
operations.

## Vendor-Specific Expressions

Conceptually:

```python
vendor_function(
    namespace="postgresql",
    name="jsonb_path_query",
    arguments=[...],
)
```

Use of a vendor-specific expression should mark the SQL implementation's
portability requirements.

## Security

Dialect implementations should enforce:

- Safe identifier quoting
- Parameter binding
- No unescaped value interpolation
- Safe generated aliases
- Restricted extension rendering
- Redaction of sensitive compiled parameters
- Safe handling of comments and metadata

The dialect compiler should treat all model-provided text as untrusted.

## Determinism

Compilation should be deterministic for equivalent inputs and context.

Stable behavior includes:

- Alias generation
- Parameter naming
- Clause ordering
- Identifier quoting
- Statement ordering
- Diagnostic codes

Determinism improves caching, testing, inspection, and governance.

## Caching

Dialect compilation results may be cached when the following remain stable:

- Logical SQL plan
- Dialect version
- Database version
- Driver capabilities
- Compilation options
- Contract mappings

Cached SQL must not contain unsafe execution-specific secrets.

## Testing

Every dialect should pass shared tests for:

- Identifier quoting
- Parameter binding
- Type mappings
- Null semantics
- Boolean logic
- Numeric behavior
- Date and time behavior
- Function mappings
- Joins
- Aggregations
- Window functions
- CTEs
- Set operations
- DML
- Transactions
- Error classification
- Diagnostics
- Deterministic compilation

## Golden SQL Tests

Golden tests may verify generated SQL text.

They should be paired with semantic execution tests because equivalent SQL may
have multiple valid textual forms.

## Semantic Equivalence Tests

Dialect output should be compared against:

- Reference Polars implementations
- Contract-defined expected results
- Cross-dialect fixtures

Tests should emphasize observable semantics over formatting.

## Package Organization

A possible package layout:

```text
pipelantic_sql/
├── dialects/
│   ├── base.py
│   ├── sqlite.py
│   ├── postgresql.py
│   ├── duckdb.py
│   └── snowflake.py
├── compiler/
├── expressions/
├── types/
├── diagnostics/
└── testing/
```

Database-specific packages may also be distributed independently.

## Recommended Practices

- Keep dialect logic isolated from pipeline contracts.
- Declare exact and partial capabilities accurately.
- Report lossy mappings.
- Use safe parameter binding.
- Normalize vendor behavior into logical semantics.
- Make version-dependent support explicit.
- Preserve deterministic compilation.
- Test semantic equivalence across backends.
- Keep vendor extensions namespaced.
- Produce actionable portability diagnostics.

## Anti-Patterns

Avoid:

- Treating all SQL databases as equivalent.
- Hiding dialect differences inside raw strings.
- Silently emulating behavior with different semantics.
- Mapping types without fidelity metadata.
- Assuming driver behavior from dialect name alone.
- Using string concatenation for values or identifiers.
- Claiming native support for emulated features.
- Applying vendor extensions implicitly.
- Making pipeline authors select SQL syntax directly.

## Key Principle

> A SQL Dialect translates Pipelantic's logical SQL semantics into
> database-specific syntax while making every capability, limitation, type
> mapping, and portability tradeoff explicit.

## Next Step

Continue with [Testing Plugins](TESTING_PLUGINS.md) to validate dialect
capabilities, deterministic compilation, and failure behavior.
