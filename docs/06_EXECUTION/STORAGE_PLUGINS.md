# Storage Plugins

> **Status: Partially available in ETLantic 0.43.0.** Structured connector
> protocols ship under `etlantic.connectors`. Built-in memory/CSV/JSON/callable
> storage remains; cloud connectors are Experimental optional packages.
> See [Connector SDK](../07_PLUGIN_SDK/CONNECTOR_SDK.md) and
> [Landing zone](LANDING_ZONE.md).

## What ships in 0.43

| Surface | Status |
|---|---|
| Memory / callable / JSON / CSV / no-write | Available ([Storage today](STORAGE_TODAY.md)) |
| `local-files` directory landing zone | Preview |
| `etlantic-s3` / `etlantic-iceberg` / `etlantic-snowflake` | Experimental (Alpha) |
| PostgreSQL connectors (`etlantic-sql`) | Experimental connector path |
| Continuous directory watch | Out of core (0.39+) |

## Authoring shape

Extracts and loads keep logical assets; profiles map them:

```python
customers: Extract[Customer] = Extract(asset="customers")
warehouse: Load[Customer] = Load(
    input=normalized.result,
    asset="warehouse.customers",
)
```

Swap providers via profile assets without rewriting topology.

## Related

- [Storage Today](STORAGE_TODAY.md) — shipped backends
- [Landing zone](LANDING_ZONE.md)
- [Connector SDK](../07_PLUGIN_SDK/CONNECTOR_SDK.md)
- [Storage plugin SDK](../07_PLUGIN_SDK/STORAGE_PLUGIN.md)
- [Resource Providers (future)](RESOURCE_PLUGINS.md)
