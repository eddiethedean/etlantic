# Compatibility

## Version policy

Pin matching minor versions:

```text
medallantic 0.34.x  ↔  etlantic 0.34.x
```

The current package requires `etlantic>=0.34.0,<0.35`. Engine plugins are
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

| Area | Status in 0.34 |
|---|---|
| Native class/builder authoring | Available |
| Deterministic ETLantic lowering | Available |
| Portable quality gates | Available |
| Importable `transform_ref` | Available |
| Lifecycle defaults and write intents | Available |
| SparkForge IR migration | Available |
| Report normalization and accept-rate enforcement | Available |
| Native PySpark Column rules | Available; capability-gated (`MDL130` off Spark) |
| Moltres-only rules | Available; capability-gated (`MDL132`) |
| Live SparkForge `PipelineBuilder` bridge | Available |
| Live SQL `SqlPipelineBuilder` bridge | Available |
| SQLite/PostgreSQL differential parity | Available; Tier A |
| Delta maintenance operations | Available through `etlantic-pyspark` when its declared capabilities are present |
| `explain_medallion_plan` + lifecycle views (M6) | Available |
| Medallion profile templates (`medallion_*_profile`) | Available |

A roadmap item is not a compatibility claim until its conformance and
differential gates pass.
