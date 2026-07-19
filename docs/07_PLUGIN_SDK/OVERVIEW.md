# Plugin SDK Overview

> **Status: Available in ETLantic 0.18.0** for the shipped protocols below.
> Future protocols are listed only in the appendix—do not treat them as APIs.

For the package-from-zero workflow, start with
[Building an ETLantic Plugin](BUILDING_A_PLUGIN.md).

The Plugin SDK defines public interfaces used to extend ETLantic without
modifying core. Core owns modeling, validation, planning, contract
coordination, lifecycle semantics, and result normalization. Plugins provide
concrete runtime behavior.

## Shipped protocols (use these)

| Protocol | Guide | Typical package |
|---|---|---|
| Dataframe | [DATAFRAME_PLUGIN](DATAFRAME_PLUGIN.md) | `etlantic-polars`, `etlantic-pandas` |
| SQL | [SQL_PLUGIN](SQL_PLUGIN.md) | `etlantic-sql` |
| PySpark | [PYSPARK_PLUGIN](PYSPARK_PLUGIN.md) | `etlantic-pyspark` |
| Orchestrator / scheduler | [ORCHESTRATOR_PLUGIN](ORCHESTRATOR_PLUGIN.md) | `etlantic-airflow`, `etlantic-prefect` |
| Secret provider | [SECRET_PROVIDER](SECRET_PROVIDER.md) | `etlantic-keyring` |
| Portable transform compiler | [PORTABLE_TRANSFORM_COMPILER](PORTABLE_TRANSFORM_COMPILER.md) | engine packages above |
| Testing / conformance | [TESTING_PLUGINS](TESTING_PLUGINS.md) | `etlantic.testing` |

Compiler support is expressed through exact DTCS profiles, actions, functions,
operators, types, and modes. Plugin identity alone never implies portable
coverage.

## Architecture (shipped)

```text
ETLantic Core
        │
        ▼
Validation → Planning → PipelinePlan
        │
        ▼
Shipped plugins: dataframe / SQL / Spark / orchestrator / secrets / compilers
```

Every plugin consumes or contributes to planning, compilation, or execution of
a validated `PipelinePlan`. No plugin changes the meaning of the pipeline.

## Core principles

- **Stable interfaces** within 0.x compatibility rules
- **Capability driven** — plugins declare what they support
- **Portable semantics** — preserve ODCS, DTCS, and DPCS meaning
- **Honest capabilities** — unsupported semantics fail during planning
- **Secret safety** — plans contain references, never resolved credentials

## Appendix — future / not shipped

These categories appear in older design pages and are **not** installable
protocols in 0.18.0:

- General storage plugins (Snowflake, S3, Iceberg, …) — see
  [Storage today](../06_EXECUTION/STORAGE_TODAY.md)
- Resource providers
- Registry plugins / approval workflows
- Observability provider protocol (beyond today's OTEL optional hooks)

See [STORAGE_PLUGIN](STORAGE_PLUGIN.md), [RESOURCE_PROVIDER](RESOURCE_PROVIDER.md),
and [OBSERVABILITY_PROVIDER](OBSERVABILITY_PROVIDER.md) (Future design banners).

## Next Step

Continue with [Building a Plugin](BUILDING_A_PLUGIN.md) or a shipped protocol
page above.
