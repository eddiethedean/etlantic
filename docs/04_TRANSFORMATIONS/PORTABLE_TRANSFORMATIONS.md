# Portable Transformations

!!! success "Available since ETLantic 0.17 (docs target 0.18.0)"
    `@Transformation.portable` and `etlantic.transform` emit validated
    `dtcs.transform-plan/2` IR. Polars, PySpark, and Pandas execute kernel +
    `portable-relational/1` plans in 0.12–0.14; safe SQL lowering for that
    claim set shipped in **0.15**. Advanced string, conversion, statistics,
    window `/1`, complex, and reshape families shipped on Polars and PySpark
    in **0.17**.

A portable transformation expresses dataframe logic once and lets ETLantic
plugins compile it for Polars, Pandas, SQL, PySpark, and future engines.

The syntax deliberately resembles PySpark's DataFrame and Column APIs:

```python
from etlantic import Data, Input, Output, Parameter, Transformation
from etlantic.transform import functions as F


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]


@NormalizeCustomers.portable
def normalize(customers, minimum_age):
    return (
        customers
        .filter(F.col("age") >= minimum_age)
        .select(
            F.col("customer_id"),
            F.concat_ws(
                " ",
                F.col("first_name"),
                F.col("last_name"),
            ).alias("full_name"),
        )
    )
```

The decorated function runs only with symbolic inputs while ETLantic builds a
canonical DTCS Transformation Plan through public `dtcs` package models. It
does not receive data, contact a backend, or execute a pipeline.

## Design goals

- Provide a rich, familiar DataFrame and Column authoring model.
- Preserve one precise meaning across execution engines.
- Validate columns, types, outputs, and plugin support before execution.
- Preserve lazy execution and backend optimization where possible.
- Keep native implementations as explicit optimization and escape hatches.
- Keep the core free of Polars, Pandas, PySpark, database, and driver imports.

## Non-goals

Portable transformations do not:

- trace arbitrary Python or inspect Python bytecode
- translate native Polars, Pandas, or PySpark expressions
- permit actions such as `collect()`, `show()`, `write`, or `toPandas()`
- silently introduce Python UDFs
- accept arbitrary SQL expression strings
- guarantee support for every PySpark API

The syntax is PySpark-inspired. ETLantic owns the portable semantics.

## Symbolic values

Portable definition arguments are symbolic values derived from declared ports:

| Declaration | Symbolic definition value |
|---|---|
| `Input[T]` | `DataFrame` expression with contract `T` |
| `Parameter[T]` | typed `Column` parameter reference |
| `Output[T]` | required returned dataframe expression |

Internally these are `FrameExpr` and `ColumnExpr` values. Users normally do not
construct them directly.

## DataFrame operations

The ETLantic facade maps DataFrame methods to published DTCS 2.0 Semantic
Actions. Method spelling is PySpark-inspired; behavior is DTCS-defined.

### Kernel profile

`dtcs:profile/portable-relational-kernel/1` covers projection, filtering, field
shaping, scalar expressions, and canonical plan serialization:

| ETLantic / PySpark-like surface | DTCS 2.0 mapping | Portable behavior |
|---|---|---|
| `frame.select(*columns)` | `dtcs:project` rich `fields` | Ordered names and `{expression, name}` projections; unselected fields are dropped |
| `frame.filter(predicate)` / `.where(...)` | `dtcs:filter` | Retain `true`; discard `false`, `null`, and `missing`; invalid fails or routes explicitly |
| `frame.withColumn(name, expression)` | `dtcs:with_fields` | Ordered assignment that adds or replaces a field |
| `frame.withColumns(**expressions)` | One `dtcs:with_fields` | ETLantic convenience for multiple ordered assignments |
| `frame.drop(*names)` | `dtcs:drop_fields` | `missingPolicy="error"` by default; explicit ignore mode may be exposed |
| `frame.withColumnRenamed(old, new)` | `dtcs:rename_fields` | Rename without changing value or logical type |
| `frame.alias(name)` | Relation/reference metadata | Scopes later field references; it is not a dataset mutation |

