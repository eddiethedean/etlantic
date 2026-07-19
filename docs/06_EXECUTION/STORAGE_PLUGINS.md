# Storage Plugins (Design Proposal)

> **Status: Future design — not shipped.** This page is a design study.
> Do not treat the catalogs below as installable product.
>
> **Storage today:** memory, callable, JSON, CSV, and no-write backends, plus
> engine-specific I/O. See [Storage Today](STORAGE_TODAY.md) and
> [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md).

## Intent (aspirational)

A future storage plugin protocol would translate logical extract/load assets
into operations for concrete storage technologies, without embedding
storage-specific APIs into pipeline definitions.

```text
Pipeline Plan
      │
      ▼
 Storage Plugin (future)
      │
 ┌────┼─────────────────────────┐
 ▼    ▼            ▼            ▼
 … candidate backends (not shipped) …
```

## Candidate backends (not available)

The following are **design targets only** — none of these are first-party
ETLantic storage plugins in 0.18.0:

- Parquet as a portable storage plugin
- MySQL / SQLite / DuckDB as storage plugins (SQL engine plugin is separate)
- Snowflake / BigQuery
- Delta Lake / Apache Iceberg
- Amazon S3 / Azure Blob / Google Cloud Storage

What ships instead: [Storage Today](STORAGE_TODAY.md).

## Authoring shape (when shipped)

Extracts and loads would keep logical assets; profiles would map them:

```python
customers: Extract[Customer] = Extract(asset="customers")
warehouse: Load[Customer] = Load(
    input=normalized.result,
    asset="warehouse.customers",
)
```

## Related

- [Storage Today](STORAGE_TODAY.md) — shipped backends
- [Storage plugin SDK (future)](../07_PLUGIN_SDK/STORAGE_PLUGIN.md)
- [Resource Providers (future)](RESOURCE_PLUGINS.md)
