# Compatibility

## Version policy

Pin matching minor versions:

```text
medallantic 0.32.x  ↔  etlantic 0.32.x
```

The current package requires `etlantic>=0.32.0,<0.33`. Engine plugins are
installed and pinned separately.

## Engine intent

| Requested family | ETLantic profile intent |
|---|---|
| Local | Dataframe engine `local` |
| Polars | Dataframe engine `polars` |
| Pandas | Dataframe engine `pandas` |
| SQL/PostgreSQL | SQL engine `sql` plus dialect/provider |
| Spark/PySpark | Spark engine `pyspark` |
| Delta | PySpark plus declared Delta capabilities |

A profile records intent; it does not install, authorize, or prove a plugin.

## Write modes

| Medallantic input | ETLantic intent | Requirement |
|---|---|---|
| `append` | `APPEND` | append-capable target |
| `overwrite` | `OVERWRITE` | overwrite-capable target |
| `overwrite_partitions` | `OVERWRITE` | partition-overwrite evidence |
| `merge` | `MERGE` | merge-capable target |
| `upsert` | `UPSERT` | upsert-capable target |
| `no_write` | `NO_WRITE` | no load mutation |

Unsupported values are errors.

## Current claims

| Area | Status in 0.32 |
|---|---|
| Native class/builder authoring | Available |
| Deterministic ETLantic lowering | Available |
| Portable quality gates | Available |
| Importable `transform_ref` | Available |
| Lifecycle defaults and write intents | Available |
| SparkForge IR migration | Available |
| Report normalization and accept-rate enforcement | Available |
| Native PySpark Column parity | Not yet a general claim |
| Moltres-only rule parity | Not yet a general claim |
| Delta maintenance operations | Plugin/capability dependent |

A roadmap item is not a compatibility claim until its conformance and
differential gates pass.

