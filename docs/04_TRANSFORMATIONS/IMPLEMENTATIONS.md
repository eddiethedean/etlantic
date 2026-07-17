# Implementations

An implementation provides the executable behavior for a `Transformation`.

Transformations describe **what** a data operation does. Implementations describe
**how** it is executed for a particular runtime.

This separation is one of ETLantic's core architectural principles.

## Interface vs. Implementation

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]
```

The class above is the transformation contract.

Execution is provided separately.

```python
@NormalizeCustomers.implementation("polars")
def normalize(customers, minimum_age):
    ...
```

## Portable definitions (0.11 authoring)

ETLantic exposes one closed, PySpark-inspired relational definition that
normalizes to the published DTCS 3.0 `dtcs.transform-plan/2` protocol
(v1 readable). Engine plugins that **compile** those plans remain 0.12+:

```python
from etlantic.transform import functions as F


@NormalizeCustomers.portable
def normalize(customers, minimum_age):
    return customers.filter(F.col("age") >= minimum_age)
```

Portable authoring is available in 0.11; compilers remain 0.12+. Native
`@implementation()` registration remains required for execution and for
non-portable behavior. See
[Portable Transformations](PORTABLE_TRANSFORMATIONS.md).

Portable support is capability-based. Plugins claim exact DTCS profiles,
actions, functions, operators, types, and modes after passing their conformance
fixtures; merely offering similar dataframe methods is insufficient.

## Why Separate Them?

Keeping implementations separate allows:

- Multiple execution engines
- Easier testing
- Runtime portability
- Cleaner contracts
- Better documentation
- Independent optimization

## Multiple Implementations

A single transformation may target several runtimes.

```python
@NormalizeCustomers.implementation("polars")
def normalize(...):
    ...

@NormalizeCustomers.implementation("pandas")
def normalize(...):
    ...

@NormalizeCustomers.implementation("sql")
def normalize(...):
    ...
```

ETLantic chooses the implementation through the active execution profile.

## Execution Profiles

Use `Profile` (there is no separate `ExecutionProfile` type):

```python
from etlantic import Profile

Profile(
    name="local",
    dataframe_engine="polars",
)

Profile(
    name="sql-prod",
    sql_engine="sql",
)
```

Changing profiles changes the implementation—not the transformation contract.
SQL implementations receive `RelationRef` handles and return SQL query
objects; they do not fetch rows into Python unless a hybrid boundary requires
it.

## Sync and Async

Both synchronous and asynchronous implementations are supported.

```python
@NormalizeCustomers.implementation("polars")
def normalize(...):
    ...
```

```python
@NormalizeCustomers.implementation("remote")
async def normalize(...):
    ...
```

ETLantic normalizes invocation internally so authors do not manage event
loops or thread pools directly.

## Signature Validation

Implementations must satisfy their transformation contract.

ETLantic validates:

- Required inputs
- Required parameters
- Declared outputs
- Parameter types
- Return structure

Planning should fail if an implementation cannot satisfy the declared interface.

## Return Values

Implementations should return values matching the declared outputs.

```python
class ValidateCustomers(Transformation):
    customers: Input[RawCustomer]

    valid: Output[Customer]
    rejected: Output[RejectedCustomer]
```

Conceptually:

```python
return {
    "valid": valid_df,
    "rejected": rejected_df,
}
```

ETLantic validates the returned outputs before they continue downstream.

## Runtime Independence

Implementations may use:

- Polars
- Pandas
- DuckDB
- SQL
- Spark
- Remote services
- Future plugins

The transformation contract never depends on these libraries.

## Callbacks

Implementations may trigger lifecycle callbacks such as:

- Invalid input
- Invalid output
- Execution failure
- Retry
- Completion

Callbacks remain independent of execution engines.

## Registration

Implementations are registered against a transformation rather than embedded
inside it.

This allows third-party packages to provide optimized implementations without
changing the original transformation contract.

## Discovery

ETLantic discovers implementations during planning.

Selection considers:

- Execution profile
- Runtime capabilities
- Plugin availability
- Version compatibility

## Best Practices

- Keep contracts execution-agnostic.
- Register one implementation per runtime.
- Reuse business logic where practical.
- Validate outputs before returning them.
- Prefer native capabilities of each runtime.

## Anti-Patterns

Avoid:

- Referencing dataframe types in transformation contracts.
- Embedding runtime logic inside transformation declarations.
- Returning undeclared outputs.
- Using global runtime state.

## Key Principle

> A `Transformation` defines the logical interface. An implementation fulfills
that interface for a specific execution backend.

## Next Step

Continue with **CALLBACKS.md** to learn how ETLantic responds to invalid
data, execution failures, retries, and other lifecycle events.
