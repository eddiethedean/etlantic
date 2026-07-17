# Portable Transformations

!!! warning "Accepted 0.11+ design—not available in ETLantic 0.10"
    This chapter defines the intended authoring experience for portable
    transformations. The API is a design contract for implementation work, not
    a currently importable surface.

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

The 0.11 kernel operation set should include:

```python
frame.select(...)
frame.filter(...)
frame.where(...)
frame.withColumn(name, expression)
frame.drop(...)
frame.withColumnRenamed(old, new)
frame.alias(name)
frame.distinct()
frame.dropDuplicates(...)
frame.orderBy(...)
frame.limit(count)
```

The 0.13 relational expansion adds:

```python
frame.join(other, on=..., how="left")
frame.groupBy(...).agg(...)
frame.unionByName(other, allowMissingColumns=False)
```

Window functions and nested array, map, and struct operations arrive only
after their cross-engine semantics and conformance fixtures are accepted.

## Column operations

Columns compose through operators and methods:

```python
(F.col("age") >= minimum_age) & F.col("email").isNotNull()
F.col("total") * F.col("quantity")
F.col("created_at").cast("timestamp")
F.lower(F.trim(F.col("email"))).alias("email")
```

`Column` truthiness is prohibited. This is invalid:

```python
if F.col("active"):
    ...
```

Authors use `&`, `|`, `~`, `F.when()`, and `DataFrame.filter()` instead.

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
| `prefer` | Prefer portable compilation; allow an explicit native fallback |
| `native` | Prefer a registered native implementation |

The selected path is recorded in the plan and run report. Fallback is never
silent.

## Planning

Planning performs these checks without reading data:

1. Definition signature matches declared inputs and parameters.
2. Referenced columns exist and expressions are well typed.
3. Returned expressions satisfy declared output contracts.
4. The definition contains only closed portable operations.
5. The selected plugin supports every required operation and semantic mode.
6. The definition and serialized plan are free of secrets and executable
   objects.

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

The proposed ETLantic DTCS profile
[Portable Transformation IR specification](../specifications/PORTABLE_TRANSFORM_IR_SPEC.md)
collects requirements for nulls, casts, arithmetic, strings, timestamps, joins,
ordering, and aggregation. Those requirements become authoritative through
DTCS publication. A plugin must preserve the published meaning or reject the
operation during planning.

See the [DTCS evolution plan](../11_DEVELOPMENT/DTCS_PORTABLE_EVOLUTION.md) for
the cross-project specification and package release workflow.
The concrete action, function, expression, capability, and conformance changes
are proposed in the
[DTCS Portable Relational Change Proposal](../11_DEVELOPMENT/DTCS_PORTABLE_SPEC_PROPOSAL.md).

## Related documents

- [Portable function reference](PORTABLE_FUNCTIONS.md)
- [Portable Transformation IR specification](../specifications/PORTABLE_TRANSFORM_IR_SPEC.md)
- [Portable compiler plugin protocol](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md)
- [Implementation plan](../11_DEVELOPMENT/PORTABLE_TRANSFORM_PLAN.md)
- [Architecture decision](../11_DEVELOPMENT/adr/ADR-013-PORTABLE-TRANSFORMATION-IR.md)
