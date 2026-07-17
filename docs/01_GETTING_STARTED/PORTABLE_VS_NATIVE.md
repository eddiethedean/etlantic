# Portable vs Native Implementations

> **Status: Available in ETLantic 0.11.0.**

## When to use `@Transformation.portable`

Use portable authoring when you want one closed relational definition that
emits `dtcs.transform-plan/2` for future multi-engine compilers:

```python
from etlantic.transform import functions as F

@Normalize.portable
def normalize(rows):
    return rows.filter(F.col("age") >= 18)
```

Inspect with `Normalize.to_transform_plan()` / `portable_fingerprint()`.

## When to use `@Transformation.implementation`

Use native implementations for **execution today** and for behavior outside the
portable profile:

```python
@Normalize.implementation("local")
def normalize_local(rows):
    ...

@Normalize.implementation("polars")
def normalize_polars(rows):
    ...
```

In 0.11 you typically register **both**: portable for the plan artifact,
native for runtime. Compilers that execute portable plans arrive in 0.12–0.15.

## Related

- [Portable Transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
- [Implementations](../04_TRANSFORMATIONS/IMPLEMENTATIONS.md)
- [Capabilities](CAPABILITIES.md)
