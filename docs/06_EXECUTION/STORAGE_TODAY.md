# Storage Today

> **Status: Available in ETLantic 0.45.0.** Decision tree for what ships today.
> Landing-zone `local-files` is a **source connector**, not an extension of
> `CsvStorage`.

## Decision tree

```text
Need in-process seed / get for tutorials and tests?
  └─ Yes → MemoryStorage (or callable bindings)
Need a single durable local file (one JSON or CSV path)?
  └─ Yes → JsonStorage / CsvStorage bindings (see examples/file_storage.py)
Need a directory/glob landing zone (snapshot or incremental ledger)?
  └─ Yes → Profile binding provider "local-files" (NOT CsvStorage)
Need object store / warehouse / table format I/O?
  └─ Experimental packages only (s3 / iceberg / snowflake) — pin matching minor
```

Landing is **not** “CSV storage with a folder.” `CsvStorage` binds one logical
asset to one CSV file. `local-files` lists identities under a root/glob, tracks
consume/checkpoint state, and returns a landing read manifest. Continuous watch
is a submitter outside core — see [Landing zone](LANDING_ZONE.md).

## Single-file and memory bindings

Core resolves extract/load **assets** through local storage backends:

| Backend | Role |
|---|---|
| Memory | In-process seed/get for tutorials and tests |
| Callable | Custom Python callables for read/write |
| JSON | Stdlib JSON files (one path per asset) |
| CSV | Stdlib CSV files (one path per asset) |
| Null / no-write | Plan and validate without publishing |

```python
from etlantic import PipelineRuntime
from etlantic.storage import CsvStorage, JsonStorage, MemoryStorage

runtime = PipelineRuntime(storage=MemoryStorage())
# or JsonStorage / CsvStorage for durable local files — see examples/file_storage.py
```

Engine plugins add their own I/O (Polars/Pandas frames, SQL relations, Spark
datasets). Those are engine capabilities, not a portable storage plugin protocol.

## Landing zone (`local-files`)

Use a profile asset binding with `provider: "local-files"` for directory/glob
CSV landing in `snapshot` or `incremental` mode. Switch modes on the binding —
do not rewrite `Extract` topology. Full guide: [Landing zone](LANDING_ZONE.md).

## Experimental cloud connectors

Optional packages (`etlantic-s3`, `etlantic-iceberg`, `etlantic-snowflake`)
expose Experimental reference connectors. Swap profile bindings without changing
graph topology. They are **not** a general storage-plugin protocol and are not
extensions of `CsvStorage` / `JsonStorage`.

See [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) for Available /
Experimental / Not included tables.

## Profiles and assets

Pipelines declare logical asset names (`Extract(asset=...)`, `Load(asset=...)`).
Profiles and runtime storage resolve those names. Keep credentials out of
contracts and plans.

## Related

- [Landing zone](LANDING_ZONE.md)
- [File storage tutorial](FILE_STORAGE_TUTORIAL.md)
- [Quickstart](../01_GETTING_STARTED/QUICKSTART.md) — memory seed/run
- [File storage example](https://github.com/eddiethedean/etlantic/blob/main/examples/file_storage.py)
- [Storage plugin protocol (planned)](../07_PLUGIN_SDK/STORAGE_PLUGIN.md)
- [Storage plugins design study](STORAGE_PLUGINS.md)
