# Storage Plugin

> **Status: Partially available in ETLantic 0.43.0.** Public storage connector
> protocol is `etlantic.storage/1` under `etlantic.connectors` (entry point
> `etlantic.storage_connectors`). Prefer
> [Connector SDK](CONNECTOR_SDK.md) for new work. Built-in memory/CSV/JSON
> paths remain under [Storage today](../06_EXECUTION/STORAGE_TODAY.md).

Storage connectors translate logical extract/load assets into operations for
concrete storage technologies without embedding vendor APIs into pipeline
definitions. Cloud reference packages (`etlantic-s3`, `etlantic-iceberg`,
`etlantic-snowflake`) are **Experimental**.

| Use | Link |
|---|---|
| Connector SDK | [CONNECTOR_SDK](CONNECTOR_SDK.md) |
| Landing zone | [Landing zone](../06_EXECUTION/LANDING_ZONE.md) |
| What works today | [Storage today](../06_EXECUTION/STORAGE_TODAY.md) |
| Extract / Load assets | [Extracts](../05_PIPELINES/EXTRACTS.md), [Loads](../05_PIPELINES/LOADS.md) |
| Shipped engines | [Plugin SDK Overview](OVERVIEW.md) |
| Capability matrix | [CONNECTOR_CAPABILITY_MATRIX_0_38](../11_DEVELOPMENT/CONNECTOR_CAPABILITY_MATRIX_0_38.json) |
