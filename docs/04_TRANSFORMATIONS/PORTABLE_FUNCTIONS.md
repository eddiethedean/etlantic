# Portable Transformation Function Reference

!!! success "Available in ETLantic 0.11 (authoring)"
    Facade methods lower to published DTCS identifiers and emit profile
    requirements on the portable plan. **Authoring is not the same as
    executable support:** advertise a method as runnable only when a compiler
    claims the matching profile (see the
    [portable compiler matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md)).
    Kernel + `portable-relational/1` execute on Polars / PySpark / Pandas in
    0.13–0.14; safe SQL lowering for that claim set is the **0.15** exit gate;
    advanced families graduate under the 0.15 continuation backlog.

Portable functions are imported through one stable namespace:

```python
from etlantic.transform import functions as F
```

Each public function maps to a DTCS Function or Operator registry identifier.
ETLantic does not assign independent semantics. Published DTCS 3.0 / toolkit
`dtcs` 0.14.0 is the current normative *content* floor where specs say so;
ETLantic's install pin remains `dtcs>=0.13,<1` (do not treat the pin as a
content version claim).

## Construction and conditional expressions

| ETLantic facade | DTCS 2.0 representation | Notes |
|---|---|---|
| `F.col(name)` | structured `fieldRef` | Qualified or relation-scoped reference |
| `F.lit(value)` | structured `literal` | Bounded boolean, string, integer, or decimal kernel literal |
| `F.when(...).otherwise(...)` | `dtcs:case_when` | Ordered first-match conditional |
| `F.coalesce(*values)` | `dtcs:coalesce` | First present non-null/non-missing value; skips invalid |
| `F.if_null(value, fallback)` | `dtcs:if_null` | Replaces null or missing |
| `F.null_if(left, right)` | `dtcs:null_if` | Returns null when equal |
| `F.try_cast(value, type)` | `dtcs:try_cast` | Tolerant conversion with defined invalid behavior |
| `F.is_invalid(value)` | `dtcs:is_invalid` | Tests the invalid value state |

## Strings

| ETLantic facade | DTCS identifier | Registered null behavior |
|---|---|---|
| `F.lower` | `dtcs:lower` | propagate |
| `F.upper` | `dtcs:upper` | propagate |
| `F.concat` | `dtcs:concat` | propagate; at least two arguments |
| `F.concat_ws` | `dtcs:concat_ws` | defined |
| `F.substring` | `dtcs:substr` | propagate |
| `F.replace` | `dtcs:replace` | propagate |
| `F.length` | `dtcs:length` | propagate |
| `Column.contains` / `F.contains` | `dtcs:contains` | propagate |
| `Column.startswith` | `dtcs:starts_with` | propagate |
| `Column.endswith` | `dtcs:ends_with` | propagate |

DTCS 2.0 publishes `trim`, `lowercase`, `uppercase`, `capitalize`, and
`normalize_whitespace` as field-targeted Semantic Actions. Only `lower` and
`upper` are also general expression Functions in the 2.0 kernel.

DTCS 3.0 profile `dtcs:profile/portable-string-advanced/1` publishes expression
Functions including `dtcs:trim`, `dtcs:ltrim`, `dtcs:rtrim`,
`dtcs:normalize_whitespace`, `dtcs:split`, regex helpers, and related string
ops. The planned ETLantic facade may expose `F.trim` / `F.split` / regex
helpers only when the profile is selected and the compiler claims it.

## Numeric and conversion functions

| ETLantic facade | DTCS identifier |
|---|---|
| `F.abs` | `dtcs:abs` |
| `F.round` | `dtcs:round` |
| `F.floor` | `dtcs:floor` |
| `F.ceil` | `dtcs:ceil` |
| `F.pow` / `F.power` | `dtcs:power` |
| `F.sqrt` | `dtcs:sqrt` |
| `F.least` | `dtcs:least` |
| `F.greatest` | `dtcs:greatest` |
| `F.min` | `dtcs:min` variadic scalar minimum |
| `F.max` | `dtcs:max` variadic scalar maximum |
| `F.to_string` | `dtcs:to_string` |
| `F.to_integer` | `dtcs:to_integer` |
| `F.to_decimal` | `dtcs:to_decimal` |

