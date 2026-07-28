# Compatibility

## Versioning

Medallantic follows Etlantic's pre-1.0 minor line. Pin matching minors:

```text
medallantic 0.27.x  <->  etlantic 0.27.x
```

The package metadata currently requires `etlantic>=0.27.0,<0.28`.

## Engine mapping

| Legacy engine | Profile mapping |
|---|---|
| `spark`, `pyspark` | `Profile.spark_engine="pyspark"` |
| `delta` | PySpark plus `spark_delta` capability |
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

Each currently requires the `spark_delta` capability. Unknown operations are
errors. Missing capabilities are errors under strict adaptation and warnings
only in explicit plan-only mode.

## Current parity level

| Area | Status |
|---|---|
| IR parsing and graph mapping | Available |
| Dependency and cycle validation | Available |
| Profile and quality-threshold mapping | Available |
| Write/retry/run-selection mapping | Available |
| Plan enrichment | Available |
| Legacy report normalization/redaction | Available |
| SparkForge callable execution | Not available |
| Legacy rule execution | Not available |
| Native Medallantic builder | Planned |
| Live PySpark differential parity | Planned |
| Live SQLAlchemy/Moltres differential parity | Planned |
| Delta maintenance execution | Plugin-dependent and planned |

See the [roadmap](../ROADMAP.md) for phase exit criteria. A roadmap item is not
a compatibility claim until its conformance and differential tests pass.

