# ETLantic 0.32 User Guide

Use this page **after** Ada/Grace success on the docs home
[green path](../README.md). Do **not** start here for install.

ETLantic **0.32.0** is a **Beta** (PyPI) release for documented single-tenant
pilots. Linked reference and design pages may describe Experimental, partial,
or future work and retain their own status labels.

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — what you can use today
3. [What's new in 0.32](WHATS_NEW_0_32.md)
4. [Learning path](LEARNING_PATH.md)
5. [Upgrade](UPGRADE.md) if migrating from an earlier minor

Prefer `import etlantic as etl` for application code. Portable quality rules live
under `etl.quality` (`etlantic.quality/1`).

## Choose your next task

| Goal | Guide |
|---|---|
| Author without classes / JSON round trip | [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md) |
| Native bronze/silver/gold + portable rules | `pip install medallantic` / [Facade packages](../11_DEVELOPMENT/FACADE_PACKAGES.md) |
| Visual builder / service integration | [Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md) |
| FastAPI reference adapter | `pip install etlantic-fastapi` / [Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md) |
| Read and write JSON or CSV | [File storage](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) |
| Execute with Polars | [Polars tutorial](../06_EXECUTION/POLARS_TUTORIAL.md) |
| Upgrade from 0.31 | [Migration 0.31 → 0.32](../11_DEVELOPMENT/MIGRATION_0_31_TO_0_32.md) |

## Status vocabulary

Pages use **Available**, **Experimental**, **Partial**, and **Future design**
labels. Prefer Available paths for pilots; treat Experimental and Future design
as non-contractual.
