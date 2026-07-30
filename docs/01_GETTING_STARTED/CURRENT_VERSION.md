# ETLantic 0.35 User Guide

Use this page **after** Ada/Grace success on the docs home
[green path](../README.md). Do **not** start here for install.

ETLantic **0.35.0** is a **Beta** (PyPI) release for documented single-tenant
pilots. Linked reference and design pages may describe Experimental, partial,
or future work and retain their own status labels.

## After first success

1. Optional: [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
2. [Capabilities](CAPABILITIES.md) — what you can use today
3. [What's new in 0.35](WHATS_NEW_0_35.md)
4. [Learning path](LEARNING_PATH.md)
5. [Upgrade](UPGRADE.md) if migrating from an earlier minor

Prefer `import etlantic as etl` for application code. Portable quality rules live
under `etl.quality` (`etlantic.quality/1`).

## Choose your next task

| Goal | Guide |
|---|---|
| Inventory / migrate SparkForge projects | [What's new in 0.35](WHATS_NEW_0_35.md) / [SparkForge migration](../09_MEDALLANTIC/SPARKFORGE_MIGRATION.md) |
| Application-pipeline testing preview | [Capabilities](CAPABILITIES.md) / `etlantic.testing` |
| Configure observability and durable run history | [What's new in 0.34](WHATS_NEW_0_34.md) / [Migration 0.33 → 0.34](../11_DEVELOPMENT/MIGRATION_0_33_TO_0_34.md) |
| Author without classes / JSON round trip | [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md) |
| Native bronze/silver/gold + portable rules | `pip install medallantic` / [Facade packages](../11_DEVELOPMENT/FACADE_PACKAGES.md) |
| SQL / SqlPipelineBuilder migration | [What's new in 0.33](WHATS_NEW_0_33.md) / [Migration 0.32 → 0.33](../11_DEVELOPMENT/MIGRATION_0_32_TO_0_33.md) |
| Visual builder / service integration | [Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md) |
| FastAPI reference adapter | `pip install etlantic-fastapi` / [Application integration](../08_VISUALIZATION/APPLICATION_INTEGRATION.md) |
| Read and write JSON or CSV | [File storage](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) |
| Execute with Polars | [Polars tutorial](../06_EXECUTION/POLARS_TUTORIAL.md) |
| Upgrade from 0.34 | [Migration 0.34 → 0.35](../11_DEVELOPMENT/MIGRATION_0_34_TO_0_35.md) |

## Status vocabulary

Pages use **Available**, **Experimental**, **Partial**, and **Future design**
labels. Prefer Available paths for pilots; treat Experimental and Future design
as non-contractual.
