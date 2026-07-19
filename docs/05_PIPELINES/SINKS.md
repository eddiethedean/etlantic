# Sinks (deprecated)

`Sink[T]` is a deprecated alias of [`Load[T]`](LOADS.md) in ETLantic 0.15.
Prefer:

```python
from etlantic import Load

warehouse = Load[Customer](
    input=normalized.result,
    asset="warehouse.customers",
)
```

`Sink` and `binding=` will be removed in **0.16**. See
[Migration 0.14 → 0.15](../11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md).

Canonical documentation: **[Loads](LOADS.md)**.
