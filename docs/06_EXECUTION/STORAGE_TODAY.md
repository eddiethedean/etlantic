# Storage Today

> **Status: Available in ETLantic 0.18.0.** This page describes what ships
> today. Cloud warehouse and object-store storage plugins are **not** shipped.

## What you can use now

Core ETLantic resolves extract/load **assets** through local storage backends:

| Backend | Role |
|---|---|
| Memory | In-process seed/get for tutorials and tests |
| Callable | Custom Python callables for read/write |
| JSON | Stdlib JSON files |
| CSV | Stdlib CSV files |
| Null / no-write | Plan and validate without publishing |

Engine plugins add their own I/O (Polars/Pandas frames, SQL relations, Spark
datasets). Those are engine capabilities, not a separate portable storage
plugin protocol.

```python
from etlantic import CsvStorage, JsonStorage, MemoryStorage, PipelineRuntime

runtime = PipelineRuntime(storage=MemoryStorage())
# or JsonStorage / CsvStorage for durable local files — see examples/file_storage.py
```

## What is not shipped

A general **storage plugin protocol** for Snowflake, BigQuery, S3, Iceberg,
Delta Lake, and similar systems is a **future design**. Do not treat design
proposal catalogs as installable APIs.

See [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) for the authoritative
Available / Experimental / Not included tables.

## Profiles and assets

Pipelines declare logical asset names (`Extract(asset=...)`, `Load(asset=...)`).
Profiles and runtime storage resolve those names. Keep credentials out of
contracts and plans.

## Related

- [Quickstart](../01_GETTING_STARTED/QUICKSTART.md) — memory seed/run
- [File storage example](https://github.com/eddiethedean/etlantic/blob/main/examples/file_storage.py)
- [Storage plugin protocol (future)](../07_PLUGIN_SDK/STORAGE_PLUGIN.md)
- [Storage plugins design study (not shipped)](STORAGE_PLUGINS.md)
