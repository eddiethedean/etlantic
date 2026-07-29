# Compatibility

## Versioning

Medallantic follows Etlantic's pre-1.0 minor line. Pin matching minors:

```text
medallantic 0.32.x  <->  etlantic 0.32.x
```

The package metadata currently requires `etlantic>=0.32.0,<0.33`.

## Engine mapping

| Legacy engine | Profile mapping |
|---|---|
| `spark`, `pyspark` | `Profile.spark_engine="pyspark"` |
| `delta` | PySpark plus `storage.delta.*` / `spark_delta` |
| `sql`, `postgres`, `postgresql` | `Profile.sql_engine="sql"` |
| other/local | `Profile.dataframe_engine="local"` |

Profile selection records intent; it does not install the engine package.

## Write modes

| Legacy mode | ETLantic mode | Notes |
|---|---|---|
| `append` | `APPEND` | Portable intent |
| `overwrite` | `OVERWRITE` | Portable intent |
| `overwrite_partitions` | `OVERWRITE` | Preserves `partition_overwrite=true` metadata |
| `merge` | `MERGE` | Requires capable storage/backend |
| `upsert` | `UPSERT` | Requires capable storage/backend |
| `no_write`, `skip`, `none` | `NO_WRITE` | No load node is created |
| omitted | `OVERWRITE` | Current adapter default |

Unsupported values raise an error rather than degrading to another mode.

## Delta operations

The adapter recognizes:

- `merge`
- `optimize`
- `vacuum`
- `history`
- `time_travel`

Each currently requires the matching `storage.delta.*` extra (merge also
accepts legacy `spark_delta` / `spark_merge` / `write.merge`). Unknown
operations are errors. Missing capabilities are errors under strict adaptation
and warnings only in explicit plan-only mode. Schema evolution is also
recognized as `storage.delta.schema_evolution`.

## Current parity level

| Area | Status |
|---|---|
| IR parsing and graph mapping | Available |
| Dependency and cycle validation | Available |
| Profile and quality-threshold mapping | Available |
| Portable rule DSL → `etlantic.quality/1` gates | Available (Polars/Pandas/local live; SQL/PySpark fail-closed) |
| Write/retry/run-selection mapping | Available |
| Plan enrichment | Available |
| Legacy report normalization/redaction | Available |
| SparkForge callable execution | Available (0.32; local/polars/pandas/pyspark) |
| Native PySpark Column rules | Available (0.32; capability-gated, `MDL130` off Spark) |
| Moltres-only rules | Planned (0.33) |
| Native Medallantic builder | Available |
| Live `PipelineBuilder` bridge | Available (0.32) |
| Live PySpark differential parity | Available (0.32 Sparkless default; live Delta optional) |
| Live SQLAlchemy/Moltres differential parity | Planned (0.33) |
| Delta maintenance execution | Available via `etlantic-pyspark` when `delta-spark` present |

See the [roadmap](../ROADMAP.md) for phase exit criteria. A roadmap item is not
a compatibility claim until its conformance and differential tests pass.

