# Migration: 0.21 → 0.22

## Version pins

```bash
pip install 'etlantic==0.22.0'
pip install 'etlantic-polars==0.22.0'  # optional engines
```

Plugin packages require `etlantic>=0.22.0,<0.23`.

## Recommended import style

Prefer:

```python
import etlantic as etl
```

`from etlantic import Data, Pipeline` remains supported. Specialist symbols
previously imported from the root (`col`, `SqlQuery`, `PluginCapabilities`, …)
are **demoted** to 0.x compatibility aliases: they still import, but emit a
one-time `DeprecationWarning` and should move to their owning namespace
(`etlantic.sql`, `etlantic.capabilities`, …) or lazy attribute
(`etl.sql`, …).

See [Surface Inventory](../10_REFERENCE/SURFACE_INVENTORY.md).

## Engine identity sets

Do not treat `DATAFRAME_ENGINES` / `SPARK_ENGINES` as privilege allowlists.
They remain documented first-party name defaults only. Unknown engine names
must register via discovery + capabilities like any other plugin.

## Capability vocabulary

Plugins should advertise `vocabulary_version="etlantic.capabilities/1"`
(default on `PluginCapabilities`). Claims must satisfy implication rules
(for example `sql_merge` ⇒ `sql`). Run public conformance suites before
shipping overstated flags.

## Compatibility check

```bash
etlantic plugin compatibility your-plugin-package --format human
```

## Conformance entry points

Use only public `etlantic.testing` symbols:

| Family | Suite |
|---|---|
| Dataframe | `run_conformance_suite` |
| SQL | `run_sql_conformance_suite` |
| Spark | `run_spark_conformance_suite` |
| Orchestrator | `run_orchestrator_conformance_suite` |
| Scheduler | `run_scheduler_conformance_suite` |
| Secrets | `run_secret_conformance_suite` |
| Portable transform | `run_portable_transform_conformance_suite` |

## Protocol freeze

0.22 does **not** freeze protocol `/1`. See
[Protocol Evolution](../07_PLUGIN_SDK/PROTOCOL_EVOLUTION.md).
