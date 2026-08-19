# Plugins

!!! warning "Future design overview — not an operator manual"
    This page is a **design sketch** of a broader plugin catalog (including
    unshipped backends). Do **not** implement against it. For **shipped**
    protocols, use [Plugin SDK Overview](../07_PLUGIN_SDK/OVERVIEW.md) and
    [Building a Plugin](../07_PLUGIN_SDK/BUILDING_A_PLUGIN.md). For storage
    that exists today, see [Storage today](STORAGE_TODAY.md).

## What ships in 0.48 (start here)

| Category | Reality in 0.48 |
|---|---|
| Dataframe / SQL / Spark engines | Shipped as `etlantic-*` packages |
| Orchestrators | Airflow compile + Prefect local MVP |
| Schedules / workers | FastAPI gateway + `etlantic scheduler serve` / `worker serve` |
| Secrets | Env / file / keyring providers |
| Observability / run history / event consumers | Shipped protocols in 0.34 (M6) |
| Extract / Load I/O | Bind to typed source / sink / storage connectors through assets and profiles |
| General storage / connector SDK | Shipped as `etlantic.source/1`, `etlantic.sink/1`, and `etlantic.storage/1`; see [Connector SDK](../07_PLUGIN_SDK/CONNECTOR_SDK.md) |
| Resource providers | Experimental `etlantic-k8s` (`FakeKubernetes`); live Kind skipped |
| Spark Connect provider | Experimental `etlantic-spark-connect` fake; live skipped |
| Kafka / managed registries | Experimental extras (`etlantic-kafka`, `etlantic-schemaregistry`) |

Authoring uses `Extract` / `Load` with `asset=` (see
[Extracts](../05_PIPELINES/EXTRACTS.md) and [Loads](../05_PIPELINES/LOADS.md)).
`Source` / `Sink` types were removed; wire JSON may still say `"source"` /
`"sink"` as node kinds — that is not a plugin category.

## Goals (design intent)

Plugins should preserve pipeline semantics, be independently installable,
declare capabilities honestly, and stay loosely coupled to core.

## Planned catalog (not installable)

The following categories appear in older design pages and **must not** be
treated as 0.38 APIs:

- Managed resource providers — Experimental `etlantic-k8s` on
  [Resource Provider](../07_PLUGIN_SDK/RESOURCE_PROVIDER.md); live packs 0.51
- Registry plugins / approval workflows
- Dagster orchestrator compiler (planned 0.49)

## Next step

1. [Plugin SDK Overview](../07_PLUGIN_SDK/OVERVIEW.md) — shipped protocol table
2. [Building a Plugin](../07_PLUGIN_SDK/BUILDING_A_PLUGIN.md)
3. [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md)