`Column.cast(type)` must resolve to a published, type-correct DTCS conversion;
unsupported general casts fail definition validation. It must never become a
backend-native cast with different overflow or invalid-value behavior.

## Null and value-state predicates

| ETLantic facade | DTCS identifier |
|---|---|
| `F.is_null` / `Column.isNull()` | `dtcs:is_null` |
| `Column.isNotNull()` | `dtcs:not(dtcs:is_null(...))` |
| `F.is_missing` / `Column.isMissing()` | `dtcs:is_missing` |
| `F.is_invalid` / `Column.isInvalid()` | `dtcs:is_invalid` |

Facade functions whose semantics are absent from the published DTCS registry
remain excluded or proposals; familiar PySpark spelling is never sufficient.

## Support levels

| Level | Meaning |
|---|---|
| `dtcs:profile/portable-relational-kernel/1` | Required projection, filtering, field shaping, and scalar expressions |
| `dtcs:profile/portable-relational/1` | Full joins, unions, aggregation, sorting, deduplication, and limits |
| `dtcs:profile/portable-window/1` | Experimental window functions and frames |
| `dtcs:profile/portable-complex-types/1` | Experimental list, map, object, tuple, and access semantics |
| Excluded | Incompatible with portable declarative execution |

## Operators and Column methods

| Surface | IR operation |
|---|---|
| `a == b`, `a != b` | equality / inequality |
| `a < b`, `a <= b`, `a > b`, `a >= b` | ordered comparison |
| `a + b`, `a - b`, `a * b`, `a / b`, `a % b` | arithmetic |
| `a & b`, `a \| b`, `~a` | three-valued boolean operations |
| `column.alias(name)` | named projection |
| `column.cast(type)` | published DTCS conversion or `try_cast` semantics |
| `column.isNull()` | null predicate |
| `column.isNotNull()` | non-null predicate |
| `column.isin(*values)` | finite membership test |
| `column.between(lower, upper)` | inclusive range predicate |
| `column.eqNullSafe(other)` | `dtcs:null_safe_eq` |
| `column[index]` | `dtcs:index` |
| `column.getField(name)` | `dtcs:field` |
| `F.element_at(column, key)` | `dtcs:element_at` |
| `column.asc()`, `column.desc()` | sort expression |
| `column.asc_nulls_first()` | explicit null ordering |
| `column.desc_nulls_last()` | explicit null ordering |

Python `and`, `or`, `not`, and implicit boolean conversion are rejected because
they cannot build symbolic expressions.

The exact published operator mappings are:

| Family | DTCS identifiers |
|---|---|
| Comparison | `eq`, `not_eq`, `lt`, `lte`, `gt`, `gte`, `null_safe_eq` |
| Boolean | `and`, `or`, `not` |
| Arithmetic | `add`, `subtract`, `multiply`, `divide`, `modulo`, `negate` |
| Membership | `in`, `between` |
| Access | `field`, `index`, `element_at` |

## Aggregate functions

The full relational profile publishes:

| ETLantic facade | DTCS identifier |
|---|---|
| `F.count_all()` / `F.count("*")` | `dtcs:count_all` |
| `F.count(column)` | `dtcs:count` |
| `F.count_distinct(column)` | `dtcs:count_distinct` |
| `F.sum(column)` | `dtcs:sum` |
| `F.avg(column)` / `F.average(column)` | `dtcs:average` |
| aggregate `F.min(column)` | aggregate context for `dtcs:min` |
| aggregate `F.max(column)` | aggregate context for `dtcs:max` |

Aggregate functions carry aggregate context in the IR. They cannot be used as
ordinary row expressions unless placed in a window.