### Full relational profile

`dtcs:profile/portable-relational/1` extends the kernel:

| ETLantic / PySpark-like surface | DTCS 2.0 mapping | Portable behavior |
|---|---|---|
| `frame.distinct()` | `dtcs:distinct` | Full-row distinct (unordered) |
| `frame.dropDuplicates(keys)` | `dtcs:deduplicate` | Key retention; nondeterministic without ordering |
| `frame.orderBy(*keys)` / `.sort(...)` | `dtcs:sort` | Each key carries expression, direction, and null placement |
| `frame.limit(n)` | `dtcs:limit` | Nondeterministic without a preceding semantic sort |
| `frame.join(other, on=..., how=...)` | `dtcs:join` | `inner`, `left`, `right`, `full`, `semi`, `anti`, and `cross` |
| `frame.groupBy(*keys).agg(...)` | `dtcs:aggregate` / `dtcs:group` | Expression lists, optional filter, explicit grouping semantics |
| `frame.union(other)` | `dtcs:union` positional mode | Positional append with declared duplicate policy |
| `frame.unionByName(other, allowMissingColumns=...)` | `dtcs:union` by-name mode | Explicit missing-column and duplicate policies |

Physical PySpark operations such as `repartition()` and `coalesce()` are not
portable DataFrame transformations. DTCS `dtcs:partition` expresses semantic
partitioning by a field; ETLantic will not map physical partition-count hints
to it.

## Join semantics

```python
customers.join(
    orders,
    on="customer_id",
    how="left",
    null_safe=False,
    collision_policy="fail",
)
```

Ordinary equality never matches two null keys. Authors must request
`null_safe=True` (DTCS `dtcs:null_safe_eq`) when nulls should match. Column-name
collisions must use an explicit published collision policy; 0.13–0.14 compilers claim
`fail` only (suffix/coalesce/qualify remain deferred). Compilers may not
silently apply backend suffix conventions.

Cross joins require `how="cross"` and must not infer a predicate. Semi and anti
joins return the left interface only.

## Column operations

Columns compose through operators and methods:

```python
(F.col("age") >= minimum_age) & F.col("email").isNotNull()
F.col("total") * F.col("quantity")
F.lower(F.col("email")).alias("email")
```

`F.try_cast` and other conversion helpers are outside the baseline kernel
claim. The conversion profile shipped on Polars and PySpark in 0.17; use a
native implementation on Pandas, SQL, or an unclaimed backend.

DTCS `trim` is a field-targeted Semantic Action, not a general DTCS 2.0
expression Function, so the strict facade does not pretend that
`F.trim(column)` is portable.

`Column` truthiness is prohibited. This is invalid:

```python
if F.col("active"):
    ...
```

Authors use `&`, `|`, `~`, `F.when()`, and `DataFrame.filter()` instead.

DTCS 2.0 structured nodes map directly to the facade:

| DTCS node | ETLantic surface |
|---|---|
| `literal` | `F.lit(value)` |
| `fieldRef` | `F.col(name)` |
| `unary` | `~column`, unary `-column`, and unary method forms |
| `binary` | comparisons, boolean operators, arithmetic, membership, and access |
| `call` | `F.<function>(...)` |

Opaque Python objects, `repr()` serialization, arbitrary lambdas, and
host-language AST nodes are rejected.

## Conditions

```python
@ClassifyCustomers.portable
def classify(customers):
    return customers.withColumn(
        "segment",
        F.when(F.col("lifetime_value") >= 10_000, F.lit("platinum"))
        .when(F.col("lifetime_value") >= 1_000, F.lit("gold"))
        .otherwise(F.lit("standard")),
    )
```

## Multiple inputs and joins

```python
@BuildCustomerOrders.portable
def build(customers, orders):
    customers = customers.alias("c")
    orders = orders.alias("o")
    return (
        customers
        .join(
            orders,
            F.col("c.customer_id") == F.col("o.customer_id"),
            "left",
        )
        .select(
            F.col("c.customer_id").alias("customer_id"),
            F.col("c.full_name"),
            F.col("o.order_id"),
            F.col("o.total"),
        )
    )
```

