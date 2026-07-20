# Portable vs Native Implementations

> **Status: Available in ETLantic 0.21.0.**

## Decision guide

| Situation | Prefer |
|---|---|
| One closed relational definition for Polars / PySpark / Pandas / SQL within kernel + `portable-relational/1` | `@Transformation.portable` |
| Local Python / memory demos | `@Transformation.implementation("local")` |
| Explicit SQL dialect control or unclaimed SQL ops | Native `@implementation("sql")` |
| Ops outside advertised claims (UDFs, unclaimed profiles, Pandas index semantics) | Native `@implementation(...)` |
| Force native only | `Profile(portable_transform_policy="native")` |
| Fail if portable cannot compile | `Profile(portable_transform_policy="require")` |

The transformation **contract** and pipeline wiring stay the same across
engines. Native implementation **bodies** may differ by engine.

## When to use `@Transformation.portable`

```python
from etlantic.transform import functions as F

@Normalize.portable
def normalize(rows):
    return rows.filter(F.col("age") >= 18)
```

Inspect with `Normalize.to_transform_plan()` / `portable_fingerprint()`.
With `portable_transform_policy` of `prefer` or `require`, Polars, PySpark,
Pandas, and SQL can execute fitting plans without a matching native
implementation (Pandas is eager-only and index-neutral; SQL uses typed IR).

## When to use `@Transformation.implementation`

```python
@Normalize.implementation("local")
def normalize_local(rows):
    ...

@Normalize.implementation("sql")
def normalize_sql(rows):
    ...
```

Safe portable SQL lowering for kernel + `portable-relational/1` shipped in
**0.15**. Keep native `@implementation("sql")` when you need dialect-specific
control or profiles outside the advertised claim set; `prefer` may select an
explicit native SQL implementation only — never silent portable emulation.
Advanced families shipped on Polars and PySpark in 0.17; Pandas and SQL remain
baseline-only (see the
[portable compiler matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md)).

## Related

- [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
- [Portable compiler matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md)
- [`examples/portable_polars_kernel.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/portable_polars_kernel.py)
- [Migration 0.14 → 0.15](../11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md)