`stddev` and `variance` are not in the DTCS 2.0 standard catalog and remain
excluded from the conforming facade.

## Date and time functions

| ETLantic facade | DTCS identifier / lowering |
|---|---|
| `F.current_date()` | `dtcs:current_date` |
| `F.current_timestamp()` | `dtcs:current_timestamp` |
| `F.date_add(value, amount, unit="day")` | `dtcs:date_add` |
| `F.date_sub(value, amount, unit="day")` | `dtcs:date_add` with a negative amount |
| `F.datediff(end, start, unit="day")` | `dtcs:date_diff` |
| `F.date_trunc(unit, value)` | `dtcs:date_trunc` |
| `F.year/month/dayofmonth/hour(value)` | `dtcs:extract` with a fixed part |
| `F.at_timezone(value, offset)` | `dtcs:at_timezone` |

The portable profile uses fixed-offset timezone semantics. IANA/DST calendar
behavior is outside DTCS 2.0 portability. Clock functions may be deterministic
only when the execution context supplies a fixed reference clock.

## Window API

DTCS 2.0 publishes the following experimental window facade:

```python
from etlantic.transform import Window

window = (
    Window.partitionBy("customer_id")
    .orderBy(F.col("created_at").desc())
)

orders.withColumn("rank", F.row_number().over(window))
```

Published functions include `row_number`, `rank`, `dense_rank`, `lag`, `lead`,
`first_value`, and `last_value`. Frame boundaries must use explicit portable
row or range specifications. Framed `sum`, `count`, `average`, `min`, and `max`
reuse the aggregate functions.

## Complex types

DTCS 2.0's experimental complex-types profile covers list/array, map, and
object/struct logical types plus `field`, `index`, and `element_at` access.
`array`, `struct`, `create_map`, `explode`, `size`, `array_contains`,
`map_keys`, `map_values`, and higher-order collection lambdas are not in the
published standard catalog and remain excluded until standardized.

## DTCS 3.0 advanced families (published; ETLantic not yet claiming)

DTCS 3.0 publishes independently claimable profiles that cover many formerly
excluded PySpark-like surfaces. Facade methods may exist for IR authoring;
ETLantic must not advertise them as **executable** until the corresponding
compiler claims the profile and conformance fixtures pass (0.15 continuation,
not the 0.15 SQL exit gate):

| Planned facade examples | DTCS 3.0 profile |
|---|---|
| `F.trim`, `F.split`, regex extract/replace | `portable-string-advanced/1` |
| strict `F.cast` / parse helpers beyond `try_cast` | `portable-conversion/1` |
| `F.stddev`, `F.variance`, correlation | `portable-statistics/1` |
| array/map/struct constructors, lambdas, explode | `portable-complex-values/1` + `portable-reshape/1` |
| `intersect` / `except`, sample, pivot | `portable-relational-extended/1` |
| IANA timezone helpers | `portable-temporal-iana/1` |
| `F.rand`, UUID | `portable-nondeterministic/1` |
| `ntile`, `percent_rank`, … | `portable-window/2` |

`F.expr(...)` SQL text remains permanently excluded from portable definitions.
Native `@Transformation.implementation(...)` remains the escape hatch.

See the
[DTCS 3.0 Rich Portable Analytics Publication Record](../11_DEVELOPMENT/DTCS_3_0_SPEC_PROPOSAL.md).

## Determinism

Every function descriptor declares whether it is:

- deterministic
- stable within one run, such as `current_timestamp()`
- nondeterministic, when a future DTCS entry explicitly declares that class

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

1. A stable DTCS registry identifier and entry version.
2. Argument and return-type rules.
3. Null, error, determinism, and ordering semantics.
4. Capability vocabulary.
5. Assignment to the kernel, relational, window, or complex-types profile.
6. At least two independent compiler implementations before an experimental
   semantic family can become standard.
7. Shared DTCS conformance fixtures, including edge cases.
8. Documentation and `plan explain` rendering.
