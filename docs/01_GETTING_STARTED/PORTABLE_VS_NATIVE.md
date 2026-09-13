# Portable vs Native Implementations

> **Status: Available in ETLantic 0.52.0 (published Beta).**

## Decision guide

| Situation | Prefer |
|---|---|
| New transformation within the qualified seven-engine baseline | `@Transformation.portable` |
| Local Python / memory demos | `@Transformation.portable` |
| Pipelines intended for adaptive execution | `@Transformation.portable` plus `portable_transform_policy="require"` |
| Explicit SQL dialect control or unclaimed SQL ops | Native `@implementation("sql")` |
| Ops outside advertised claims (UDFs, unclaimed profiles, Pandas index semantics) | Native `@implementation(...)` |
| Force native only | `Profile(portable_transform_policy="native")` |
| Fail if portable cannot compile | `Profile(portable_transform_policy="require")` |

Portable is the default authoring recommendation. The same definition can be
compiled for Local, Polars, Pandas, SQL, PySpark, DataFusion, and DuckDB within
the qualified baseline. Native implementation bodies are tied to their
registered engine and are not eligible for adaptive execution.

## When to use `@Transformation.portable`

```python
from etlantic.transform import functions as F

@Normalize.portable
def normalize(rows):
    return rows.filter(F.col("age") >= 18)
```

Inspect with `Normalize.to_transform_plan()` / `portable_fingerprint()`.
With `portable_transform_policy` of `prefer` or `require`, all seven qualified
engines can execute fitting baseline plans without a matching native
implementation. Use `require` for new projects so an unsupported operation
fails during validation or planning instead of selecting a native body.

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

Choosing a native body is an explicit portability tradeoff. It can still be
the right choice for unsupported semantics or a proven backend-specific
optimization, but the step stays pinned to that engine and cannot participate
in adaptive execution.

## Related

- [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
- [Portable compiler matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md)
- [`examples/portable_polars_kernel.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/portable_polars_kernel.py)
- [Migration 0.14 → 0.15](../11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md)
