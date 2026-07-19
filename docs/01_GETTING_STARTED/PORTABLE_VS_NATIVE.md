# Portable vs Native Implementations

> **Status: Available in ETLantic 0.14.0.**

## When to use `@Transformation.portable`

Use portable authoring when you want one closed relational definition that
emits `dtcs.transform-plan/2` for compilers:

```python
from etlantic.transform import functions as F

@Normalize.portable
def normalize(rows):
    return rows.filter(F.col("age") >= 18)
```

Inspect with `Normalize.to_transform_plan()` / `portable_fingerprint()`.
In **0.12**, Polars can execute kernel-shaped plans without a native
`@implementation("polars")` when `portable_transform_policy` is `prefer` or
`require`.

## When to use `@Transformation.implementation`

Use native implementations for engines without a shipped compiler, for
behavior outside the portable claim set, or when
`portable_transform_policy="native"`:

```python
@Normalize.implementation("local")
def normalize_local(rows):
    ...

@Normalize.implementation("pandas")
def normalize_pandas(rows):
    ...
```

Common pattern: keep portable authoring for the plan artifact, use
Polars/PySpark/Pandas portable relational execution when the claim set fits,
and keep native callables for SQL (0.15+) or profiles outside advertised
claims.

## Related

- [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
- [`examples/portable_polars_kernel.py`](https://github.com/eddiethedean/etlantic/blob/main/examples/portable_polars_kernel.py)
- [Migration 0.11 → 0.12](../11_DEVELOPMENT/MIGRATION_0_11_TO_0_12.md)
