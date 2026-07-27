# Public Surface Inventory (0.24)

Machine-readable companion: [`surface-inventory.json`](https://github.com/eddiethedean/etlantic/blob/main/src/etlantic/schemas/surface-inventory.json)
(also packaged under `etlantic.schemas`).

Stability classes:

| Class | Meaning |
|---|---|
| `stable` | Supported within the documented 0.24 reference envelope |
| `provisional` | Public but may change with migration notes before 1.0 |
| `experimental` | May change or be removed without 1.0 obligation |
| `compatibility` | Pre-1.0 root alias (warn once); prefer the owning namespace |
| `private` | Underscore modules / internal helpers — do not import |

## Recommended import style

```python
import etlantic as etl
```

## SDK (root curated)

Unchanged curated root from 0.23. Prefer `etl.authoring` for programmatic
definition APIs.

## Lazy namespaces

| Attribute | Module | Class |
|---|---|---|
| `etl.authoring` | `etlantic.authoring` | stable |
| `etl.service` | `etlantic.service` | stable |
| `etl.transform` | `etlantic.transform` | stable |
| `etl.dataframe` | `etlantic.dataframe` | stable |
| `etl.sql` | `etlantic.sql` | stable |
| `etl.spark` | `etlantic.spark` | stable |
| `etl.orchestration` | `etlantic.orchestration` | stable |
| `etl.viz` | `etlantic.viz` | stable |
| `etl.secrets` | `etlantic.secrets` | stable |
| `etl.testing` | `etlantic.testing` | stable |

## Wire schemas (wire-stable in 0.24)

| Schema ID | Class |
|---|---|
| `etlantic.pipeline/1` | stable (authoring) |
| `etlantic.plan/1` | stable (resolved execution IR — **not** authoring round-trip) |
| `etlantic.run_report/1` | stable |
| `etlantic.authoring-catalog/1` | stable |
| `etlantic.interchange/1` | stable |
| `etlantic.capabilities/1` | stable |
| Profile JSON | stable |
| Reliability / policy / extension bags | stable (secret-free; unknown fields fail closed where enforced) |

## Optional packages

| Package | Role |
|---|---|
| `etlantic-fastapi` | Thin 0.24 reference adapter (not 1.1 control plane) |
