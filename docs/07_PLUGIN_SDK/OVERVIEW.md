# Plugin SDK Overview

> **Status: Available in ETLantic 0.43.0** for the shipped protocols below.
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
| Observability provider | [OBSERVABILITY_PROVIDER](OBSERVABILITY_PROVIDER.md) | core reference + `etlantic[otel]` |
| Run history provider | [RUN_HISTORY_PROVIDER](RUN_HISTORY_PROVIDER.md) | file / in-memory reference |
| Event consumer | [EVENT_CONSUMER](EVENT_CONSUMER.md) | trend consumer reference |
| Source / sink / storage connectors | [CONNECTOR_SDK](CONNECTOR_SDK.md) | core `local-files`; `etlantic-s3`, `etlantic-iceberg`, `etlantic-snowflake`, `etlantic-sql` |
| Portable transform compiler | [PORTABLE_TRANSFORM_COMPILER](PORTABLE_TRANSFORM_COMPILER.md) | engine packages above |
| Testing / conformance | [TESTING_PLUGINS](TESTING_PLUGINS.md) | `etlantic.testing` |

Compiler support is expressed through exact [DTCS](../04_TRANSFORMATIONS/DTCS.md) profiles, actions, functions,
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
Shipped plugins: dataframe / SQL / Spark / orchestrator / secrets /
observability / run history / event consumers / connectors / compilers
```

Every plugin consumes or contributes to planning, compilation, execution, or
evidence of a validated `PipelinePlan`. No plugin changes the meaning of the
pipeline.

## Core principles

- **Stable interfaces** within 0.x compatibility rules
- **Capability driven** — plugins declare what they support
- **Portable semantics** — preserve
  [ODCS](../03_DATA_CONTRACTS/ODCS.md),
  [DTCS](../04_TRANSFORMATIONS/DTCS.md), and
  [DPCS](../05_PIPELINES/DPCS.md) meaning
- **Honest capabilities** — unsupported semantics fail during planning
- **Secret safety** — plans contain references, never resolved credentials

## Appendix — planned / not shipped

These categories appear in older design pages and are **not** installable
protocols in **0.39.0**:

- Managed resource providers — Kubernetes/reference proof in 0.47 and
  supported provider packs in 0.51.
- Registry plugins / approval workflows — planned through 0.40–0.43.

Source / sink / **storage connectors** ship via
[Connector SDK](CONNECTOR_SDK.md) (`etlantic.storage_connectors`). The older
[Storage Plugin](STORAGE_PLUGIN.md) page points at that path; it is not a
separate unshipped protocol. See
[Resource Provider](RESOURCE_PROVIDER.md) for the managed-resource design stub.
Operator how-to: [Observability today](../06_EXECUTION/OBSERVABILITY_TODAY.md)
and [Reports and history](../06_EXECUTION/REPORTS_AND_HISTORY.md).

## Next Step

Continue with [Building a Plugin](BUILDING_A_PLUGIN.md) or a shipped protocol
page above.