Relation identities, rather than strings alone, disambiguate bound columns in
the intermediate representation.

## Aggregation

```python
@SummarizeOrders.portable
def summarize(orders):
    return (
        orders
        .groupBy("customer_id")
        .agg(
            F.count("*").alias("order_count"),
            F.sum("total").alias("lifetime_value"),
            F.max("created_at").alias("latest_order_at"),
        )
    )
```

`F.count()` is an aggregate expression. A dataframe action such as
`frame.count()` is not portable and is rejected during definition building.

DTCS distinguishes `count_all()` from `count(column)`. Missing grouping keys
are distinct from null keys. Aggregate filters, empty-input behavior, and
result logical types must be preserved by each compiler.

## Sorting, limiting, and deduplication

Ordering exists only after `orderBy()` / `sort()`. Source order, insertion
order, and backend index order have no portable meaning. Every sort key records
ascending/descending and `nulls="first" | "last"`.

`limit()` without a prior sort and `dropDuplicates()` without a deterministic
retention order are valid only when the definition accepts nondeterminism. The
planner must expose that property; compilers may not choose a stable-looking
backend order and claim deterministic semantics.

## Windows

ETLantic 0.17 ships `dtcs:profile/portable-window/1` on Polars and PySpark:

```python
from etlantic.transform import Window

w = (
    Window.partitionBy("customer_id")
    .orderBy(F.col("created_at").desc_nulls_last())
)

orders.withColumn("row_number", F.row_number().over(w))
```

Explicit frames remain unsupported in 0.17 and fail closed. Published
functions include
`row_number`, `rank`, `dense_rank`, `lag`, `lead`, `first_value`,
and `last_value`.

## Complex types

ETLantic 0.17 ships `dtcs:profile/portable-complex-types/1` and
`portable-complex-values/1` on Polars and PySpark for lists/arrays, maps, and
objects/structs. The facade maps indexed and keyed access through
`dtcs:index`, `dtcs:field`, and `dtcs:element_at`; out-of-bounds
`element_at` returns null. Constructors and `size` are included; `explode`
ships under `portable-reshape/1`. Higher-order lambdas and map/array mutation
remain post-0.17.

## Value states

Portable expressions preserve three distinct states:

| State | Meaning |
|---|---|
| `null` | Present field with a null payload |
| `missing` | Absent value represented by the DTCS missing token |
| `invalid` | Present but invalid value, optionally carrying a reason |

Functions and actions apply their registered behavior to each state. ETLantic
must not normalize missing or invalid to null unless the DTCS entry explicitly
requires it.

## Multiple outputs

Return a mapping keyed by declared output port:

```python
@ValidateOrders.portable
def validate(orders):
    accepted = F.col("order_id").isNotNull() & (F.col("total") >= 0)
    return {
        "valid": orders.filter(accepted),
        "invalid": orders.filter(~accepted),
    }
```

Every declared output must be produced exactly once. Undeclared outputs are an
error.

## Native implementations

Portable and native implementations may coexist:

```python
@NormalizeCustomers.portable
def normalize(customers):
    ...


@NormalizeCustomers.implementation("pyspark")
def optimized_spark(customers):
    ...
```

Profiles choose an implementation policy:

| Policy | Meaning |
|---|---|
| `require` | Require portable compilation; native fallback is forbidden |
| `prefer` | Prefer portable compilation; allow an explicit native fallback (default) |
| `native` | Prefer a registered native implementation |

The selected path is recorded in the plan and run report. Fallback is never
silent. Portable IR is inspectable via `to_transform_plan()` /
`portable_fingerprint()`.

## Planning

Planning performs these checks without reading data:

