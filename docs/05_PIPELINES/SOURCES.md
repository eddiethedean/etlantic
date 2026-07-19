# Sources (deprecated)

`Source[T]` is a deprecated alias of [`Extract[T]`](EXTRACTS.md) in ETLantic
0.15. Prefer:

```python
from etlantic import Extract

customers = Extract[RawCustomer](asset="customers_csv")
```

`Source` and `binding=` will be removed in **0.16**. See
[Migration 0.14 → 0.15](../11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md).

Canonical documentation: **[Extracts](EXTRACTS.md)**.
