# Portable Transformation Function Reference

!!! warning "Proposed 0.11+ API—not available in ETLantic 0.10"
    This reference inventories the planned PySpark-inspired portable API. A
    function becomes supported only when its semantics, IR node, capability,
    and conformance fixtures are accepted.

Portable functions are imported through one stable namespace:

```python
from etlantic.transform import functions as F
```

## Support levels

| Level | Meaning |
|---|---|
| Kernel | Required for the first portable IR release |
| Relational | Added with joins and aggregation |
| Advanced | Added after multi-engine conformance |
| Excluded | Incompatible with portable declarative execution |

## Kernel functions

| Function | Purpose | Required semantics |
|---|---|---|
| `F.col(name)` | Reference a column | qualified and unqualified resolution |
| `F.lit(value)` | Safe bounded literal | normalized portable type |
| `F.when(condition, value)` | Begin conditional expression | ordered first-match evaluation |
| `F.coalesce(*values)` | First non-null value | SQL-style null semantics |
| `F.concat(*values)` | Concatenate strings or collections | explicit type rules |
| `F.concat_ws(separator, *values)` | Join string values | normative null handling |
| `F.lower(value)` | Lowercase string | Unicode behavior declared |
| `F.upper(value)` | Uppercase string | Unicode behavior declared |
| `F.trim(value)` | Trim whitespace | portable whitespace definition |
| `F.length(value)` | String or collection length | code-point semantics for strings |
| `F.abs(value)` | Absolute numeric value | overflow behavior declared |
| `F.round(value, scale=0)` | Round numeric value | half-even by default |

`F.when()` returns a conditional column supporting `.when()` and
`.otherwise()`.

## Operators and Column methods

| Surface | IR operation |
|---|---|
| `a == b`, `a != b` | equality / inequality |
| `a < b`, `a <= b`, `a > b`, `a >= b` | ordered comparison |
| `a + b`, `a - b`, `a * b`, `a / b`, `a % b` | arithmetic |
| `a & b`, `a \| b`, `~a` | three-valued boolean operations |
| `column.alias(name)` | named projection |
| `column.cast(type)` | explicit portable cast |
| `column.isNull()` | null predicate |
| `column.isNotNull()` | non-null predicate |
| `column.isin(*values)` | finite membership test |
| `column.between(lower, upper)` | inclusive range predicate |
| `column.asc()`, `column.desc()` | sort expression |
| `column.asc_nulls_first()` | explicit null ordering |
| `column.desc_nulls_last()` | explicit null ordering |

Python `and`, `or`, `not`, and implicit boolean conversion are rejected because
they cannot build symbolic expressions.

## Relational functions

The relational milestone adds:

| Family | Functions |
|---|---|
| Aggregates | `count`, `count_distinct`, `sum`, `avg`, `min`, `max` |
| Statistical | `stddev`, `variance` after numeric semantics are accepted |
| Strings | `substring`, `split`, `regexp_extract`, `regexp_replace` |
| Numeric | `floor`, `ceil`, `sqrt`, `pow`, `greatest`, `least` |
| Dates | `to_date`, `to_timestamp`, `date_add`, `date_sub`, `datediff` |
| Date parts | `year`, `month`, `dayofmonth`, `hour`, `date_trunc` |

Aggregate functions carry aggregate context in the IR. They cannot be used as
ordinary row expressions unless placed in a window.

## Window API

The advanced milestone proposes:

```python
from etlantic.transform import Window

window = (
    Window
    .partitionBy("customer_id")
    .orderBy(F.col("created_at").desc())
)

orders.withColumn("rank", F.row_number().over(window))
```

Planned functions include `row_number`, `rank`, `dense_rank`, `lag`, `lead`,
`first_value`, and `last_value`. Frame boundaries must use explicit portable
row or range specifications.

## Complex types

Arrays, maps, and structs are deferred until type and null behavior are proven
across Polars, Pandas/Arrow, SQL dialects, and Spark. Candidate functions
include `array`, `struct`, `create_map`, `explode`, `size`, `array_contains`,
`element_at`, `map_keys`, and `map_values`.

## Determinism

Every function descriptor declares whether it is:

- deterministic
- stable within one run, such as `current_timestamp()`
- nondeterministic, such as a random function

Nondeterministic operations require an explicit capability and affect caching,
retries, and idempotency. Plugins must not strengthen or weaken determinism
silently.

## Excluded APIs

These PySpark-like surfaces are intentionally excluded from portable
definitions:

- `frame.collect()`, `show()`, `take()`, `toPandas()`, and other actions
- `frame.write` and direct persistence
- `frame.rdd`
- Python, Pandas, or backend UDF registration
- raw SQL expression strings such as `F.expr(...)`
- arbitrary Python lambdas embedded in expression nodes
- runtime schema or data inspection

Native `@Transformation.implementation(...)` functions remain the escape hatch
for engine-specific behavior.

## Adding a function

A portable function is complete only when it has:

1. A stable function identifier and IR version.
2. Argument and return-type rules.
3. Null, error, determinism, and ordering semantics.
4. Capability vocabulary.
5. At least two independent compiler implementations.
6. Shared conformance fixtures, including edge cases.
7. Documentation and `plan explain` rendering.