1. Definition signature matches declared inputs and parameters.
2. Referenced columns exist and expressions are well typed.
3. Returned expressions satisfy declared output contracts.
4. The definition contains only closed portable operations.
5. The selected plugin supports every required operation and semantic mode.
6. The definition and serialized plan are free of secrets and executable
   objects.
7. The plan declares one or more exact DTCS semantic-family profiles: kernel,
   relational, window, or complex types.
8. Every action, function, operator, type, value-state mode, join policy, and
   ordering mode is supported by the selected compiler.

`etlantic plan --explain` should identify the selected compiler, IR version,
required capabilities, materialization boundaries, and native fallbacks.

## Execution

Plugins compile the portable IR to native expressions:

| Portable operation | Polars | Pandas | SQL | PySpark |
|---|---|---|---|---|
| `F.col("age")` | `pl.col("age")` | `df["age"]` | quoted column | `F.col("age")` |
| `.filter(x)` | `.filter(x)` | `.loc[x]` | `WHERE x` | `.filter(x)` |
| `.withColumn()` | `.with_columns()` | assignment/copy | projection or CTE | `.withColumn()` |
| `.groupBy().agg()` | `.group_by().agg()` | `.groupby().agg()` | `GROUP BY` | `.groupBy().agg()` |
| `.join(..., how="anti")` | anti join | merge/filter lowering | `NOT EXISTS`/anti join | `left_anti` |
| `.unionByName(...)` | diagonal/relaxed concat as required | aligned concat | named projection + union | `.unionByName()` |
| window expressions | `.over(...)` | group/rolling lowering when conforming | `OVER (...)` | `Window` expressions |

This table is illustrative, not a capability claim. A compiler supports a row
only after it advertises the matching DTCS profile and passes that profile's
conformance fixtures.

The planner may fuse adjacent portable steps into one backend region while
retaining logical step identities for lineage, validation, and diagnostics.

## DTCS semantic authority

Familiar syntax is not sufficient for portability. DTCS owns the
Transformation Plan, semantic actions, expressions, functions, types, and
capability meaning. The `dtcs` package supplies canonical models; ETLantic
supplies the authoring facade, planning, compiler selection, and runtime
coordination.

Because ETLantic and DTCS share a publisher, new portable requirements can be
standardized and released in DTCS before ETLantic exposes them. Shared
publishing authority shortens the feedback loop but does not remove explicit
versioning and compatibility gates.

The ETLantic integration profile
[Portable Transformation IR specification](../specifications/PORTABLE_TRANSFORM_IR_SPEC.md)
collects requirements for nulls, casts, arithmetic, strings, timestamps, joins,
ordering, and aggregation. DTCS 3.0 / `dtcs` 0.13 supply the normative Portable
Relational and Rich Portable Analytics semantics plus canonical models
(`dtcs.transform-plan/2`, with v1 readable). Remaining ETLantic-specific
requirements govern authoring and compiler integration. A plugin must preserve
published DTCS meaning or reject the operation during planning.

See the [DTCS evolution plan](../11_DEVELOPMENT/DTCS_PORTABLE_EVOLUTION.md) for
the cross-project specification and package release workflow.
Publication records:

- [DTCS 2.0 Portable Relational](../11_DEVELOPMENT/DTCS_PORTABLE_SPEC_PROPOSAL.md)
- [DTCS 3.0 Rich Portable Analytics](../11_DEVELOPMENT/DTCS_3_0_SPEC_PROPOSAL.md)

## Related documents

- [Portable function reference](PORTABLE_FUNCTIONS.md)
- [Portable Transformation IR specification](../specifications/PORTABLE_TRANSFORM_IR_SPEC.md)
- [Portable compiler plugin protocol](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
- [Implementation plan](../11_DEVELOPMENT/PORTABLE_TRANSFORM_PLAN.md)
- [DTCS 3.0 Rich Portable Analytics Publication Record](../11_DEVELOPMENT/DTCS_3_0_SPEC_PROPOSAL.md)
- [Architecture decision](../11_DEVELOPMENT/adr/ADR-013-PORTABLE-TRANSFORMATION-IR.md)
